"""Part 1 (Lab 33B): the model's output as a typed object, not a string.

The agent accepts SQL from the model only through SQLQuery, which runs the
gate's static checks (no database needed) and insists on exactly one of
sql or decline. The server's gate stays the authority: this layer refuses a
bad reply before any round trip, with a code the repair edge can hand back
to the model.
"""
import sys
from pathlib import Path
from typing import Optional

from pydantic import (BaseModel, ConfigDict, Field, ValidationError,
                      field_validator, model_validator)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from askpanel import gate  # noqa: E402


class ColumnInfo(BaseModel):
    """One column as the model reads it: a name and the catalog's note."""
    column: str
    description: str = ""


class SchemaCatalog(BaseModel):
    """What the model may query: every table, with its columns and notes."""
    tables: dict[str, list[ColumnInfo]]

    def render(self) -> str:
        """The schema text the prompt carries, one line per table."""
        return "\n".join(
            f"{t}(" + ", ".join(
                f"{c.column}: {c.description}" if c.description else c.column
                for c in cols) + ")"
            for t, cols in self.tables.items())


class QueryRequest(BaseModel):
    """One turn's input to the model, exactly as nodes.build_request
    assembles it. ReplayClient keys its cache on all of these fields, so
    anything the model sees belongs here."""
    model_config = ConfigDict(populate_by_name=True)

    model: str
    system: str = ""
    # "schema" shadows a BaseModel attribute, so the field carries it as an alias
    schema_text: str = Field("", alias="schema")
    history: list[dict] = []
    question: str
    attempt: int = 0
    error: Optional[dict] = None
    prior_sql: Optional[str] = None


class SQLQuery(BaseModel):
    """The model's answer: one gated SELECT, or a reason to decline."""
    sql: Optional[str] = None
    decline: Optional[str] = None
    explanation: str = ""

    @field_validator("sql")
    @classmethod
    def gated(cls, v):
        # static_check returns the cleaned SQL (stripped, no trailing ';')
        return None if v is None else gate.static_check(v)

    @model_validator(mode="after")
    def exactly_one(self):
        if (self.sql is None) == (self.decline is None):
            raise ValueError("give exactly one of sql or decline")
        return self


class QueryResult(BaseModel):
    """The server's reply to run_query, as gate.run_query shapes it."""
    sql: str
    columns: list[str]
    rows: list[list[str | int | float | None]]
    row_count: int
    truncated: bool
    ms: float


def validate_query(d):
    """(SQLQuery, None) for a valid model reply; (None, {"code", "detail"})
    otherwise. The code is the gate's own (not_select, multiple_statements,
    not_authorized, ...) so the repair edge can tell the model what was
    wrong, or "invalid" for a shape error such as both fields set."""
    try:
        return SQLQuery.model_validate(d), None
    except ValidationError as e:
        return None, _error_info(e)


def _error_info(e: ValidationError):
    for item in e.errors():
        exc = (item.get("ctx") or {}).get("error")
        if isinstance(exc, gate.GateError):
            return {"code": exc.code, "detail": exc.detail}
    first = e.errors()[0]
    return {"code": "invalid", "detail": first.get("msg", str(e))}
