from __future__ import annotations

import json
import os
import subprocess
import sys
from io import BytesIO
from pathlib import Path

from open_table_connector.local_files import encode_json_table
from open_table_connector.process import ConnectorProcessEnvelope, ProcessOperation
from open_table_connector.process.framing import read_frame, write_frame

from packages.local_files.tests.test_temporal_csv import operations
from packages.timeseries.tests.fixtures import descriptor, ticks_table


def test_configured_json_executable_completes_hello_and_execute(tmp_path: Path) -> None:
    source = tmp_path / "ticks.json"
    source.write_text(encode_json_table(ticks_table()), encoding="utf-8")
    target = f"json://{source.as_posix()}"
    config = tmp_path / "process.json"
    config.write_text(
        json.dumps(
            {
                "schema_version": "otc.process-bootstrap/v1",
                "provider": "json",
                "descriptor": descriptor().to_wire(),
                "target": target,
                "managed": False,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    plan = operations()[0]
    connector = {"id": "json", "version": "0.1.0", "contract_version": "1.0"}
    limits = plan.resource_bounds
    hello = ConnectorProcessEnvelope(
        protocol="otc.connector-process/v1",
        message_id="hello",
        session_id="session",
        operation=ProcessOperation.HELLO,
        connector=connector,
        capability_version="1.0",
        resource_limits=limits,
        credential_reference=None,
        payload={
            "portable_plan_version": "otc.portable-temporal-plan/v1",
            "capability_versions": {"timeseries.scan.range": "1.0"},
        },
        artifact_references=(),
    )
    execute = ConnectorProcessEnvelope(
        protocol="otc.connector-process/v1",
        message_id="execute",
        session_id="session",
        operation=ProcessOperation.EXECUTE,
        connector=connector,
        capability_version="1.0",
        resource_limits=limits,
        credential_reference=None,
        payload={
            "target": target,
            "portable_plan": plan.to_wire(),
            "snapshot_reference": None,
        },
        artifact_references=(),
    )
    request_bytes = BytesIO()
    write_frame(request_bytes, hello)
    write_frame(request_bytes, execute)
    environment = os.environ.copy()
    environment.update(
        {
            "OTC_PROCESS_CONFIG": str(config),
            "OTC_ARTIFACT_ROOT": str(tmp_path / "artifacts"),
        }
    )

    completed = subprocess.run(
        [sys.executable, "-m", "open_table_connector.process"],
        input=request_bytes.getvalue(),
        capture_output=True,
        check=False,
        env=environment,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")
    responses = BytesIO(completed.stdout)
    hello_response = ConnectorProcessEnvelope.from_response_wire(
        read_frame(responses, 16 * 1024 * 1024)
    )
    execute_response = ConnectorProcessEnvelope.from_response_wire(
        read_frame(responses, 16 * 1024 * 1024)
    )
    assert read_frame(responses, 16 * 1024 * 1024) is None
    assert hello_response.payload["result"]["capability_versions"] == {
        "timeseries.scan.range": "1.0"
    }
    assert execute_response.payload["ok"] is True
    assert execute_response.payload["result"]["receipt"]["returned_rows"] == 4
    assert len(execute_response.artifact_references) == 1


def test_executable_refuses_an_unconfigured_empty_registry(tmp_path: Path) -> None:
    environment = os.environ.copy()
    environment.pop("OTC_PROCESS_CONFIG", None)
    environment["OTC_ARTIFACT_ROOT"] = str(tmp_path)

    completed = subprocess.run(
        [sys.executable, "-m", "open_table_connector.process"],
        input=b"",
        capture_output=True,
        check=False,
        env=environment,
        timeout=10,
    )

    assert completed.returncode == 2
    assert completed.stderr == b"OTC_PROCESS_CONFIG is required\n"
