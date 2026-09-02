from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

import open_table_connector.formulas as otf
import pytest
from open_table_connector.contract import ConnectorError, ConnectorErrorCode, TableMode, TableURI
from open_table_connector.feishu_bitable import (
    FEISHU_FORMULA_FIELD_TYPE,
    FeishuBitableConnector,
    FeishuBitableFieldFormulaExtension,
)

HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64


@dataclass
class BoundTable:
    _binding: Any


def table() -> BoundTable:
    return BoundTable(
        type(
            "Binding",
            (),
            {"uri": TableURI("feishu://app-token/table-id"), "mode": TableMode.BASE},
        )()
    )


def field_doc(
    *,
    expression: str = "price - cost",
    field_id: str = "fld-margin",
    field_name: str = "gross_margin",
    field_type: int = FEISHU_FORMULA_FIELD_TYPE,
) -> dict[str, Any]:
    return {
        "field_id": field_id,
        "field_name": field_name,
        "type": field_type,
        "property": {
            "formula_expression": expression,
            "formatter": "0.00",
            "auto_fill": True,
        },
        "description": "kept unchanged",
    }


class RecordingTransport:
    def __init__(self, fields: list[dict[str, Any]] | None = None) -> None:
        self.fields = copy.deepcopy(fields or [field_doc()])
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []
        self.page_calls = 0
        self.fail_next_put: Exception | None = None
        self.records: list[dict[str, Any]] = []
        self.record_pages: list[dict[str, Any]] = []

    def request(self, method, url, *, headers, body=None, timeout=None):
        del headers, timeout
        self.calls.append((method, url, body))
        if "/fields" in url and method == "GET":
            self.page_calls += 1
            if "page_token=next" in url:
                return {"code": 0, "data": {"items": self.fields[1:], "has_more": False}}
            return {
                "code": 0,
                "data": {
                    "items": self.fields[:1],
                    "has_more": len(self.fields) > 1,
                    "page_token": "next" if len(self.fields) > 1 else None,
                },
            }
        if "/fields/" in url and method == "PUT":
            if self.fail_next_put is not None:
                error, self.fail_next_put = self.fail_next_put, None
                raise error
            field_id = url.rsplit("/", 1)[-1]
            existing = next(field for field in self.fields if field["field_id"] == field_id)
            replacement = copy.deepcopy(existing)
            replacement.update(copy.deepcopy(body))
            replacement["field_id"] = field_id
            for index, existing in enumerate(self.fields):
                if existing["field_id"] == field_id:
                    self.fields[index] = replacement
                    break
            return {"code": 0, "data": {"field": replacement}}
        if "/records" in url and method == "GET":
            token = "page_token=next" in url
            page = self.record_pages[1 if token else 0]
            return page
        raise AssertionError(f"unexpected request: {method} {url}")


class ResponseCodeTransport(RecordingTransport):
    def __init__(self, code: object, *, omit_code: bool = False) -> None:
        super().__init__()
        self.response_code = code
        self.omit_code = omit_code

    def request(self, method, url, *, headers, body=None, timeout=None):
        payload = super().request(method, url, headers=headers, body=body, timeout=timeout)
        if self.omit_code:
            payload.pop("code", None)
        else:
            payload["code"] = self.response_code
        return payload


class EvidenceReadbackTransport(RecordingTransport):
    def __init__(self) -> None:
        super().__init__()
        self.add_evidence = False

    def request(self, method, url, *, headers, body=None, timeout=None):
        payload = super().request(method, url, headers=headers, body=body, timeout=timeout)
        if method == "PUT":
            self.add_evidence = True
        if method == "GET" and "/fields" in url and self.add_evidence:
            for item in payload["data"]["items"]:
                item["provider_revision"] = HASH_B
                item["provider_evidence"] = {"status": "verified"}
        return payload


class UnrelatedReadbackTransport(EvidenceReadbackTransport):
    def request(self, method, url, *, headers, body=None, timeout=None):
        payload = super().request(method, url, headers=headers, body=body, timeout=timeout)
        if method == "GET" and "/fields" in url and self.add_evidence:
            for item in payload["data"]["items"]:
                item["description"] = "provider changed an unrelated property"
        return payload


def bind(extension: FeishuBitableFieldFormulaExtension):
    result = extension.bind_field(
        otf.FieldFormulaBindRequest(
            otf.FieldFormulaTarget(table(), otf.FieldRef(name="gross_margin"))
        )
    )
    assert result.outcome is otf.FormulaOutcome.SUCCEEDED
    assert result.value is not None
    return result.value


def test_bind_follows_field_pages_and_binds_stable_id_without_leaks() -> None:
    transport = RecordingTransport([field_doc(), field_doc(field_id="fld-other", field_name="other")])
    extension = FeishuBitableFieldFormulaExtension(
        FeishuBitableConnector(transport, tenant_access_token="tenant-secret", timeout=11)
    )

    binding = bind(extension)

    assert binding.target.field == otf.FieldRef(field_id="fld-margin")
    assert binding.capabilities.details.dialects == (otf.FEISHU_BITABLE,)
    assert binding.capabilities.details.max_expression_bytes == 64 * 1024
    assert binding.capabilities.details.max_cells_per_operation is None
    assert binding.capabilities.details.recalculation_scopes == ()
    assert binding.capabilities.details.idempotency_strength is otf.IdempotencyStrength.RECONCILED
    assert binding.observed_revision.startswith("sha256:")
    assert "tenant-secret" not in repr(binding)
    assert "app-token" not in repr(binding.capabilities.details)
    assert transport.page_calls == 2


@pytest.mark.parametrize(
    ("fields", "selector", "code"),
    [
        ([field_doc(field_name="same"), field_doc(field_id="fld-2", field_name="same")], otf.FieldRef(name="same"), otf.FormulaErrorCode.INVALID_TARGET),
        ([field_doc(field_id="")], otf.FieldRef(name="gross_margin"), otf.FormulaErrorCode.PROTOCOL_FAILURE),
        ([field_doc(field_type=1)], otf.FieldRef(name="gross_margin"), otf.FormulaErrorCode.INVALID_TARGET),
    ],
)
def test_bind_rejects_ambiguous_missing_or_non_formula_fields(fields, selector, code) -> None:
    transport = RecordingTransport(fields)
    extension = FeishuBitableFieldFormulaExtension(
        FeishuBitableConnector(transport, tenant_access_token="tenant-secret")
    )

    result = extension.bind_field(otf.FieldFormulaBindRequest(otf.FieldFormulaTarget(table(), selector)))

    assert result.error is not None
    assert result.error.code is code
    assert all("formula_expression" not in str(call) for call in transport.calls if call[0] == "PUT")


@pytest.mark.parametrize(
    ("code", "omit_code"),
    [(None, True), ("0", False), (True, False), (0.0, False)],
)
def test_all_feishu_responses_require_an_integer_status_code(code, omit_code) -> None:
    transport = ResponseCodeTransport(code, omit_code=omit_code)
    extension = FeishuBitableFieldFormulaExtension(
        FeishuBitableConnector(transport, tenant_access_token="tenant-secret")
    )

    result = extension.bind_field(otf.FieldFormulaBindRequest(otf.FieldFormulaTarget(table(), otf.FieldRef(name="gross_margin"))))

    assert result.outcome is otf.FormulaOutcome.FAILED
    assert result.error is not None
    assert result.error.code is otf.FormulaErrorCode.PROTOCOL_FAILURE


def test_read_field_uses_fresh_metadata_and_formula_observation() -> None:
    transport = RecordingTransport()
    extension = FeishuBitableFieldFormulaExtension(
        FeishuBitableConnector(transport, tenant_access_token="tenant-secret")
    )
    binding = bind(extension)

    transport.fields[0]["property"]["formula_expression"] = "ROUND(price - cost, 2)"
    result = extension.read_field(otf.FieldFormulaReadRequest(binding.target))

    assert result.outcome is otf.FormulaOutcome.SUCCEEDED
    assert result.value is not None
    assert result.value.expression == otf.FormulaExpression("ROUND(price - cost, 2)", otf.FEISHU_BITABLE)
    assert result.receipts
    assert "app-token" not in repr(result.receipts[0])


def test_set_sends_only_allowed_metadata_and_verifies_isolated_readback() -> None:
    transport = RecordingTransport()
    extension = FeishuBitableFieldFormulaExtension(
        FeishuBitableConnector(transport, tenant_access_token="tenant-secret")
    )
    binding = bind(extension)

    result = extension.set_field(
        otf.FieldFormulaSetRequest(
            binding.target,
            otf.FormulaExpression("ROUND(price - cost, 2)", otf.FEISHU_BITABLE),
            expected_revision=binding.observed_revision,
            idempotency_key="set-1",
        )
    )

    assert result.outcome is otf.FormulaOutcome.SUCCEEDED
    assert result.value is not None
    method, url, body = next(call for call in transport.calls if call[0] == "PUT")
    assert method == "PUT"
    assert url.endswith("/fields/fld-margin")
    assert set(body or {}) == {"field_name", "type", "property"}
    assert body["property"]["formula_expression"] == "ROUND(price - cost, 2)"
    assert result.value.formula_observation.expression.text == "ROUND(price - cost, 2)"


def test_set_allows_provider_safe_readback_evidence_without_leaking_formula_text() -> None:
    transport = EvidenceReadbackTransport()
    extension = FeishuBitableFieldFormulaExtension(
        FeishuBitableConnector(transport, tenant_access_token="tenant-secret")
    )
    binding = bind(extension)
    marker = "https://formula-secret.example/token"

    result = extension.set_field(
        otf.FieldFormulaSetRequest(
            binding.target,
            otf.FormulaExpression(marker, otf.FEISHU_BITABLE),
            expected_revision=binding.observed_revision,
        )
    )

    assert result.outcome is otf.FormulaOutcome.SUCCEEDED
    assert marker not in repr(result.error)
    assert marker not in repr(result.receipts)


def test_set_rejects_unrelated_readback_changes_without_leaking_formula_text() -> None:
    transport = UnrelatedReadbackTransport()
    extension = FeishuBitableFieldFormulaExtension(
        FeishuBitableConnector(transport, tenant_access_token="tenant-secret")
    )
    binding = bind(extension)
    marker = "https://formula-secret.example/token"

    result = extension.set_field(
        otf.FieldFormulaSetRequest(
            binding.target,
            otf.FormulaExpression(marker, otf.FEISHU_BITABLE),
            expected_revision=binding.observed_revision,
        )
    )

    assert result.outcome is otf.FormulaOutcome.FAILED
    assert result.error is not None
    assert result.error.code is otf.FormulaErrorCode.READBACK_MISMATCH
    assert marker not in repr(result.error)


def test_set_reconciles_lost_ack_without_resending() -> None:
    transport = RecordingTransport()
    extension = FeishuBitableFieldFormulaExtension(
        FeishuBitableConnector(transport, tenant_access_token="tenant-secret")
    )
    binding = bind(extension)
    transport.fail_next_put = ConnectorError(ConnectorErrorCode.TIMEOUT, "timed out", {})

    result = extension.set_field(
        otf.FieldFormulaSetRequest(
            binding.target,
            otf.FormulaExpression("ROUND(price - cost, 2)", otf.FEISHU_BITABLE),
            expected_revision=binding.observed_revision,
            idempotency_key="set-timeout",
        )
    )

    assert result.outcome is otf.FormulaOutcome.UNKNOWN
    assert result.error is not None
    assert result.error.code is otf.FormulaErrorCode.UNCERTAIN_MUTATION
    assert len([call for call in transport.calls if call[0] == "PUT"]) == 1


def test_read_field_values_follows_pages_and_preserves_provider_order() -> None:
    transport = RecordingTransport()
    transport.record_pages = [
        {"code": 0, "data": {"items": [{"record_id": "rec-1", "fields": {"fld-margin": 10}}], "has_more": True, "page_token": "next", "formula_calculation_state": "current"}},
        {"code": 0, "data": {"items": [{"record_id": "rec-2", "fields": {"fld-margin": None}}], "has_more": False, "formula_calculation_state": "current"}},
    ]
    extension = FeishuBitableFieldFormulaExtension(
        FeishuBitableConnector(transport, tenant_access_token="tenant-secret")
    )
    binding = bind(extension)

    result = extension.read_field_values(otf.FieldFormulaValueReadRequest(binding.target))

    assert result.outcome is otf.FormulaOutcome.SUCCEEDED
    assert result.value is not None
    assert [item.record_id for item in result.value.values] == ["rec-1", "rec-2"]
    assert [item.value.kind for item in result.value.values] == ["integer", "null"]
    assert result.value.calculation_state is otf.CalculationState.PROVIDER_CURRENT
    assert result.value.calculation_trigger is otf.CalculationTrigger.PROVIDER_READ
    assert result.value.dependency_scope == "provider_dynamic"


def test_read_field_values_rejects_missing_bound_field_value() -> None:
    transport = RecordingTransport()
    transport.record_pages = [
        {"code": 0, "data": {"items": [{"record_id": "rec-1", "fields": {}}], "has_more": False}}
    ]
    extension = FeishuBitableFieldFormulaExtension(
        FeishuBitableConnector(transport, tenant_access_token="tenant-secret")
    )
    binding = bind(extension)

    result = extension.read_field_values(otf.FieldFormulaValueReadRequest(binding.target))

    assert result.error is not None
    assert result.error.code is otf.FormulaErrorCode.PROTOCOL_FAILURE


def test_read_field_values_maps_formula_error_object_to_safe_contract_value() -> None:
    transport = RecordingTransport()
    transport.record_pages = [
        {
            "code": 0,
            "data": {
                "items": [{"record_id": "rec-1", "fields": {"fld-margin": {"type": "error", "value": "FORMULA_SECRET"}}}],
                "has_more": False,
            },
        }
    ]
    extension = FeishuBitableFieldFormulaExtension(
        FeishuBitableConnector(transport, tenant_access_token="tenant-secret")
    )
    binding = bind(extension)

    result = extension.read_field_values(otf.FieldFormulaValueReadRequest(binding.target))

    assert result.outcome is otf.FormulaOutcome.SUCCEEDED
    assert result.value is not None
    assert result.value.values[0].value.kind == "provider_error"
    assert result.value.values[0].value.value.code == otf.FormulaErrorCode.INVALID_FORMULA.value
    assert "FORMULA_SECRET" not in repr(result.value)


def test_read_field_values_rejects_unknown_provider_object() -> None:
    transport = RecordingTransport()
    transport.record_pages = [
        {
            "code": 0,
            "data": {
                "items": [{"record_id": "rec-1", "fields": {"fld-margin": {"type": "mystery", "value": "FORMULA_SECRET"}}}],
                "has_more": False,
            },
        }
    ]
    extension = FeishuBitableFieldFormulaExtension(
        FeishuBitableConnector(transport, tenant_access_token="tenant-secret")
    )
    binding = bind(extension)

    result = extension.read_field_values(otf.FieldFormulaValueReadRequest(binding.target))

    assert result.error is not None
    assert result.error.code is otf.FormulaErrorCode.PROTOCOL_FAILURE
    assert "FORMULA_SECRET" not in repr(result.error)


def test_read_field_values_rejects_duplicate_ids_and_unproven_current_state() -> None:
    transport = RecordingTransport()
    transport.record_pages = [
        {"code": 0, "data": {"items": [{"record_id": "rec-1", "fields": {"fld-margin": {"foo": "bar"}}}, {"record_id": "rec-1", "fields": {"fld-margin": 3}}], "has_more": False}}
    ]
    extension = FeishuBitableFieldFormulaExtension(
        FeishuBitableConnector(transport, tenant_access_token="tenant-secret")
    )
    binding = bind(extension)

    result = extension.read_field_values(otf.FieldFormulaValueReadRequest(binding.target))

    assert result.error is not None
    assert result.error.code is otf.FormulaErrorCode.PROTOCOL_FAILURE


def test_connector_and_cli_adapter_forward_formula_extension() -> None:
    connector = FeishuBitableConnector(RecordingTransport(), tenant_access_token="tenant-secret")
    extension = connector.formula_extension_for()

    assert isinstance(extension, otf.CompositeFormulaConnectorExtension)
    assert isinstance(extension.field, FeishuBitableFieldFormulaExtension)
