"""Part 2 (Lab 34B): synchronous tool calls over the MCP client.

LangGraph nodes and Streamlit are synchronous; the SDK client is async. One
long-lived session in a background event loop keeps the two apart, and the
server's four tools become the plain-function dict nodes.make_nodes expects.

A refused call raises ToolCallError carrying the gate's code, so the
execute node's repair edge can read it (getattr(e, "code", ...)).
"""
import asyncio
import threading

from mcp import Client


GATE_CODES = ("empty", "not_select", "multiple_statements", "not_authorized",
              "invalid", "timeout")


class ToolCallError(Exception):
    def __init__(self, tool, text):
        super().__init__(f"{tool}: {text}")
        self.tool, self.detail = tool, text
        # the SDK prefixes its own words, so find the gate's code in the text
        self.code = next((c for c in GATE_CODES if f"{c}:" in text), "tool_error")


class McpTools:
    """Holds one Client session open on a background loop. The session is
    entered and exited in the same task (_hold): doing them in different
    calls raises a cancel-scope error at shutdown."""

    def __init__(self, server, timeout_s=30.0):
        self._timeout = timeout_s
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop.run_forever, daemon=True).start()
        ready = threading.Event()
        asyncio.run_coroutine_threadsafe(self._hold(server, ready), self._loop)
        if not ready.wait(timeout_s):
            raise TimeoutError("MCP client session did not open")

    async def _hold(self, server, ready):
        self._stop = asyncio.Event()
        async with Client(server) as client:
            self._client = client
            ready.set()
            await self._stop.wait()

    def call(self, name, **args):
        fut = asyncio.run_coroutine_threadsafe(
            self._client.call_tool(name, args), self._loop)
        r = fut.result(self._timeout)
        if r.is_error:
            raise ToolCallError(name, " ".join(c.text for c in r.content))
        return r.structured_content

    def tools(self):
        """name -> callable, shaped as askpanel.nodes.make_nodes expects."""
        return {
            "list_tables": lambda: self.call("list_tables")["tables"],
            "describe_table": lambda table: self.call(
                "describe_table", table=table)["columns"],
            "sample_values": lambda table, column, limit=20: self.call(
                "sample_values", table=table, column=column, limit=limit)["values"],
            "run_query": lambda sql: self.call("run_query", sql=sql),
        }

    def close(self):
        self._loop.call_soon_threadsafe(self._stop.set)
        self._loop.call_soon_threadsafe(self._loop.stop)


def connect(server=None):
    """The agent's entry point: McpTools over the in-memory server."""
    if server is None:
        from services.mcp import server as srv
        server = srv.mcp
    return McpTools(server)
