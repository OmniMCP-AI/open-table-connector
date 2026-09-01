from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterator, Mapping, Sequence
from copy import deepcopy
from pathlib import Path

import jsonschema
import pytest
from open_table_connector.formulas import (
    FormulaCapabilitySet,
    FormulaReceiptDetails,
    formula_observation_from_wire,
    formula_operation_from_wire,
)

ROOT = Path(__file__).parents[3]
SCHEMA_ROOT = ROOT / "specification" / "schemas"
FIXTURE_ROOT = ROOT / "specification" / "fixtures" / "formulas" / "v1"


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _object_paths(value: object, path: tuple[object, ...] = ()) -> Iterator[tuple[object, ...]]:
    if isinstance(value, Mapping):
        yield path
        for key, item in value.items():
            yield from _object_paths(item, (*path, key))
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            yield from _object_paths(item, (*path, index))


def _inject_unexpected(value: object, path: tuple[object, ...]) -> object:
    mutated = deepcopy(value)
    current = mutated
    for segment in path:
        current = current[segment]
    current["unexpected"] = True
    return mutated


def _is_path_closed_under_test(path: tuple[object, ...]) -> bool:
    return "entries" not in path


def _manifest_lines() -> list[str]:
    return (FIXTURE_ROOT / "manifest.sha256").read_text(encoding="utf-8").splitlines()


@pytest.mark.parametrize(
    ("fixture_name", "schema_name", "decoder"),
    [
        (
            "grid-sparse-observation.json",
            "formula-observation-v1.schema.json",
            formula_observation_from_wire,
        ),
        (
            "field-observation.json",
            "formula-observation-v1.schema.json",
            formula_observation_from_wire,
        ),
        (
            "value-observations.json",
            "formula-observation-v1.schema.json",
            formula_observation_from_wire,
        ),
        (
            "grid-copy-fill.json",
            "formula-operation-v1.schema.json",
            formula_operation_from_wire,
        ),
        (
            "capability-details.json",
            "formula-capability-details-v1.schema.json",
            FormulaCapabilitySet.from_wire,
        ),
        (
            "receipt-details.json",
            "formula-receipt-details-v1.schema.json",
            FormulaReceiptDetails.from_wire,
        ),
    ],
)
def test_formula_contract_fixtures_match_closed_schemas_and_python_codecs(
    fixture_name: str,
    schema_name: str,
    decoder: Callable[[Mapping[str, object]], object],
) -> None:
    fixture_path = FIXTURE_ROOT / fixture_name
    schema = _load_json(SCHEMA_ROOT / schema_name)
    fixture = _load_json(fixture_path)

    jsonschema.Draft202012Validator.check_schema(schema)
    validator = jsonschema.Draft202012Validator(schema)
    validator.validate(fixture)

    decoded = decoder(fixture)
    assert _canonical_json(decoded.to_wire()) == fixture_path.read_text(encoding="utf-8").strip()

    for path in _object_paths(fixture):
        if not _is_path_closed_under_test(path):
            continue
        mutated = _inject_unexpected(fixture, path)
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(mutated)


def test_formula_contract_manifest_uses_lexical_file_order_and_exact_hash_lines() -> None:
    fixture_files = sorted(
        path for path in FIXTURE_ROOT.glob("*.json") if path.name != "manifest.sha256"
    )
    expected_lines = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
        for path in fixture_files
    ]

    assert _manifest_lines() == expected_lines


def test_formula_contract_schemas_reject_unknown_versions_target_kinds_states_scopes_and_forbidden_receipt_fields() -> None:
    receipt_schema = _load_json(SCHEMA_ROOT / "formula-receipt-details-v1.schema.json")
    receipt = _load_json(FIXTURE_ROOT / "receipt-details.json")
    receipt["schema"] = "otc.formula-receipt-details/v2"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(receipt_schema).validate(receipt)

    capability_schema = _load_json(SCHEMA_ROOT / "formula-capability-details-v1.schema.json")
    capability = _load_json(FIXTURE_ROOT / "capability-details.json")
    capability["details"]["target_kind"] = "cell"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(capability_schema).validate(capability)

    capability = _load_json(FIXTURE_ROOT / "capability-details.json")
    capability["details"]["calculation_states"] = ["stale"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(capability_schema).validate(capability)

    capability = _load_json(FIXTURE_ROOT / "capability-details.json")
    capability["details"]["recalculation_scopes"] = ["sheet"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(capability_schema).validate(capability)

    capability = _load_json(FIXTURE_ROOT / "capability-details.json")
    capability["details"]["dialects"] = ["provider-x"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(capability_schema).validate(capability)

    receipt = _load_json(FIXTURE_ROOT / "receipt-details.json")
    receipt["values"] = [1, 2]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(receipt_schema).validate(receipt)


def test_formula_observation_schema_rejects_provider_error_variants_with_raw_payloads() -> None:
    schema = _load_json(SCHEMA_ROOT / "formula-observation-v1.schema.json")
    fixture = _load_json(FIXTURE_ROOT / "value-observations.json")
    fixture["values"][0]["value"] = {
        "kind": "provider_error",
        "error": {"code": "DIV0", "message": "#DIV/0!"},
    }

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(fixture)


def test_formula_receipt_schema_rejects_nested_safe_details_extra_keys_in_context() -> None:
    schema = _load_json(SCHEMA_ROOT / "formula-receipt-details-v1.schema.json")
    fixture = _load_json(FIXTURE_ROOT / "receipt-details.json")
    fixture["safe_details"] = {"provider_status": {"state": "committed"}}

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(fixture)


def test_formula_mapping_schema_rejects_nested_entry_extra_keys_in_context() -> None:
    schema = _load_json(SCHEMA_ROOT / "formula-observation-v1.schema.json")
    fixture = _load_json(FIXTURE_ROOT / "value-observations.json")
    fixture["values"][1]["value"]["entries"]["amount"]["unexpected"] = True

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(fixture)
