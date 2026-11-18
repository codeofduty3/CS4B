"""Part 3 (Lab 35B): the SQL-writing model, Gemini behind record/replay.

    make_model(P, "replay")   reads outputs/cache/ only: no key, no cost
    make_model(P, "record")   calls Gemini (GEMINI_API_KEY), then caches

The request is exactly nodes.build_request(...): the cache key is the
SHA-256 of all of it (model id, system prompt, schema, history, question,
attempt, error, prior SQL), so a replay answers only what was recorded.

Gemini is asked for JSON in the shape of the Pydantic contract (SQLQuery);
the graph's check node then validates the reply with validate_query, so a
malformed reply becomes a repairable error, not a crash.
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from askpanel import econ, llm  # noqa: E402

from agent.contract import SQLQuery  # noqa: E402

RETRY_CODES = {429, 500, 503}     # free-tier rate limits and transient errors


def render_prompt(req):
    """The user turn: schema, prior turns, the question and, on a repair,
    the failed SQL and the gate's error."""
    parts = [f"Tables and columns:\n{req['schema']}"]
    if req.get("history"):
        turns = "\n".join(f"- Q: {h['question']}\n  SQL: {h.get('sql') or '(declined)'}"
                          for h in req["history"])
        parts.append(f"Earlier in this conversation:\n{turns}")
    parts.append(f"Question: {req['question']}")
    if req.get("error"):
        e = req["error"]
        parts.append(f"Attempt {req['attempt'] + 1}. Your previous reply was refused.\n"
                     f"Previous SQL: {req.get('prior_sql') or '(none)'}\n"
                     f"Error: {e.get('code')}: {e.get('detail')}\n"
                     "Write a corrected query, or decline if the data cannot answer.")
    return "\n\n".join(parts)


def gemini_call(prices):
    """A callable(request) -> reply dict, for ReplayClient's record mode."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("record mode needs GEMINI_API_KEY (replay mode does not)")
    from google import genai            # imported here: replay never needs the SDK
    from google.genai import errors, types

    client = genai.Client(api_key=key)

    def call(req):
        config = types.GenerateContentConfig(
            system_instruction=req["system"], temperature=0,
            response_mime_type="application/json",
            response_json_schema=SQLQuery.model_json_schema())
        for n in range(5):
            try:
                resp = client.models.generate_content(
                    model=req["model"], contents=render_prompt(req), config=config)
                break
            except errors.APIError as e:
                if e.code not in RETRY_CODES or n == 4:
                    raise
                time.sleep(10 * 2 ** n)
        u = resp.usage_metadata
        t_in = u.prompt_token_count or 0
        # thinking tokens are billed as output
        t_out = (u.candidates_token_count or 0) + (u.thoughts_token_count or 0)
        out = {"tokens_in": t_in, "tokens_out": t_out,
               "usd": round(econ.step_usd(t_in, t_out, prices["usd_per_mtok_in"],
                                          prices["usd_per_mtok_out"]), 8)}
        try:
            reply = json.loads(resp.text)
        except (TypeError, ValueError):
            # neither sql nor decline: the check node calls it invalid and repairs
            return {**out, "sql": None, "decline": None, "explanation": "",
                    "raw": resp.text}
        return {**out, "sql": reply.get("sql"), "decline": reply.get("decline"),
                "explanation": reply.get("explanation") or ""}

    return call


def make_model(P, mode=None):
    """The model the graph calls: a ReplayClient over outputs/cache/."""
    mode = mode or P["model"]["mode"]
    if mode not in ("record", "replay"):
        raise ValueError(f"model mode must be record or replay, not {mode!r}")
    call = gemini_call(P["prices"]) if mode == "record" else None
    return llm.ReplayClient(ROOT / P["model"]["cache_dir"], mode, call=call)
