"""Part 1 unit tests: the refusals the brief names, plus the happy paths.

    pytest -q tests/test_contract.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from agent.contract import (ColumnInfo, SchemaCatalog, SQLQuery,  # noqa: E402
                            QueryRequest, QueryResult, validate_query)


def _refused(d, code):
    model, err = validate_query(d)
    assert model is None, f"not refused: {d}"
    assert err["code"] == code, (d, err)
    assert err["detail"]


def test_valid_select_is_cleaned():
    model, err = validate_query({"sql": "SELECT bdc FROM holdings_v;",
                                 "explanation": "names"})
    assert err is None
    assert model.sql == "SELECT bdc FROM holdings_v"   # ';' stripped by the gate
    assert model.decline is None


def test_decline_without_sql_is_valid():
    model, err = validate_query({"sql": None, "decline": "not in the data"})
    assert err is None and model.decline == "not in the data"


def test_delete_is_refused():
    _refused({"sql": "DELETE FROM holdings"}, "not_select")


def test_two_statements_are_refused():
    _refused({"sql": "SELECT 1; DROP TABLE holdings"}, "multiple_statements")


def test_sqlite_master_is_refused():
    _refused({"sql": "SELECT * FROM sqlite_master"}, "not_authorized")


def test_both_fields_set_is_refused():
    _refused({"sql": "SELECT 1", "decline": "no"}, "invalid")


def test_neither_field_set_is_refused():
    _refused({"sql": None, "decline": None}, "invalid")


def test_schema_catalog_renders_for_the_prompt():
    cat = SchemaCatalog(tables={"holdings_v": [
        ColumnInfo(column="bdc", description="BDC name"),
        ColumnInfo(column="price")]})
    assert cat.render() == "holdings_v(bdc: BDC name, price)"


def test_query_request_accepts_build_request_dict():
    r = QueryRequest.model_validate({"model": "m", "system": "s", "schema": "t(c)",
                                     "history": [], "question": "q", "attempt": 0,
                                     "error": None, "prior_sql": None})
    assert r.schema_text == "t(c)" and r.question == "q"


def test_query_result_matches_gate_shape():
    r = QueryResult(sql="SELECT 1", columns=["1"], rows=[[1]],
                    row_count=1, truncated=False, ms=0.3)
    assert r.rows == [[1]] and not r.truncated
