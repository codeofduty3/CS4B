"""Part 2 contract tests, over the MCP protocol in memory:

    pytest -q tests/test_server.py

The server is imported against a scratch database built from the fixture and
sql/holdings_v.sql (ASKPANEL_DB), so tests never touch the demo database.
A refused query is a result, not an exception: call_tool returns is_error.
"""
import asyncio
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from askpanel import catalog, db  # noqa: E402

_TMP = Path(tempfile.mkdtemp())
_PANEL = db.load_panel(ROOT / "data/fixture/panel_2p.csv")
os.environ["ASKPANEL_DB"] = str(db.build_db(
    _PANEL, _TMP / "server-test.sqlite", (ROOT / "sql/holdings_v.sql").read_text()))

from mcp import Client  # noqa: E402
from services.mcp import server  # noqa: E402


def call(name, args=None):
    async def go():
        async with Client(server.mcp) as c:      # in memory, no transport
            return await c.call_tool(name, args or {})
    return asyncio.run(go())


def test_catalog_is_closed():
    assert catalog.conformance(server.REGISTRY) == []

    async def names():
        async with Client(server.mcp) as c:
            return sorted(t.name for t in (await c.list_tools()).tools)
    assert asyncio.run(names()) == sorted(server.REGISTRY)


def test_list_and_describe():
    r = call("list_tables")
    assert not r.is_error
    assert set(r.structured_content["tables"]) == {"holdings_v", "filings", "holdings"}
    d = call("describe_table", {"table": "holdings_v"})
    cols = {c["column"] for c in d.structured_content["columns"]}
    assert cols == set(db.VIEW_COLUMNS)
    bad = call("describe_table", {"table": "secrets"})
    assert bad.is_error


def test_sample_values():
    r = call("sample_values", {"table": "holdings_v", "column": "bdc", "limit": 10})
    assert not r.is_error
    assert len(r.structured_content["values"]) == 4     # the four fixture BDCs


def test_select_works():
    r = call("run_query", {"sql": "SELECT bdc, COUNT(*) AS n FROM holdings_v "
                                  "GROUP BY bdc ORDER BY bdc"})
    assert not r.is_error
    sc = r.structured_content
    assert sc["row_count"] == 4 and sc["columns"] == ["bdc", "n"]
    assert server.LEDGER.find("tool_call", tool="run_query")


def test_writes_and_escapes_are_refused():
    before = len(server.LEDGER.find("policy_block"))
    refusals = ["INSERT INTO filings (adsh) VALUES ('x')",
                "DROP TABLE holdings",
                "ATTACH DATABASE 'x.db' AS x",
                "PRAGMA table_info(holdings)",
                "SELECT * FROM sqlite_master",
                "SELECT 1; DELETE FROM holdings"]       # a second statement after ;
    codes = ("not_select", "multiple_statements", "not_authorized",
             "invalid", "empty", "timeout")
    for sql in refusals:
        r = call("run_query", {"sql": sql})
        assert r.is_error, f"not refused: {sql}"
        text = " ".join(c.text for c in r.content)
        assert any(c in text for c in codes), f"no gate code in: {text}"
    blocks = server.LEDGER.find("policy_block", tool="run_query")
    assert len(server.LEDGER.find("policy_block")) - before == len(refusals)
    assert blocks, "refusals must land in the ledger"


def test_database_file_is_untouched_after_write_attempts():
    mtime = Path(os.environ["ASKPANEL_DB"]).stat().st_mtime_ns
    call("run_query", {"sql": "INSERT INTO filings (adsh) VALUES ('y')"})
    assert Path(os.environ["ASKPANEL_DB"]).stat().st_mtime_ns == mtime
