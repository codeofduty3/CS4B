"""Part 3 (Lab 35B): answer questions/questions.yaml through the agent.

    python agent/run.py --mode record     # calls Gemini once per new request, caches it
    python agent/run.py --mode replay     # cache only: no key, no cost (the default)

Writes outputs/questions/<id>.json for every question. Each question runs on
its own thread; a follow_up runs on the thread of the question it follows,
so the model sees that question and its SQL in the history.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[0] = str(ROOT)                  # import agent.*, not agent/'s files as top-level modules
sys.path.insert(1, str(ROOT / "src"))

import yaml  # noqa: E402

from agent import graph, mcp_client, model  # noqa: E402
from askpanel import llm, questions  # noqa: E402


def output(q, thread, s):
    """The saved record: the OUTPUT_FIELDS the self-check reads, plus the
    numbers the economics and failure log are written from."""
    query = s.get("query") or {}
    return {"id": q["id"], "question": q["question"], "category": q["category"],
            "follows": q.get("follows"), "thread": thread,
            "sql": query.get("sql"), "decline": query.get("decline"),
            "explanation": query.get("explanation"),
            "answer": s["answer"], "result": s.get("result"),
            "error": s.get("error"), "stop": s.get("stop"),
            "model_calls": sum(t["node"] == "generate" for t in s["trace"]),
            "tokens": s["tokens"], "usd": s["usd"], "trace": s["trace"]}


def main(argv=None):
    P = yaml.safe_load((ROOT / "params.yaml").read_text())
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mode", choices=["record", "replay"], default=P["model"]["mode"])
    args = ap.parse_args(argv)

    qs = questions.load(ROOT / "questions/questions.yaml")
    probs = questions.validate(qs)
    if probs:
        print("questions.yaml:", "; ".join(probs))
    out_dir = ROOT / "outputs/questions"
    out_dir.mkdir(parents=True, exist_ok=True)

    tools = mcp_client.connect()
    app = graph.build_graph(model.make_model(P, args.mode), tools.tools(), P)
    threads, missed = {}, []
    try:
        for q in qs:
            thread = threads[q["follows"]] if q.get("follows") else q["id"]
            threads[q["id"]] = thread
            try:
                s = graph.ask(app, q["question"], thread, run_id=q["id"])
            except llm.CacheMiss as e:
                missed.append(q["id"])
                print(f"{q['id']}: not in the replay cache ({e}); record it first")
                continue
            o = output(q, thread, s)
            (out_dir / f"{q['id']}.json").write_text(
                json.dumps(o, indent=2, sort_keys=True, default=str) + "\n",
                encoding="utf-8")
            path = " -> ".join(t["node"] + (f"[{t['outcome']}]" if t.get("outcome") else "")
                               for t in s["trace"])
            print(f"{q['id']} ({q['category']}, {o['model_calls']} call(s), "
                  f"${o['usd']:.5f}): {path}")
    finally:
        tools.close()
    print(f"{len(qs) - len(missed)}/{len(qs)} answered in {args.mode} mode -> {out_dir}")
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main())
