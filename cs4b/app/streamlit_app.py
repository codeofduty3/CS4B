"""Part 4 (Lab 36B): Ask the Panel, the analyst's interface.

    streamlit run app/streamlit_app.py

Thin by design: it calls the same LangGraph agent as agent/run.py, which
reaches the data only through the MCP server. Replay mode (the default)
answers recorded questions from outputs/cache/ with no key; record mode
calls Gemini and needs GEMINI_API_KEY.
"""
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402
import yaml  # noqa: E402
from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402

from agent import graph, mcp_client, model  # noqa: E402
from askpanel import llm  # noqa: E402

P = yaml.safe_load((ROOT / "params.yaml").read_text())
st.set_page_config(page_title="Ask the Panel", layout="wide")


@st.cache_resource
def get_tools():
    """One MCP client session for the app's lifetime (Streamlit reruns the
    script on every input)."""
    return mcp_client.connect().tools()


@st.cache_resource
def get_checkpointer():
    """Shared by both modes, so switching mode keeps the conversation."""
    return InMemorySaver()


@st.cache_resource
def get_app(mode):
    return graph.build_graph(model.make_model(P, mode), get_tools(), P,
                             checkpointer=get_checkpointer())


def new_conversation():
    st.session_state.thread = f"ui-{uuid.uuid4().hex[:8]}"
    st.session_state.turns = []


if "thread" not in st.session_state:
    new_conversation()

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Ask the Panel")
    modes = ["replay", "record"]
    mode = st.radio("Model mode", modes, index=modes.index(P["model"]["mode"]),
                    help="replay: answers from outputs/cache/ only, no key, no cost. "
                         "record: calls Gemini (needs GEMINI_API_KEY) and caches the reply.")
    st.caption(f"Model: `{P['model']['name']}`")
    st.caption("Panel: " + ("real (" + P["data"]["real_panel"] + ")"
                            if P["data"].get("use_real") else "fixture"))
    st.button("New conversation", on_click=new_conversation, width="stretch")
    turns = st.session_state.turns
    if turns:
        st.divider()
        st.metric("Conversation cost", f"${sum(t['usd'] for t in turns):.5f}")
        st.metric("Model calls", sum(t["calls"] for t in turns))
    st.caption(f"Thread `{st.session_state.thread}`")


# ---------------------------------------------------------------- one turn
def show(turn):
    with st.chat_message("user"):
        st.write(turn["question"])
    with st.chat_message("assistant"):
        if turn.get("failure"):
            st.error(turn["failure"])
            return
        st.write(turn["answer"])
        if turn["sql"]:
            st.code(turn["sql"], language="sql")
        r = turn["result"]
        if r and r["rows"]:
            st.dataframe(pd.DataFrame(r["rows"], columns=r["columns"]),
                         hide_index=True, width="stretch")
            if r.get("truncated"):
                st.caption(f"Truncated at the server's row cap ({r['row_count']} rows).")
        st.caption(f"Cost ${turn['usd']:.5f} · {turn['calls']} model call(s) · "
                   f"{turn['tokens']:,} tokens · {turn['mode']} mode")
        with st.expander("Trace"):
            # mixed types per column (ints, codes, hashes): show every cell as text
            rows = [{k: "" if v is None else str(v) for k, v in t.items() if k != "run_id"}
                    for t in turn["trace"]]
            st.dataframe(pd.DataFrame(rows).fillna(""), hide_index=True, width="stretch")


st.title("Ask the Panel")
st.caption("Questions about the BDC holdings panel, answered with one read-only SQL query "
           "and the SQL behind it.")
for t in st.session_state.turns:
    show(t)

if q := st.chat_input("Ask about the BDC holdings"):
    turn = {"question": q, "mode": mode}
    try:
        with st.spinner("Thinking..."):
            s = graph.ask(get_app(mode), q, st.session_state.thread,
                          run_id=f"{st.session_state.thread}-{len(st.session_state.turns) + 1}")
        query = s.get("query") or {}
        turn.update(answer=s["answer"], sql=query.get("sql"), result=s.get("result"),
                    usd=s["usd"], tokens=s["tokens"], trace=s["trace"],
                    calls=sum(t["node"] == "generate" for t in s["trace"]))
    except llm.CacheMiss:
        turn.update(failure="This question (with this conversation's history) is not in the "
                            "replay cache. Ask a recorded question exactly as recorded, or "
                            "switch to record mode.", usd=0.0, calls=0)
    except RuntimeError as e:          # record mode without GEMINI_API_KEY
        turn.update(failure=str(e), usd=0.0, calls=0)
    st.session_state.turns.append(turn)
    st.rerun()
