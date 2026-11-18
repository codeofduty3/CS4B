"""Part 3 (Lab 35B): the agent as a LangGraph StateGraph.

    load_schema -> generate -> check --ok--> execute --ok--> summarize
                       ^          |               |
                       +--repair--+------repair---+   (capped at agent.max_attempts)

The nodes come from askpanel.nodes.make_nodes; the check node is ours: it
accepts the model's reply only through the Pydantic contract
(agent.contract.validate_query), so the gate's refusal code (not_select,
multiple_statements, not_authorized, invalid, ...) lands in state["error"]
and the repair edge hands it back to the model.

compile(checkpointer=...) keeps each thread's state, so a follow-up on the
same thread_id starts from the history of the turn before it.
"""
import sys
from pathlib import Path
from typing import Optional, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from askpanel import clock as kclock, nodes  # noqa: E402

from agent.contract import validate_query  # noqa: E402


class AskState(TypedDict, total=False):
    # every list (trace, history) is returned whole by the nodes, so the
    # default overwrite reducer is the right one (operator.add would double it)
    question: str
    history: list
    schema: str
    attempt: int
    query: Optional[dict]
    error: Optional[dict]
    result: Optional[dict]
    answer: Optional[str]
    trace: list
    usd: float
    tokens: int
    stop: Optional[str]
    run_id: str


def make_check(clock):
    """The check node, over the Pydantic contract. Same trace record and
    return keys as the kit's check, so the routers work unchanged."""

    def rec(state, **kw):
        return state["trace"] + [{"run_id": state["run_id"],
                                  "step": len(state["trace"]) + 1,
                                  "ts": clock().isoformat(), "node": "check", **kw}]

    def check(state):
        q, err = validate_query(state["query"] or {})
        if err:
            return {"error": err, "attempt": state["attempt"] + 1,
                    "trace": rec(state, outcome=err["code"])}
        if q.sql is None:
            return {"query": q.model_dump(), "trace": rec(state, outcome="decline")}
        return {"query": q.model_dump(), "trace": rec(state, outcome="ok")}

    return check


def build_graph(model, tools, P, clock=kclock.clock, checkpointer=None):
    """model: a ReplayClient (agent.model.make_model). tools: the MCP client's
    calls (agent.mcp_client.McpTools.tools()). P: params.yaml as a dict."""
    a = P["agent"]
    N, after_check, after_execute = nodes.make_nodes(
        model, tools, clock, model_name=P["model"]["name"],
        max_attempts=a["max_attempts"], usd_cap=a["usd_cap_per_question"],
        token_cap=a["token_cap_per_question"])

    g = StateGraph(AskState)
    g.add_node("load_schema", N["load_schema"])
    g.add_node("generate", N["generate"])
    g.add_node("check", make_check(clock))
    g.add_node("execute", N["execute"])
    g.add_node("summarize", N["summarize"])
    g.add_edge(START, "load_schema")
    g.add_edge("load_schema", "generate")
    g.add_edge("generate", "check")
    g.add_conditional_edges("check", after_check,
                            {"execute": "execute", "generate": "generate",
                             "summarize": "summarize"})
    g.add_conditional_edges("execute", after_execute,
                            {"generate": "generate", "summarize": "summarize"})
    g.add_edge("summarize", END)
    return g.compile(checkpointer=checkpointer or InMemorySaver())


def ask(app, question, thread_id, run_id=None):
    """One turn on a thread: the history comes from the checkpointer, so a
    follow-up sees the questions and SQL before it."""
    cfg = {"configurable": {"thread_id": thread_id}}
    prev = app.get_state(cfg).values.get("history", [])
    return app.invoke(nodes.new_state(question, prev, run_id=run_id or thread_id), cfg)
