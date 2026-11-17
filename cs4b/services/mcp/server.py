"""Part 2 (Lab 34B): the MCP query server — the one audited door to the data.

Four READ tools, a closed catalog, a read-only connection (gate.connect_ro:
mode=ro plus SQLite's authorizer), every query through gate.run_query, and a
ledger event for every call and every refusal.

    mcp dev services/mcp/server.py      # the Inspector

ASKPANEL_DB overrides the database path so tests run on a scratch database.
"""
import os
import sys
from pathlib import Path

import yaml
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from askpanel import audit, clock, gate, tools  # noqa: E402

# The closed catalog. A literal, read by the self-check: adding a tool here
# (or a @mcp.tool not listed here) fails catalog conformance.
REGISTRY = {
    "list_tables": "READ",
    "describe_table": "READ",
    "sample_values": "READ",
    "run_query": "READ",
}

_P = yaml.safe_load((ROOT / "params.yaml").read_text())
DB_PATH = Path(os.environ.get("ASKPANEL_DB", ROOT / _P["data"]["db"]))
TABLES = tuple(_P["server"]["tables"])
MAX_ROWS = int(_P["server"]["max_rows"])
TIMEOUT_S = float(_P["server"]["timeout_s"])

LEDGER = audit.Ledger(clock=clock.clock)
CON = gate.connect_ro(DB_PATH, tables=set(TABLES))

mcp = MCPServer("askpanel-query")


class TableList(BaseModel):
    tables: list[str]


class ColumnDescription(BaseModel):
    column: str
    description: str = ""


class TableDescription(BaseModel):
    table: str
    columns: list[ColumnDescription]


class SampleValues(BaseModel):
    table: str
    column: str
    values: list[str | int | float | None]


class QueryResult(BaseModel):
    sql: str
    columns: list[str]
    rows: list[list[str | int | float | None]]
    row_count: int
    truncated: bool
    ms: float


def _cols(table):
    if table not in TABLES:
        raise gate.GateError("not_authorized", f"unknown table {table!r}")
    cur = CON.execute(f'SELECT * FROM "{table}" LIMIT 0')
    return [d[0] for d in cur.description]


def _refused(tool, e: gate.GateError):
    LEDGER.record("policy_block", tool=tool, code=e.code)
    # ToolError is an expected refusal: the client sees is_error with
    # "code: detail" intact; a bare GateError would be logged as a crash
    # and its message replaced, losing the code the repair edge needs.
    raise ToolError(f"{e.code}: {e.detail}") from e


@mcp.tool()
def list_tables() -> TableList:
    """The tables and views the agent may query (READ)."""
    LEDGER.record("tool_call", tool="list_tables")
    return TableList(tables=list(TABLES))


@mcp.tool()
def describe_table(table: str) -> TableDescription:
    """Columns of one catalog table, with the notes the model reads (READ)."""
    try:
        cols = _cols(table)
    except gate.GateError as e:
        _refused("describe_table", e)
    LEDGER.record("tool_call", tool="describe_table", table=table)
    return TableDescription(table=table, columns=[
        ColumnDescription(column=c, description=tools.DESCRIPTIONS.get(c, ""))
        for c in cols])


@mcp.tool()
def sample_values(table: str, column: str, limit: int = 20) -> SampleValues:
    """Distinct values of one column: exact names and spellings (READ)."""
    try:
        if column not in _cols(table):
            raise gate.GateError("invalid", f"no column {column!r} in {table}")
        r = gate.run_query(CON, f'SELECT DISTINCT "{column}" FROM "{table}" '
                                f'WHERE "{column}" IS NOT NULL ORDER BY 1 '
                                f'LIMIT {int(limit)}')
    except gate.GateError as e:
        _refused("sample_values", e)
    LEDGER.record("tool_call", tool="sample_values", table=table, column=column)
    return SampleValues(table=table, column=column,
                        values=[row[0] for row in r["rows"]])


@mcp.tool()
def run_query(sql: str) -> QueryResult:
    """Run ONE gated SELECT (READ). Anything else is refused."""
    try:
        r = gate.run_query(CON, sql, max_rows=MAX_ROWS, timeout_s=TIMEOUT_S)
    except gate.GateError as e:
        _refused("run_query", e)
    LEDGER.record("tool_call", tool="run_query", rows=r["row_count"],
                  truncated=r["truncated"], ms=r["ms"])
    return QueryResult(**r)


if __name__ == "__main__":
    mcp.run()
