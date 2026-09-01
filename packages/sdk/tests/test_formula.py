from __future__ import annotations

from dataclasses import replace

import open_table_connector.formulas as otf
import open_table_connector.sdk as otc
import pytest
from open_table_connector.contract import ConnectorIdentity, TableURI

from .conftest import FakeLegacyAdapter, FakeSdkConnector, legacy_descriptor

HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64
HASH_C = "sha256:" + "c" * 64


def _grid_target(uri: str = "gridfake://warehouse/model") -> object:
    return otc.GridFormulaTarget(uri, otc.WorksheetRef(name="Model"))


def _grid_expression(
    text: str = '=HYPERLINK("https://secret.example", "x")',
    dialect: str = "google-sheets-a1",
) -> object:
    return otc.FormulaExpression(text=text, dialect=dialect)


def _grid_connector() -> FakeSdkConnector:
    return FakeSdkConnector(
        identity=ConnectorIdentity("gridfake", "0.1.0", "1.0"),
        schemes=("gridfake",),
        modes=(otc.TableMode.SHEET_MODE,),
        table_uri="gridfake://warehouse/model",
        open_mode=otc.TableMode.SHEET_MODE,
    )


def test_client_binds_grid_and_field_formula_views(fake_connector: FakeSdkConnector) -> None:
    grid_connector = _grid_connector()
    client = otc.Client(registry=otc.ConnectorRegistry([fake_connector, grid_connector]))

    grid = client.formulas(_grid_target()).require_value()
    table = client.open("fake://warehouse/orders").require_value()
    field = client.formulas(
        otc.FieldFormulaTarget(table, otc.FieldRef(name="gross_margin"))
    ).require_value()

    assert isinstance(grid, otc.GridFormulaView)
    assert isinstance(field, otc.FieldFormulaView)
    assert [name for name, _ in grid_connector.formula_extension.calls] == ["bind_grid"]
    assert [name for name, _ in fake_connector.formula_extension.calls] == ["bind_field"]


def test_sdk_exports_formula_values_but_not_provider_request_or_ledger_types() -> None:
    public_values = (
        "FieldFormulaTarget",
        "FormulaExpression",
        "FormulaValue",
        "FormulaResourceLimits",
        "GridFormulaTarget",
        "WorksheetRef",
    )
    provider_only = (
        "FormulaIdempotencyLedger",
        "FormulaReceiptDetails",
        "GridFormulaBindRequest",
        "GridFormulaSetRequest",
    )

    assert all(hasattr(otc, name) for name in public_values)
    assert all(not hasattr(otc, name) for name in provider_only)


def test_client_routes_grid_by_uri_and_field_by_bound_table_owner(
    fake_connector: FakeSdkConnector,
) -> None:
    grid_connector = _grid_connector()
    client = otc.Client(registry=otc.ConnectorRegistry([fake_connector, grid_connector]))

    grid_view = client.formulas(_grid_target()).require_value()
    table = client.open("fake://warehouse/orders").require_value()
    field_view = client.formulas(
        otc.FieldFormulaTarget(table, otc.FieldRef(name="gross_margin"))
    ).require_value()
    grid_view.read("A1").require_value()
    field_view.read().require_value()

    assert [name for name, _ in grid_connector.formula_extension.calls] == ["bind_grid", "read_grid"]
    assert [name for name, _ in fake_connector.formula_extension.calls] == ["bind_field", "read_field"]


def test_formula_views_normalize_all_eight_extension_operations(
    fake_connector: FakeSdkConnector,
) -> None:
    grid_connector = _grid_connector()
    client = otc.Client(registry=otc.ConnectorRegistry([fake_connector, grid_connector]))
    grid = client.formulas(_grid_target()).require_value()
    table = client.open("fake://warehouse/orders").require_value()
    field = client.formulas(
        otc.FieldFormulaTarget(table, otc.FieldRef(name="gross_margin"))
    ).require_value()

    assert isinstance(grid.read("A1").require_value(), otc.GridFormulaObservation)
    assert isinstance(grid.set("A1", _grid_expression()).require_value(), otc.FormulaMutation)
    assert isinstance(
        grid.read_values("A1").require_value(), otc.GridFormulaValueObservation
    )
    assert isinstance(
        grid.recalculate(scope=otc.GridRecalculationScope.RANGE, cell_range="A1").require_value(),
        otc.RecalculationObservation,
    )
    assert isinstance(field.read().require_value(), otc.FieldFormulaObservation)
    assert isinstance(
        field.set(otc.FormulaExpression("[Amount] * 2", otc.MAYBE_BASE)).require_value(),
        otc.FormulaMutation,
    )
    assert isinstance(field.read_values().require_value(), otc.FieldFormulaValueObservation)
    assert isinstance(
        field.recalculate(scope=otc.FieldRecalculationScope.FIELD).require_value(),
        otc.RecalculationObservation,
    )


def test_client_rejects_missing_formula_extension_without_table_io() -> None:
    connector = _grid_connector()
    connector.formula_extension_for = None  # type: ignore[method-assign]
    client = otc.Client(registry=otc.ConnectorRegistry([connector]))

    with pytest.raises(otc.OTCError) as raised:
        client.formulas(_grid_target())

    assert raised.value.result.error is not None
    assert raised.value.result.error.code is otc.ErrorCode.UNSUPPORTED_CAPABILITY
    assert connector.calls == []


def test_client_rejects_grid_targets_for_non_sheet_connectors_before_provider_io() -> None:
    connector = FakeSdkConnector(table_uri="fake://warehouse/model")
    client = otc.Client(registry=otc.ConnectorRegistry([connector]))

    with pytest.raises(otc.OTCError) as raised:
        client.formulas(
            otc.GridFormulaTarget("fake://warehouse/model", otc.WorksheetRef(name="Model"))
        )

    assert raised.value.result.error is not None
    assert raised.value.result.error.code is otc.ErrorCode.UNSUPPORTED_MODE
    assert connector.formula_extension.calls == []


def test_client_rejects_field_targets_for_sheet_mode_tables_before_provider_io() -> None:
    connector = FakeSdkConnector(
        modes=(otc.TableMode.SHEET_MODE,),
        open_mode=otc.TableMode.SHEET_MODE,
        table_uri="fake://warehouse/model",
    )
    client = otc.Client(registry=otc.ConnectorRegistry([connector]))
    table = client.open("fake://warehouse/model").require_value()

    with pytest.raises(otc.OTCError) as raised:
        client.formulas(otc.FieldFormulaTarget(table, otc.FieldRef(name="gross_margin")))

    assert raised.value.result.error is not None
    assert raised.value.result.error.code is otc.ErrorCode.UNSUPPORTED_MODE
    assert connector.formula_extension.calls == []


def test_client_rejects_foreign_field_targets_before_provider_io(
    fake_connector: FakeSdkConnector,
) -> None:
    owner = otc.Client(registry=otc.ConnectorRegistry([fake_connector]))
    foreign_table = owner.open("fake://warehouse/orders").require_value()
    other_connector = FakeSdkConnector(
        identity=ConnectorIdentity("other", "0.1.0", "1.0"),
        schemes=("other",),
        table_uri="other://warehouse/orders",
    )
    other = otc.Client(registry=otc.ConnectorRegistry([other_connector]))

    with pytest.raises(otc.OTCError) as raised:
        other.formulas(otc.FieldFormulaTarget(foreign_table, otc.FieldRef(name="gross_margin")))

    assert raised.value.result.error is not None
    assert raised.value.result.error.code is otc.ErrorCode.INVALID_TARGET
    assert other_connector.formula_extension.calls == []


def test_grid_binding_rejects_a_changed_caller_supplied_stable_worksheet_id() -> None:
    connector = _grid_connector()
    target = otc.GridFormulaTarget(
        "gridfake://warehouse/model",
        otc.WorksheetRef(worksheet_id="ws-requested"),
    )
    binding = connector.formula_extension._grid_binding(target)
    connector.formula_extension.overrides["bind_grid"] = otf.FormulaExtensionResult(
        value=replace(
            binding,
            target=otf.BoundGridFormulaTarget(
                grid="gridfake://warehouse/model",
                worksheet=otc.WorksheetRef(worksheet_id="ws-redirected"),
            ),
        ),
        outcome=otf.FormulaOutcome.SUCCEEDED,
        commit=otf.FormulaCommitState.NOT_APPLICABLE,
        verification=otf.FormulaVerificationState.PASSED,
        receipts=(),
    )
    client = otc.Client(registry=otc.ConnectorRegistry([connector]))

    with pytest.raises(otc.OTCError) as raised:
        client.formulas(target)

    assert raised.value.result.error is not None
    assert raised.value.result.error.code is otc.ErrorCode.PROTOCOL_FAILURE
    assert [name for name, _ in connector.formula_extension.calls] == ["bind_grid"]


def test_field_binding_rejects_a_changed_caller_supplied_stable_field_id(
    fake_connector: FakeSdkConnector,
) -> None:
    client = otc.Client(registry=otc.ConnectorRegistry([fake_connector]))
    table = client.open("fake://warehouse/orders").require_value()
    target = otc.FieldFormulaTarget(table, otc.FieldRef(field_id="fld-requested"))
    binding = fake_connector.formula_extension._field_binding(target)
    fake_connector.formula_extension.overrides["bind_field"] = otf.FormulaExtensionResult(
        value=replace(
            binding,
            target=replace(
                binding.target,
                field=otc.FieldRef(field_id="fld-redirected"),
            ),
        ),
        outcome=otf.FormulaOutcome.SUCCEEDED,
        commit=otf.FormulaCommitState.NOT_APPLICABLE,
        verification=otf.FormulaVerificationState.PASSED,
        receipts=(),
    )

    with pytest.raises(otc.OTCError) as raised:
        client.formulas(target)

    assert raised.value.result.error is not None
    assert raised.value.result.error.code is otc.ErrorCode.PROTOCOL_FAILURE
    assert [name for name, _ in fake_connector.formula_extension.calls] == ["bind_field"]


def test_formula_views_reject_use_after_client_close_before_provider_io() -> None:
    connector = _grid_connector()
    client = otc.Client(registry=otc.ConnectorRegistry([connector]))
    view = client.formulas(_grid_target()).require_value()
    client.close()

    with pytest.raises(otc.OTCError) as raised:
        view.read("A1")

    assert raised.value.result.error is not None
    assert raised.value.result.error.code is otc.ErrorCode.CLIENT_CLOSED
    assert [name for name, _ in connector.formula_extension.calls] == ["bind_grid"]


def test_formula_view_rejects_unsupported_methods_before_provider_io() -> None:
    connector = _grid_connector()
    connector.formula_extension.grid_capabilities = (otf.GRID_READ,)
    client = otc.Client(registry=otc.ConnectorRegistry([connector]))
    view = client.formulas(_grid_target()).require_value()

    with pytest.raises(otc.OTCError) as raised:
        view.set("A1", _grid_expression())

    assert raised.value.result.error is not None
    assert raised.value.result.error.code is otc.ErrorCode.UNSUPPORTED_CAPABILITY
    assert [name for name, _ in connector.formula_extension.calls] == ["bind_grid"]


def test_formula_view_rejects_unsupported_dialects_and_scopes_before_provider_io() -> None:
    connector = _grid_connector()
    connector.formula_extension.grid_details = replace(
        connector.formula_extension.grid_details,
        recalculation_scopes=(otf.GridRecalculationScope.WORKSHEET.value,),
    )
    client = otc.Client(registry=otc.ConnectorRegistry([connector]))
    view = client.formulas(_grid_target()).require_value()

    with pytest.raises(otc.OTCError) as dialect_error:
        view.set("A1", _grid_expression(dialect="excel-a1"))

    assert dialect_error.value.result.error is not None
    assert dialect_error.value.result.error.code is otc.ErrorCode.INVALID_FORMULA
    assert [name for name, _ in connector.formula_extension.calls] == ["bind_grid"]

    with pytest.raises(otc.OTCError) as scope_error:
        view.recalculate(scope=otc.GridRecalculationScope.RANGE, cell_range="A1")

    assert scope_error.value.result.error is not None
    assert scope_error.value.result.error.code is otc.ErrorCode.UNSUPPORTED_CAPABILITY
    assert [name for name, _ in connector.formula_extension.calls] == ["bind_grid"]


@pytest.mark.parametrize(
    ("override", "call", "outcome", "commit", "verification", "code"),
    [
        (
            otf.FormulaExtensionResult(
                value=None,
                outcome=otf.FormulaOutcome.REJECTED,
                commit=otf.FormulaCommitState.NOT_STARTED,
                verification=otf.FormulaVerificationState.SKIPPED,
                receipts=(),
                error=otf.FormulaExtensionErrorInfo(
                    code=otf.FormulaErrorCode.INVALID_FORMULA,
                    message="formula syntax was rejected",
                    safe_details={"dialect": "google-sheets-a1"},
                ),
            ),
            lambda view: view.set("A1", _grid_expression()),
            otc.Outcome.REJECTED,
            otc.CommitState.NOT_STARTED,
            otc.VerificationState.SKIPPED,
            "invalid_formula",
        ),
        (
            otf.FormulaExtensionResult(
                value=None,
                outcome=otf.FormulaOutcome.FAILED,
                commit=otf.FormulaCommitState.NOT_COMMITTED,
                verification=otf.FormulaVerificationState.SKIPPED,
                receipts=(),
                error=otf.FormulaExtensionErrorInfo(
                    code=otf.FormulaErrorCode.EXECUTION_FAILED,
                    message="provider refused the mutation",
                    safe_details={"provider_status_code": 400},
                ),
            ),
            lambda view: view.set("A1", _grid_expression()),
            otc.Outcome.FAILED,
            otc.CommitState.NOT_COMMITTED,
            otc.VerificationState.SKIPPED,
            "execution_failed",
        ),
        (
            otf.FormulaExtensionResult(
                value=otf.FormulaMutation(
                    target_kind="grid",
                    affected_count=1,
                    formula_observation=otf.GridFormulaObservation(
                        worksheet_id="ws-model",
                        requested_range="A1",
                        formulas=(otf.FormulaCell("A1", otf.FormulaExpression("=1", "google-sheets-a1")),),
                        observed_revision=HASH_A,
                    ),
                    revision_before=HASH_B,
                    revision_after=HASH_C,
                ),
                outcome=otf.FormulaOutcome.PARTIAL,
                commit=otf.FormulaCommitState.PARTIAL,
                verification=otf.FormulaVerificationState.FAILED,
                receipts=(),
                error=otf.FormulaExtensionErrorInfo(
                    code=otf.FormulaErrorCode.PARTIAL_EFFECT,
                    message="only part of the range updated",
                    safe_details={"affected_count": 1},
                ),
            ),
            lambda view: view.set(
                "A1",
                otc.FormulaExpression("=1", "google-sheets-a1"),
                expected_revision=view.observed_revision,
            ),
            otc.Outcome.PARTIAL,
            otc.CommitState.PARTIAL,
            otc.VerificationState.FAILED,
            "partial_effect",
        ),
        (
            otf.FormulaExtensionResult(
                value=None,
                outcome=otf.FormulaOutcome.UNKNOWN,
                commit=otf.FormulaCommitState.UNKNOWN,
                verification=otf.FormulaVerificationState.UNAVAILABLE,
                receipts=(),
                error=otf.FormulaExtensionErrorInfo(
                    code=otf.FormulaErrorCode.UNCERTAIN_MUTATION,
                    message="provider acknowledgement was lost",
                    safe_details={"provider_status_code": 503},
                ),
            ),
            lambda view: view.set("A1", _grid_expression()),
            otc.Outcome.UNKNOWN,
            otc.CommitState.UNKNOWN,
            otc.VerificationState.UNAVAILABLE,
            "uncertain_mutation",
        ),
    ],
)
def test_formula_results_normalize_formula_states_into_sdk_results(
    override: otf.FormulaExtensionResult[object],
    call,
    outcome: otc.Outcome,
    commit: otc.CommitState,
    verification: otc.VerificationState,
    code: str,
) -> None:
    connector = _grid_connector()
    connector.formula_extension.overrides["set_grid"] = override
    client = otc.Client(registry=otc.ConnectorRegistry([connector]))
    view = client.formulas(_grid_target()).require_value()

    with pytest.raises(otc.OTCError) as raised:
        call(view)

    assert raised.value.result.outcome is outcome
    assert raised.value.result.commit is commit
    assert raised.value.result.verification is verification
    assert raised.value.result.error is not None
    assert raised.value.result.error.code.value == code


def test_formula_result_receipts_use_sdk_envelopes_without_raw_expression_or_value_leakage() -> None:
    connector = _grid_connector()
    client = otc.Client(registry=otc.ConnectorRegistry([connector]))
    view = client.formulas(_grid_target()).require_value()
    expression = _grid_expression()

    result = view.set("A1", expression)
    mutation = result.require_value()
    request = connector.formula_extension.calls[-1][1]
    receipt = result.receipts[0]

    assert result.outcome is otc.Outcome.SUCCEEDED
    assert result.commit is otc.CommitState.COMMITTED
    assert result.verification is otc.VerificationState.PASSED
    assert mutation.formula_observation.formulas[0].expression.text == expression.text
    assert request.expected_revision is None
    assert receipt.kind == "formula"
    assert receipt.operation == "formula.grid.set/1.0"
    assert receipt.connector_id == "gridfake"
    assert receipt.safe_target == TableURI("gridfake://warehouse/model")
    assert receipt.mode is otc.TableMode.SHEET_MODE
    assert receipt.details["input_sha256"] == expression.sha256
    assert "expression" not in receipt.details
    assert "formula" not in receipt.details
    assert "value" not in receipt.details
    assert "https://secret.example" not in repr(receipt.details)


def test_malformed_formula_results_do_not_chain_sensitive_provider_values() -> None:
    secret_expression = '=HYPERLINK("https://secret.example", "token")'

    class MalformedResult:
        @property
        def value(self) -> object:
            raise ValueError(secret_expression)

    connector = _grid_connector()
    connector.formula_extension.overrides["read_grid"] = MalformedResult()  # type: ignore[assignment]
    client = otc.Client(registry=otc.ConnectorRegistry([connector]))
    view = client.formulas(_grid_target()).require_value()

    with pytest.raises(otc.OTCError) as raised:
        view.read("A1")

    assert raised.value.result.error is not None
    assert raised.value.result.error.code is otc.ErrorCode.PROTOCOL_FAILURE
    assert secret_expression not in str(raised.value)
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None


def test_provider_exceptions_become_unchained_safe_protocol_failures() -> None:
    secret = '=HYPERLINK("https://secret.example/?credential=token", "42")'
    connector = _grid_connector()
    client = otc.Client(registry=otc.ConnectorRegistry([connector]))
    view = client.formulas(_grid_target()).require_value()
    connector.formula_extension.failures["read_grid"] = RuntimeError(secret)

    with pytest.raises(otc.OTCError) as raised:
        view.read("A1")

    assert raised.value.result.error is not None
    assert raised.value.result.error.code is otc.ErrorCode.PROTOCOL_FAILURE
    rendered = str(raised.value) + repr(raised.value.result)
    for sensitive_part in ("HYPERLINK", "secret.example", "credential=token", '"42"'):
        assert sensitive_part not in rendered
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None


def test_provider_error_messages_are_not_copied_into_sdk_errors() -> None:
    secret = '=HYPERLINK("https://secret.example/?credential=token", "42")'
    connector = _grid_connector()
    connector.formula_extension.overrides["read_grid"] = otf.FormulaExtensionResult(
        value=None,
        outcome=otf.FormulaOutcome.REJECTED,
        commit=otf.FormulaCommitState.NOT_STARTED,
        verification=otf.FormulaVerificationState.SKIPPED,
        receipts=(),
        error=otf.FormulaExtensionErrorInfo(
            code=otf.FormulaErrorCode.INVALID_FORMULA,
            message=f"provider rejected {secret}",
        ),
    )
    client = otc.Client(registry=otc.ConnectorRegistry([connector]))
    view = client.formulas(_grid_target()).require_value()

    with pytest.raises(otc.OTCError) as raised:
        view.read("A1")

    assert raised.value.result.error is not None
    assert raised.value.result.error.code is otc.ErrorCode.INVALID_FORMULA
    rendered = (
        raised.value.result.error.message + str(raised.value) + repr(raised.value.result)
    )
    for sensitive_part in ("HYPERLINK", "secret.example", "credential=token", '"42"'):
        assert sensitive_part not in rendered


def test_client_formulas_uses_legacy_bridge_formula_forwarding() -> None:
    config = otc.ClientConfig.empty()
    client = otc.Client.from_config(
        config,
        descriptors=(legacy_descriptor(),),
        resolver=otc.EnvironmentCredentialResolver(config, {}),
    )
    table = client.open("legacy://warehouse/orders").require_value()

    view = client.formulas(
        otc.FieldFormulaTarget(table, otc.FieldRef(name="gross_margin"))
    ).require_value()
    observation = view.read().require_value()

    assert observation.table_uri == TableURI("legacy://warehouse/orders")
    assert observation.field_id == "fld-gross_margin"


def test_legacy_bridge_missing_formula_extension_is_an_unsupported_capability() -> None:
    adapter = FakeLegacyAdapter()
    adapter.formula_extension_for = None  # type: ignore[method-assign]
    bridge = otc.LegacyConnectorAdapterBridge(adapter)
    client = otc.Client(registry=otc.ConnectorRegistry([bridge]))
    table = client.open("legacy://warehouse/orders").require_value()

    with pytest.raises(otc.OTCError) as raised:
        client.formulas(otc.FieldFormulaTarget(table, otc.FieldRef(name="gross_margin")))

    assert raised.value.result.error is not None
    assert raised.value.result.error.code is otc.ErrorCode.UNSUPPORTED_CAPABILITY
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None


def test_legacy_bridge_invalid_formula_extension_is_a_safe_protocol_failure() -> None:
    adapter = FakeLegacyAdapter()
    adapter.formula_extension = object()  # type: ignore[assignment]
    bridge = otc.LegacyConnectorAdapterBridge(adapter)
    client = otc.Client(registry=otc.ConnectorRegistry([bridge]))
    table = client.open("legacy://warehouse/orders").require_value()

    with pytest.raises(otc.OTCError) as raised:
        client.formulas(otc.FieldFormulaTarget(table, otc.FieldRef(name="gross_margin")))

    assert raised.value.result.error is not None
    assert raised.value.result.error.code is otc.ErrorCode.PROTOCOL_FAILURE
    assert "TypeError" not in str(raised.value)
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None


@pytest.mark.parametrize(
    "limits",
    [
        otc.FormulaResourceLimits(max_cells=0),
        otc.FormulaResourceLimits(max_records=-1),
        otc.FormulaResourceLimits(max_response_bytes=True),
        otc.FormulaResourceLimits(max_cells=1.5),  # type: ignore[arg-type]
        otc.FormulaResourceLimits(timeout_seconds=False),
        otc.FormulaResourceLimits(timeout_seconds=float("nan")),
        otc.FormulaResourceLimits(timeout_seconds=float("inf")),
    ],
)
def test_formula_views_reject_invalid_resource_limits_before_provider_io(
    limits: otc.FormulaResourceLimits,
) -> None:
    connector = _grid_connector()
    client = otc.Client(registry=otc.ConnectorRegistry([connector]))
    view = client.formulas(_grid_target()).require_value()

    with pytest.raises(otc.OTCError) as raised:
        view.read("A1", limits=limits)

    assert raised.value.result.error is not None
    assert raised.value.result.error.code is otc.ErrorCode.RESOURCE_LIMIT
    assert [name for name, _ in connector.formula_extension.calls] == ["bind_grid"]


def test_grid_range_exceeding_caller_max_cells_is_rejected_before_provider_io() -> None:
    connector = _grid_connector()
    client = otc.Client(registry=otc.ConnectorRegistry([connector]))
    view = client.formulas(_grid_target()).require_value()

    with pytest.raises(otc.OTCError) as raised:
        view.read("A1:B2", limits=otc.FormulaResourceLimits(max_cells=2))

    assert raised.value.result.error is not None
    assert raised.value.result.error.code is otc.ErrorCode.RESOURCE_LIMIT
    assert [name for name, _ in connector.formula_extension.calls] == ["bind_grid"]
