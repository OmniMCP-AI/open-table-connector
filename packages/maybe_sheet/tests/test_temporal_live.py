from __future__ import annotations

import hashlib
import json
import os

import pytest

from open_table_connector.maybe_sheet import SubprocessProcessClient, probe_temporal_capabilities


@pytest.mark.skipif(
    os.environ.get("OTC_TEST_MBS_ENABLED") != "1" or not os.environ.get("OTC_TEST_MBS_URI"),
    reason="OTC_TEST_MBS_ENABLED=1 and OTC_TEST_MBS_URI are required",
)
def test_live_maybe_sheet_temporal_capability_evidence() -> None:
    capabilities = sorted(probe_temporal_capabilities(SubprocessProcessClient()))
    assert "timeseries.describe/1.0" in capabilities
    evidence = hashlib.sha256(json.dumps(capabilities).encode()).hexdigest()
    print(f"MaybeSheet temporal capability evidence sha256:{evidence}")
