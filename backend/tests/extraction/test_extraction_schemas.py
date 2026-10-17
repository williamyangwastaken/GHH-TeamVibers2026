"""Keeps app/schemas.py in lockstep with the frozen api_contract.yaml."""

import json
import types
import typing
from enum import Enum
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from app import schemas

REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACT_PATH = REPO_ROOT / "api_contract.yaml"
FIXTURE_PATH = REPO_ROOT / "fixtures" / "synthetic_case.json"

yaml = pytest.importorskip("yaml")


def _contract_schemas() -> dict:
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    # Tolerate a stray markdown code fence (```yaml) wrapped around the spec.
    lines = [line for line in text.splitlines() if not line.lstrip().startswith("```")]
    return yaml.safe_load("\n".join(lines))["components"]["schemas"]


def _allows_none(annotation) -> bool:
    origin = typing.get_origin(annotation)
    if origin in (typing.Union, types.UnionType):
        return type(None) in typing.get_args(annotation)
    return False


CONTRACT = _contract_schemas()


@pytest.mark.parametrize("name", sorted(CONTRACT))
def test_every_contract_schema_has_a_matching_model(name):
    spec = CONTRACT[name]
    py = getattr(schemas, name, None)
    assert py is not None, f"app.schemas is missing {name}"

    if "enum" in spec:
        assert issubclass(py, Enum)
        assert [m.value for m in py] == spec["enum"]
        return

    assert issubclass(py, BaseModel)
    props = spec.get("properties", {})
    required = set(spec.get("required", []))
    fields = py.model_fields
    assert set(fields) == set(props), f"{name}: field names differ from contract"
    for field_name, field in fields.items():
        assert field.is_required() == (field_name in required), (
            f"{name}.{field_name}: required-ness differs from contract"
        )
        nullable = bool(props[field_name].get("nullable"))
        assert _allows_none(field.annotation) == nullable, (
            f"{name}.{field_name}: nullability differs from contract"
        )


def test_synthetic_fixture_round_trips_unchanged():
    raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    parsed = schemas.AnalysisResponse.model_validate(raw)
    assert json.loads(parsed.model_dump_json()) == raw


def test_contract_models_reject_unknown_fields():
    with pytest.raises(ValidationError):
        schemas.LetterRequest(case_id="c", finding_ids=["f"], intent="clarification", extra=1)


def test_contract_constraints_are_enforced():
    with pytest.raises(ValidationError):
        schemas.LetterRequest(case_id="c", finding_ids=[], intent="clarification")
    with pytest.raises(ValidationError):
        schemas.LineItem(id="li", description="x", page=0)
    with pytest.raises(ValidationError):
        schemas.DocumentSummary(
            id="d", kind="bill", filename="f.pdf", pages=0,
            extraction_quality="complete", line_items=[], extraction_warnings=[],
        )


def test_extraction_error_maps_to_error_response():
    err = schemas.ExtractionError(
        schemas.ErrorCode.FILE_TOO_LARGE, "Too big.", http_status=413, retryable=False
    )
    assert err.to_response().model_dump(mode="json") == {
        "error": {"code": "FILE_TOO_LARGE", "message": "Too big.", "retryable": False}
    }


def test_gemini_schema_has_no_defaults_so_every_key_is_emitted():
    for model in (schemas.ExtractedDocument, schemas.ExtractedLineItem):
        optional = [n for n, f in model.model_fields.items() if not f.is_required()]
        assert optional == [], f"{model.__name__} fields must be required-but-nullable"
