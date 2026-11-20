summary: Build a natural-language BDC analytics agent with a guarded MCP server, replayable LangGraph workflow, and Streamlit interface.
id: ask-the-panel
categories: python,langgraph,mcp,streamlit,sqlite
environments: Web
status: Published
authors: Dany Sigha
feedback link: https://github.com/codeofduty3/CS4B/issues

# Ask the Panel

## Overview
Duration: 2:00

Ask the Panel is a natural-language analyst interface over a BDC holdings
panel. The model turns a question into one read-only SQL query. A typed
contract, a SQLite gate, and an MCP server protect the data before any rows
are returned.

The finished system has four layers:

- a Pydantic query contract with static SQL validation;
- a four-tool MCP server over a read-only SQLite connection;
- a LangGraph agent with repair and budget edges;
- a Streamlit interface backed by committed record/replay responses.

By the end, you will have a reproducible query agent that runs without an API
key and a clear audit record for every answer.

## Build the database and view
Duration: 4:00

Create the environment and install the pinned dependencies.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The real panel is committed, while the generated database is ignored. Build
it and verify the analytical view.

```bash
python tools/build_db.py
```

The command should report that `holdings_v` meets the contract. The view
contains current-schedule rows and exposes derived fields such as `price`
and `is_debt`.

## Guard the SQL
Duration: 5:00

Inspect the static and database-backed SQL protections.

```bash
PYTHONPATH=src python - <<'PY'
from askpanel import gate

for sql in [
    "SELECT bdc FROM holdings_v",
    "DELETE FROM holdings",
    "SELECT 1; DROP TABLE holdings",
    "SELECT * FROM sqlite_master",
]:
    try:
        print("allowed", gate.static_check(sql))
    except gate.GateError as e:
        print(e.code, e.detail)
PY
```

`SQLQuery` applies the same static check before execution and requires exactly
one of `sql` or `decline`. Validation errors retain the gate’s code so the
agent can repair the query.

## Run the MCP server
Duration: 5:00

Open the Inspector.

```bash
mcp dev services/mcp/server.py
```

The server exposes exactly four READ tools:

| Tool | Purpose |
|---|---|
| `list_tables` | List the closed query catalog |
| `describe_table` | Return columns and model-facing descriptions |
| `sample_values` | Inspect exact names and spellings |
| `run_query` | Run one gated SELECT |

Every successful call and refusal is recorded in the ledger. Try
`SELECT * FROM sqlite_master` and confirm that the Inspector reports
`not_authorized`.

## Run the agent
Duration: 5:00

Replay the ten recorded questions:

```bash
python agent/run.py --mode replay
```

The LangGraph workflow is:

```text
load_schema -> generate -> check -> execute -> summarize
                         ^          |
                         +--repair--+
```

The cache key includes the model, system prompt, schema, history, question,
attempt, prior error, and prior SQL. A changed request therefore produces a
cache miss instead of silently reusing a stale answer.

## Use the Streamlit interface
Duration: 3:00

Start the interface:

```bash
streamlit run app/streamlit_app.py
```

Replay is the default. Ask a recorded question and verify the screen shows:

- the natural-language answer;
- the generated SQL;
- result rows;
- cost, model calls, tokens, and execution mode;
- the full trace.

For the follow-up demonstration, ask the `q07` question first, then `q08` in
the same conversation.

## Verify reproducibility
Duration: 3:00

Run the full grading checks:

```bash
python tests/run_tests.py
pytest -q tests/test_server.py
python agent/run.py --mode replay
PYTHONPATH=src python -m askpanel.check
```

The repository is designed so that a clean clone needs no API key for any of
these commands.

## Congratulations
Duration: 1:00

You have built a constrained analytics agent with four important properties:

1. SQL is validated before execution.
2. Database access is read-only and passes through one audited server.
3. Model output and execution are replayable without a key.
4. The interface exposes both the answer and the evidence behind it.

Return to the [repository](https://github.com/codeofduty3/CS4B) for the source,
tests, questions, and economics.
