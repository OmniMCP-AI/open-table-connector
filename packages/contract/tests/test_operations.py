import pytest

from open_table_connector.contract.operations import (
    CapabilityObservation,
    ExecutionOptions,
    OperationDescriptor,
    OperationRequest,
    TargetSelector,
)


def test_operation_request_roundtrip_is_closed_and_immutable():
    descriptor = OperationDescriptor(
        schema="otc.operation/1.0",
        operation_id="range.write",
        version="1.0",
        target_kind="range",
        arguments_schema={"type": "object", "properties": {"values": {"type": "array"}}},
        capability="spreadsheet.range.write/1.0",
        effects=("buffered_write",),
    )
    request = OperationRequest(
        namespace="spreadsheet",
        operation_id="range.write",
        version="1.0",
        target=TargetSelector(uri="file:///tmp/report.xlsx", sheet="Report"),
        arguments={"values": [[None, False, 0, ""]]},
    )
    observation = CapabilityObservation(
        target=request.target,
        provider="local-files",
        provider_version="0.1.0",
        resolution="static",
        operations=(descriptor,),
    )
    assert OperationDescriptor.from_wire(descriptor.to_wire()) == descriptor
    assert OperationRequest.from_wire(request.to_wire()) == request
    assert CapabilityObservation.from_wire(observation.to_wire()) == observation
    with pytest.raises(TypeError):
        request.arguments["new"] = True
    with pytest.raises(ValueError):
        OperationDescriptor.from_wire({**descriptor.to_wire(), "unexpected": True})


def test_execution_options_roundtrip_preserves_explicit_false_and_zero():
    options = ExecutionOptions(
        dry_run=False,
        allow_partial=False,
        expected_revision="",
        idempotency_key=None,
    )
    assert ExecutionOptions.from_wire(options.to_wire()) == options
