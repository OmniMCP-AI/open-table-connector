from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from unittest.mock import patch

import pytest

from open_connectors.contract import ConnectorError, ConnectorErrorCode
from open_connectors.dbt import (
    DbtCompileRequest,
    DbtConnector,
    DbtPreparedOperation,
    DbtRunResult,
)

from specification.conformance.universal.cases import ConnectorCase, cases_with
from specification.conformance.universal.fixtures import RecordingDbtRunner


_FIXTURE_CREDENTIALS = {
    "password": "fixture-dbt-password",
    "token": "fixture-dbt-token",
}


def _dbt_case() -> ConnectorCase:
    matches = cases_with("dbt.compile")
    assert [item.name for item in matches] == ["dbt"]
    return matches[0]


def _compile_request(
    project_dir: Path,
    *,
    select: tuple[str, ...] = (),
    exclude: tuple[str, ...] = (),
    target: str | None = None,
    vars: dict[str, object] | None = None,
) -> DbtCompileRequest:
    return DbtCompileRequest(
        project_dir=project_dir,
        select=select,
        exclude=exclude,
        target=target,
        vars={} if vars is None else vars,
    )


def _prepared_operation(connector_case: ConnectorCase) -> DbtPreparedOperation:
    operation = connector_case.capability_binding("dbt.compile").invoke()
    assert isinstance(operation, DbtPreparedOperation)
    return operation


def test_dbt_compile_constructs_exact_argv_and_records_project_directory() -> None:
    connector_case = _dbt_case()
    fixture = connector_case.dbt_fixture
    assert fixture is not None

    operation = connector_case.connector.compile(
        _compile_request(fixture.project_dir)
    )

    expected_argv = (
        "dbt",
        "compile",
        "--project-dir",
        str(fixture.project_dir),
    )
    assert operation.argv == expected_argv
    assert fixture.runner.calls == [
        fixture.recorded_call(expected_argv),
    ]


def test_dbt_compile_propagates_select_exclude_target_and_vars_to_both_commands() -> None:
    connector_case = _dbt_case()
    fixture = connector_case.dbt_fixture
    assert fixture is not None
    request = _compile_request(
        fixture.project_dir,
        select=("model.fixture.orders", "tag:daily"),
        exclude=("tag:slow", "model.fixture.refunds"),
        target="fixture",
        vars={"currency": "USD", "window_days": 7},
    )

    operation = connector_case.connector.compile(request)

    option_argv = (
        "--project-dir",
        str(fixture.project_dir),
        "--select",
        "model.fixture.orders",
        "tag:daily",
        "--exclude",
        "tag:slow",
        "model.fixture.refunds",
        "--target",
        "fixture",
        "--vars",
        '{"currency":"USD","window_days":7}',
    )
    assert operation.argv == ("dbt", "compile", *option_argv)
    assert operation.run_argv == ("dbt", "run", *option_argv)
    assert fixture.runner.calls[-1] == fixture.recorded_call(operation.argv)


def test_dbt_compile_repeated_invocations_have_deterministic_identity() -> None:
    connector_case = _dbt_case()
    fixture = connector_case.dbt_fixture
    assert fixture is not None
    request = _compile_request(
        fixture.project_dir,
        select=("model.fixture.orders",),
        target="fixture",
        vars={"currency": "USD"},
    )

    first = connector_case.connector.compile(request)
    second = connector_case.connector.compile(request)

    assert first.invocation_id == second.invocation_id
    assert first.invocation_id.startswith("dbt_")
    assert len(first.invocation_id) == 28
    assert [call.argv for call in fixture.runner.calls] == [first.argv, first.argv]
    assert all(call.project_dir == fixture.project_dir for call in fixture.runner.calls)


def test_dbt_compile_repeated_invocations_have_deterministic_artifact_hash() -> None:
    connector_case = _dbt_case()
    fixture = connector_case.dbt_fixture
    assert fixture is not None
    request = _compile_request(fixture.project_dir)

    first = connector_case.connector.compile(request)
    second = connector_case.connector.compile(request)

    assert first.compiled_artifacts == second.compiled_artifacts == {
        "manifest.json": b'{"nodes":{"model.fixture.orders":{}}}',
    }
    assert first.artifact_hash == second.artifact_hash == (
        "681fa7b1d3c62ef61289d1f99a7c6690c739230cff716c2730bf236afcaeb184"
    )


def test_dbt_run_maps_status_results_refs_and_exact_invocation() -> None:
    connector_case = _dbt_case()
    fixture = connector_case.dbt_fixture
    assert fixture is not None
    operation = _prepared_operation(connector_case)

    result = connector_case.capability_binding("dbt.run").invoke()

    assert isinstance(result, DbtRunResult)
    assert result.status == "success"
    assert result.run_results == b'{"results":[]}'
    assert result.artifact_refs == {"run_results.json": "run_results.json"}
    run_call = fixture.runner.calls[-1]
    assert run_call.argv == operation.run_argv
    assert run_call.project_dir == fixture.project_dir


def test_dbt_repeated_runs_return_deterministic_results_and_recordings() -> None:
    connector_case = _dbt_case()
    fixture = connector_case.dbt_fixture
    assert fixture is not None
    operation = _prepared_operation(connector_case)

    first = connector_case.connector.run(operation)
    second = connector_case.connector.run(operation)

    assert first == second == DbtRunResult(
        invocation_id=operation.invocation_id,
        status="success",
        run_results=b'{"results":[]}',
        artifact_refs={"run_results.json": "run_results.json"},
    )
    assert fixture.runner.calls[-2:] == [
        fixture.recorded_call(operation.run_argv),
        fixture.recorded_call(operation.run_argv),
    ]


def test_dbt_cancel_maps_cancelled_status_results_and_exact_invocation() -> None:
    connector_case = _dbt_case()
    fixture = connector_case.dbt_fixture
    assert fixture is not None
    operation = _prepared_operation(connector_case)

    result = connector_case.connector.cancel(operation)

    assert result == DbtRunResult(
        invocation_id=operation.invocation_id,
        status="cancelled",
        run_results=b'{"status":"cancelled"}',
    )
    assert fixture.runner.calls[-1] == fixture.recorded_call(
        ("dbt", "cancel", "--invocation-id", operation.invocation_id)
    )


def test_dbt_artifact_lookup_returns_owned_bytes_and_maps_missing_names() -> None:
    connector_case = _dbt_case()
    operation = _prepared_operation(connector_case)

    artifact = connector_case.capability_binding("dbt.artifact.read").invoke()

    assert artifact == b'{"nodes":{"model.fixture.orders":{}}}'
    with pytest.raises(ConnectorError) as raised:
        connector_case.connector.read_artifact(operation, "catalog.json")
    assert raised.value.code is ConnectorErrorCode.INVALID_URI
    assert raised.value.message == "dbt artifact is unavailable"
    assert raised.value.safe_details == {"artifact": "catalog.json"}


def test_dbt_readback_returns_runner_owned_physical_facts() -> None:
    connector_case = _dbt_case()
    fixture = connector_case.dbt_fixture
    assert fixture is not None
    operation = _prepared_operation(connector_case)

    facts = connector_case.connector.readback(operation, "analytics.orders")

    assert facts == {
        "relation": "analytics.orders",
        "database": "fixture_warehouse",
        "schema": "analytics",
        "identifier": "orders",
        "row_count": 2,
    }
    assert fixture.runner.readback_relations == ["analytics.orders"]


def test_dbt_unsupported_runner_maps_run_and_cancel_without_launching_commands() -> None:
    connector_case = _dbt_case()
    fixture = connector_case.dbt_fixture
    assert fixture is not None
    connector = DbtConnector()

    with patch.object(subprocess, "run") as run, patch.object(subprocess, "Popen") as popen:
        operation = connector.compile(_compile_request(fixture.project_dir))
        with pytest.raises(ConnectorError) as run_error:
            connector.run(operation)
        with pytest.raises(ConnectorError) as cancel_error:
            connector.cancel(operation)

    assert run_error.value.to_wire() == {
        "code": "unsupported_capability",
        "message": "dbt execution runner is not configured",
        "safe_details": {},
    }
    assert cancel_error.value.to_wire() == {
        "code": "unsupported_capability",
        "message": "dbt cancellation runner is not configured",
        "safe_details": {},
    }
    run.assert_not_called()
    popen.assert_not_called()


@pytest.mark.parametrize(
    ("operation_name", "expected_code", "expected_message"),
    (
        pytest.param(
            "compile",
            ConnectorErrorCode.EXECUTION_FAILED,
            "dbt compile failed",
            id="compile",
        ),
        pytest.param(
            "run",
            ConnectorErrorCode.EXECUTION_FAILED,
            "dbt run failed",
            id="run",
        ),
        pytest.param(
            "cancel",
            ConnectorErrorCode.CANCELLED,
            "dbt cancellation failed",
            id="cancel",
        ),
    ),
)
def test_dbt_runner_failures_map_to_stable_connector_errors(
    operation_name: str,
    expected_code: ConnectorErrorCode,
    expected_message: str,
) -> None:
    connector_case = _dbt_case()
    fixture = connector_case.dbt_fixture
    assert fixture is not None
    failure = RuntimeError(f"recorded {operation_name} rejection")
    runner = RecordingDbtRunner(
        failures={operation_name: failure},
        expected_project_dir=fixture.project_dir,
    )
    connector = DbtConnector(runner)

    if operation_name == "compile":
        invoke = lambda: connector.compile(_compile_request(fixture.project_dir))
    else:
        prepared = _prepared_operation(connector_case)
        invoke = lambda: getattr(connector, operation_name)(prepared)

    with pytest.raises(ConnectorError) as raised:
        invoke()

    assert raised.value.code is expected_code
    assert raised.value.message == expected_message
    assert raised.value.safe_details == {
        "reason": f"recorded {operation_name} rejection"
    }
    assert runner.calls[-1].project_dir == fixture.project_dir


def test_dbt_error_details_are_closed_json_safe_and_credential_free() -> None:
    connector_case = _dbt_case()
    fixture = connector_case.dbt_fixture
    assert fixture is not None
    runner = RecordingDbtRunner(
        failures={"compile": RuntimeError("recorded compile rejection")},
        credentials=_FIXTURE_CREDENTIALS,
        expected_project_dir=fixture.project_dir,
    )

    with pytest.raises(ConnectorError) as raised:
        DbtConnector(runner).compile(_compile_request(fixture.project_dir))

    wire = raised.value.to_wire()
    assert wire == {
        "code": "execution_failed",
        "message": "dbt compile failed",
        "safe_details": {"reason": "recorded compile rejection"},
    }
    serialized = json.dumps(wire, sort_keys=True)
    assert all(secret not in serialized for secret in _FIXTURE_CREDENTIALS.values())


def test_dbt_capability_bindings_use_only_the_recording_runner() -> None:
    connector_case = _dbt_case()
    fixture = connector_case.dbt_fixture
    assert fixture is not None

    with (
        patch.object(subprocess, "run") as run,
        patch.object(subprocess, "Popen") as popen,
        patch.object(os, "system") as system,
    ):
        compile_result = connector_case.capability_binding("dbt.compile").invoke()
        run_result = connector_case.capability_binding("dbt.run").invoke()
        cancel_result = connector_case.capability_binding("dbt.cancel").invoke()
        artifact = connector_case.capability_binding("dbt.artifact.read").invoke()

    assert isinstance(compile_result, DbtPreparedOperation)
    assert isinstance(run_result, DbtRunResult)
    assert isinstance(cancel_result, DbtRunResult)
    assert artifact == b'{"nodes":{"model.fixture.orders":{}}}'
    assert [call.argv[1] for call in fixture.runner.calls] == [
        "compile",
        "compile",
        "run",
        "compile",
        "cancel",
        "compile",
    ]
    assert all(call.project_dir == fixture.project_dir for call in fixture.runner.calls)
    run.assert_not_called()
    popen.assert_not_called()
    system.assert_not_called()


def test_dbt_credentials_are_excluded_from_argv_calls_and_metadata() -> None:
    connector_case = _dbt_case()
    fixture = connector_case.dbt_fixture
    assert fixture is not None
    assert fixture.runner.credentials == _FIXTURE_CREDENTIALS

    operation = _prepared_operation(connector_case)
    connector_case.capability_binding("dbt.run").invoke()

    observed = repr(
        {
            "compile_argv": operation.argv,
            "run_argv": operation.run_argv,
            "metadata": operation.metadata,
            "calls": fixture.runner.calls,
        }
    )
    assert all(secret not in observed for secret in _FIXTURE_CREDENTIALS.values())
    assert set(operation.metadata) == {"adapter_type", "artifacts"}
    assert operation.metadata["adapter_type"] == "fixture"


def test_dbt_temporary_project_contains_only_fixture_project_files() -> None:
    connector_case = _dbt_case()
    fixture = connector_case.dbt_fixture
    assert fixture is not None

    files = {
        path.relative_to(fixture.project_dir).as_posix(): path.read_text(encoding="utf-8")
        for path in fixture.project_dir.rglob("*")
        if path.is_file()
    }

    assert files == {
        "dbt_project.yml": (
            "name: fixture_project\n"
            "version: '1.0'\n"
            "profile: fixture\n"
            "config-version: 2\n"
        ),
        "models/orders.sql": "select 1 as id\n",
    }
