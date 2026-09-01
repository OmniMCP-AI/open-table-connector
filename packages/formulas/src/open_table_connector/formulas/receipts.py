"""Safe formula receipt details."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from open_table_connector.contract.errors import _safe_value

from .errors import _SAFE_DETAIL_KEYS, _is_unsafe_detail_value

_SCHEMA = "otc.formula-receipt-details/v1"
_TARGET_KINDS = {"grid", "field"}
_TABLE_MODES = {"sheet", "base"}
_FORBIDDEN_KEYS = {"expression", "formula", "value", "values", "credential", "token"}
_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _hash(value: object, field_name: str) -> str:
    text = _text(value, field_name)
    if _HASH_RE.fullmatch(text) is None:
        raise ValueError(f"{field_name} must be a lowercase sha256 identity")
    return text


def _optional_hash(value: object, field_name: str) -> str | None:
    return None if value is None else _hash(value, field_name)


def _optional_text(value: object, field_name: str) -> str | None:
    return None if value is None else _text(value, field_name)


def _optional_provider_receipt_ref(value: object) -> str | None:
    receipt_ref = _optional_text(value, "provider_receipt_ref")
    if receipt_ref is not None and ("http://" in receipt_ref.casefold() or "https://" in receipt_ref.casefold()):
        raise ValueError("provider_receipt_ref must not contain a URL")
    return receipt_ref


def _optional_count(value: object, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer when provided")
    return value


def _reject_forbidden_names(keys: object) -> None:
    names = {str(key).casefold() for key in keys}
    forbidden = sorted(names.intersection(_FORBIDDEN_KEYS))
    if forbidden:
        raise ValueError(f"forbidden receipt field names: {forbidden}")


def _reject_unsafe_strings(value: object) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            _reject_forbidden_names([str(key)])
            _reject_unsafe_strings(item)
        return
    if isinstance(value, list):
        for item in value:
            _reject_unsafe_strings(item)
        return
    if isinstance(value, str) and ("http://" in value.casefold() or "https://" in value.casefold()):
        raise ValueError("safe details must not contain URLs copied from expressions")


def _safe_details(value: Mapping[str, Any] | None) -> dict[str, Any]:
    details = _safe_value({} if value is None else value)
    _reject_unsafe_strings(details)
    _reject_forbidden_names(details.keys())
    return {
        key: item
        for key, item in details.items()
        if key.casefold() in _SAFE_DETAIL_KEYS
        and (item is None or isinstance(item, (str, int, float, bool)))
        and not _is_unsafe_detail_value(item)
    }


@dataclass(frozen=True, slots=True)
class FormulaReceiptDetails:
    target_kind: str
    table_mode: str
    target: str
    selector: str
    capability: str
    dialect: str
    expression_sha256: str | None = None
    observation_sha256: str | None = None
    value_observation_sha256: str | None = None
    affected_count: int | None = None
    observed_count: int | None = None
    copy_fill_policy: str | None = None
    calculation_state: str | None = None
    calculation_trigger: str | None = None
    dependency_scope: str | None = None
    revision_before: str | None = None
    revision_after: str | None = None
    mutation_atomicity: str | None = None
    revision_enforcement: str | None = None
    verification: str | None = None
    provider_receipt_ref: str | None = None
    safe_details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        target_kind = _text(self.target_kind, "target_kind")
        table_mode = _text(self.table_mode, "table_mode")
        if target_kind not in _TARGET_KINDS:
            raise ValueError("target_kind must be 'grid' or 'field'")
        if table_mode not in _TABLE_MODES:
            raise ValueError("table_mode must be 'sheet' or 'base'")
        if (target_kind == "grid") != (table_mode == "sheet"):
            raise ValueError("target_kind and table_mode must stay aligned")
        object.__setattr__(self, "target_kind", target_kind)
        object.__setattr__(self, "table_mode", table_mode)
        object.__setattr__(self, "target", _text(self.target, "target"))
        object.__setattr__(self, "selector", _text(self.selector, "selector"))
        object.__setattr__(self, "capability", _text(self.capability, "capability"))
        object.__setattr__(self, "dialect", _text(self.dialect, "dialect"))
        object.__setattr__(self, "expression_sha256", _optional_hash(self.expression_sha256, "expression_sha256"))
        object.__setattr__(self, "observation_sha256", _optional_hash(self.observation_sha256, "observation_sha256"))
        object.__setattr__(
            self, "value_observation_sha256", _optional_hash(self.value_observation_sha256, "value_observation_sha256")
        )
        object.__setattr__(self, "affected_count", _optional_count(self.affected_count, "affected_count"))
        object.__setattr__(self, "observed_count", _optional_count(self.observed_count, "observed_count"))
        object.__setattr__(self, "copy_fill_policy", _optional_text(self.copy_fill_policy, "copy_fill_policy"))
        object.__setattr__(self, "calculation_state", _optional_text(self.calculation_state, "calculation_state"))
        object.__setattr__(self, "calculation_trigger", _optional_text(self.calculation_trigger, "calculation_trigger"))
        object.__setattr__(self, "dependency_scope", _optional_text(self.dependency_scope, "dependency_scope"))
        object.__setattr__(self, "revision_before", _optional_hash(self.revision_before, "revision_before"))
        object.__setattr__(self, "revision_after", _optional_hash(self.revision_after, "revision_after"))
        object.__setattr__(self, "mutation_atomicity", _optional_text(self.mutation_atomicity, "mutation_atomicity"))
        object.__setattr__(
            self, "revision_enforcement", _optional_text(self.revision_enforcement, "revision_enforcement")
        )
        object.__setattr__(self, "verification", _optional_text(self.verification, "verification"))
        object.__setattr__(self, "provider_receipt_ref", _optional_provider_receipt_ref(self.provider_receipt_ref))
        object.__setattr__(self, "safe_details", _safe_details(self.safe_details))

        if self.affected_count is None and self.observed_count is None:
            raise ValueError("receipt must include affected_count or observed_count")
        if self.affected_count is not None and self.observed_count is not None:
            raise ValueError("receipt must not include both affected_count and observed_count")
        if self.value_observation_sha256 is not None:
            if self.calculation_state is None:
                raise ValueError("calculation_state is required for calculated-value receipts")
            if self.calculation_trigger is None:
                raise ValueError("calculation_trigger is required for calculated-value receipts")
            if self.dependency_scope != "provider_dynamic":
                raise ValueError("calculated-value receipts must declare dependency_scope=provider_dynamic")
        if self.capability.endswith(".set/1.0"):
            if self.expression_sha256 is None:
                raise ValueError("expression_sha256 is required for set receipts")
            if self.observation_sha256 is None:
                raise ValueError("observation_sha256 is required for set receipts")
            if self.verification == "passed":
                raise ValueError("set receipts must not make a calculated-value verification claim")
            if self.verification != "formula_text_readback":
                raise ValueError("set receipts require formula_text_readback verification")
        if self.copy_fill_policy is not None and self.copy_fill_policy != "top_left":
            raise ValueError("copy_fill_policy must be top_left when provided")

    @classmethod
    def for_grid_read(
        cls,
        *,
        target: str,
        selector: str,
        capability: str,
        dialect: str,
        observation_sha256: str,
        observed_count: int,
        revision_after: str | None,
    ) -> FormulaReceiptDetails:
        return cls(
            target_kind="grid",
            table_mode="sheet",
            target=target,
            selector=selector,
            capability=capability,
            dialect=dialect,
            observation_sha256=observation_sha256,
            observed_count=observed_count,
            revision_after=revision_after,
        )

    @classmethod
    def for_grid_set(
        cls,
        *,
        target: str,
        selector: str,
        capability: str,
        dialect: str,
        expression_sha256: str,
        observation_sha256: str,
        affected_count: int,
        revision_before: str | None,
        revision_after: str,
        mutation_atomicity: str,
        revision_enforcement: str,
        verification: str,
    ) -> FormulaReceiptDetails:
        return cls(
            target_kind="grid",
            table_mode="sheet",
            target=target,
            selector=selector,
            capability=capability,
            dialect=dialect,
            expression_sha256=expression_sha256,
            observation_sha256=observation_sha256,
            affected_count=affected_count,
            copy_fill_policy="top_left",
            revision_before=revision_before,
            revision_after=revision_after,
            mutation_atomicity=mutation_atomicity,
            revision_enforcement=revision_enforcement,
            verification=verification,
        )

    @classmethod
    def for_field_set(
        cls,
        *,
        target: str,
        selector: str,
        capability: str,
        dialect: str,
        expression_sha256: str,
        observation_sha256: str,
        affected_count: int,
        revision_before: str | None,
        revision_after: str,
        mutation_atomicity: str,
        revision_enforcement: str,
        verification: str,
    ) -> FormulaReceiptDetails:
        return cls(
            target_kind="field",
            table_mode="base",
            target=target,
            selector=selector,
            capability=capability,
            dialect=dialect,
            expression_sha256=expression_sha256,
            observation_sha256=observation_sha256,
            affected_count=affected_count,
            revision_before=revision_before,
            revision_after=revision_after,
            mutation_atomicity=mutation_atomicity,
            revision_enforcement=revision_enforcement,
            verification=verification,
        )

    @classmethod
    def for_grid_values_read(
        cls,
        *,
        target: str,
        selector: str,
        capability: str,
        dialect: str,
        observation_sha256: str,
        value_observation_sha256: str,
        observed_count: int,
        revision_after: str | None,
        calculation_state: str | None,
        calculation_trigger: str | None,
        dependency_scope: str | None,
    ) -> FormulaReceiptDetails:
        return cls(
            target_kind="grid",
            table_mode="sheet",
            target=target,
            selector=selector,
            capability=capability,
            dialect=dialect,
            observation_sha256=observation_sha256,
            value_observation_sha256=value_observation_sha256,
            observed_count=observed_count,
            revision_after=revision_after,
            calculation_state=calculation_state,
            calculation_trigger=calculation_trigger,
            dependency_scope=dependency_scope,
        )

    @classmethod
    def for_field_values_read(
        cls,
        *,
        target: str,
        selector: str,
        capability: str,
        dialect: str,
        observation_sha256: str,
        value_observation_sha256: str,
        observed_count: int,
        revision_after: str | None,
        calculation_state: str | None,
        calculation_trigger: str | None,
        dependency_scope: str | None,
    ) -> FormulaReceiptDetails:
        return cls(
            target_kind="field",
            table_mode="base",
            target=target,
            selector=selector,
            capability=capability,
            dialect=dialect,
            observation_sha256=observation_sha256,
            value_observation_sha256=value_observation_sha256,
            observed_count=observed_count,
            revision_after=revision_after,
            calculation_state=calculation_state,
            calculation_trigger=calculation_trigger,
            dependency_scope=dependency_scope,
        )

    def to_wire(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema": _SCHEMA,
            "target_kind": self.target_kind,
            "table_mode": self.table_mode,
            "target": self.target,
            "selector": self.selector,
            "capability": self.capability,
            "dialect": self.dialect,
        }
        for key in (
            "observation_sha256",
            "value_observation_sha256",
            "affected_count",
            "observed_count",
            "copy_fill_policy",
            "calculation_state",
            "calculation_trigger",
            "dependency_scope",
            "revision_before",
            "revision_after",
            "mutation_atomicity",
            "revision_enforcement",
            "verification",
            "provider_receipt_ref",
        ):
            value = getattr(self, key)
            if value is not None:
                payload[key] = value
        if self.expression_sha256 is not None:
            payload["input_sha256"] = self.expression_sha256
        if self.safe_details:
            payload["safe_details"] = dict(self.safe_details)
        return payload

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> FormulaReceiptDetails:
        _reject_forbidden_names(payload.keys())
        if payload.get("schema") != _SCHEMA:
            raise ValueError("unsupported formula receipt schema")
        allowed = {
            "schema",
            "target_kind",
            "table_mode",
            "target",
            "selector",
            "capability",
            "dialect",
            "input_sha256",
            "observation_sha256",
            "value_observation_sha256",
            "affected_count",
            "observed_count",
            "copy_fill_policy",
            "calculation_state",
            "calculation_trigger",
            "dependency_scope",
            "revision_before",
            "revision_after",
            "mutation_atomicity",
            "revision_enforcement",
            "verification",
            "provider_receipt_ref",
            "safe_details",
        }
        if set(payload) - allowed:
            raise ValueError("forbidden receipt fields are present")
        return cls(
            target_kind=payload["target_kind"],
            table_mode=payload["table_mode"],
            target=payload["target"],
            selector=payload["selector"],
            capability=payload["capability"],
            dialect=payload["dialect"],
            expression_sha256=payload.get("input_sha256"),
            observation_sha256=payload.get("observation_sha256"),
            value_observation_sha256=payload.get("value_observation_sha256"),
            affected_count=payload.get("affected_count"),
            observed_count=payload.get("observed_count"),
            copy_fill_policy=payload.get("copy_fill_policy"),
            calculation_state=payload.get("calculation_state"),
            calculation_trigger=payload.get("calculation_trigger"),
            dependency_scope=payload.get("dependency_scope"),
            revision_before=payload.get("revision_before"),
            revision_after=payload.get("revision_after"),
            mutation_atomicity=payload.get("mutation_atomicity"),
            revision_enforcement=payload.get("revision_enforcement"),
            verification=payload.get("verification"),
            provider_receipt_ref=payload.get("provider_receipt_ref"),
            safe_details=payload.get("safe_details", {}),
        )


__all__ = ["FormulaReceiptDetails"]
