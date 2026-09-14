from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from multiprocessing import get_context
from pathlib import Path

import open_table_connector.local_files.portable_json as portable_json
import open_table_connector.sdk as otc
import polars as pl
import pytest
from open_table_connector.local_files import LocalFilesConnector


def _client() -> otc.Client:
    return otc.Client(registry=otc.ConnectorRegistry([LocalFilesConnector()]))


def _uri(scheme: str, path: Path) -> str:
    return path.as_uri().replace("file://", f"{scheme}://", 1)


def _race_materialize(uri: str, queue) -> None:
    try:
        _client().materialize(pl.DataFrame({"id": [1]}), to=uri, profile=otc.PORTABLE_TABLE_PROFILE_V1, idempotency_key="race")
        queue.put("succeeded")
    except otc.OTCError as exc:
        queue.put(exc.result.error.code.value)


@pytest.mark.parametrize(
    ("scheme", "suffix", "expected"),
    [
        ("json", ".json", b'{"schemaVersion":"otc.table-json/v1","profile":"otc.portable-table/v1","schema":[{"name":"id","type":"Int64"},{"name":"label","type":"String"}],"rows":[[9223372036854775807,"\xe6\x9d\xb1\xe4\xba\xac"],[null,""]]}\n'),
        ("jsonl", ".jsonl", b'{"$otc":{"schemaVersion":"otc.table-jsonl/v1","profile":"otc.portable-table/v1","schema":[{"name":"id","type":"Int64"},{"name":"label","type":"String"}]}}\n[9223372036854775807,"\xe6\x9d\xb1\xe4\xba\xac"]\n[null,""]\n'),
    ],
)
def test_portable_materialization_writes_deterministic_versioned_bytes_and_recovers_types(
    tmp_path: Path, scheme: str, suffix: str, expected: bytes
) -> None:
    """Catches an envelope that changes field order, scalar rendering, or typed recovery."""
    path = tmp_path / f"portable{suffix}"
    source = pl.DataFrame({"id": [2**63 - 1, None], "label": ["東京", ""]}, schema={"id": pl.Int64, "label": pl.String})

    result = _client().materialize(source, to=_uri(scheme, path), profile=otc.PORTABLE_TABLE_PROFILE_V1, idempotency_key=f"golden-{scheme}")

    assert path.read_bytes() == expected
    assert result.commit is otc.CommitState.COMMITTED
    assert result.verification is otc.VerificationState.PASSED
    assert _client().open(_uri(scheme, path)).require_value().read().require_value().equals(source)


def test_portable_json_materialization_preserves_all_portable_scalar_types(tmp_path: Path) -> None:
    """Catches type erasure for decimal, date, or UTC datetime values."""
    path = tmp_path / "all-types.json"
    source = pl.DataFrame({"truth": [True, None], "int": [-(2**63), None], "float": [1.25, None], "amount": [Decimal("123.450"), None], "day": [date(2026, 9, 14), None], "when": [datetime(2026, 9, 14, 1, 2, 3, 456789, UTC), None]}, schema={"truth": pl.Boolean, "int": pl.Int64, "float": pl.Float64, "amount": pl.Decimal(precision=6, scale=3), "day": pl.Date, "when": pl.Datetime("us", "UTC")})

    _client().materialize(source, to=_uri("json", path), profile=otc.PORTABLE_TABLE_PROFILE_V1, idempotency_key="all-types")

    assert _client().open(_uri("json", path)).require_value().read().require_value().equals(source)


@pytest.mark.parametrize(("scheme", "suffix"), [("json", ".json"), ("jsonl", ".jsonl")])
def test_portable_materialization_writes_metadata_only_for_zero_rows(tmp_path: Path, scheme: str, suffix: str) -> None:
    """Catches a zero-row materialization that loses its declared schema."""
    path = tmp_path / f"empty{suffix}"
    source = pl.DataFrame(schema={"all_null": pl.String, "count": pl.Int64})

    _client().materialize(source, to=_uri(scheme, path), profile=otc.PORTABLE_TABLE_PROFILE_V1, idempotency_key=f"empty-{scheme}")

    observed = _client().open(_uri(scheme, path)).require_value().read().require_value()
    assert observed.schema == source.schema
    assert observed.height == 0


def test_portable_materialization_keeps_legacy_json_and_jsonl_untyped(tmp_path: Path) -> None:
    """Catches legacy reads being mistaken for versioned portable envelopes."""
    json_path = tmp_path / "legacy.json"
    jsonl_path = tmp_path / "legacy.jsonl"
    json_path.write_text('[{"id":1,"name":"legacy"}]\n', encoding="utf-8")
    jsonl_path.write_text('{"id":1,"name":"legacy"}\n', encoding="utf-8")

    assert _client().open(_uri("json", json_path)).require_value().read().require_value().to_dicts() == [{"id": 1, "name": "legacy"}]
    assert _client().open(_uri("jsonl", jsonl_path)).require_value().read().require_value().to_dicts() == [{"id": 1, "name": "legacy"}]


def test_portable_materialization_is_create_only_and_rejects_invalid_destination(tmp_path: Path) -> None:
    """Catches overwrites and routes unsafe/suffix-mismatched destinations before publication."""
    path = tmp_path / "exists.json"
    path.write_text("[]", encoding="utf-8")
    client = _client()
    source = pl.DataFrame({"id": [1]}, schema={"id": pl.Int64})

    with pytest.raises(otc.OTCError) as exists:
        client.materialize(source, to=_uri("json", path), profile=otc.PORTABLE_TABLE_PROFILE_V1, idempotency_key="exists")
    assert exists.value.result.error.code is otc.ErrorCode.DESTINATION_EXISTS
    assert path.read_text(encoding="utf-8") == "[]"

    with pytest.raises(otc.OTCError) as invalid:
        client.materialize(source, to=_uri("jsonl", tmp_path / "wrong.json"), profile=otc.PORTABLE_TABLE_PROFILE_V1, idempotency_key="wrong-suffix")
    assert invalid.value.result.error.code is otc.ErrorCode.INVALID_TARGET


def test_post_publication_failure_is_committed_and_retains_evidence(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "post.json"
    calls = 0
    real_fsync = portable_json.os.fsync
    def fail_directory_fsync(fd: int) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected")
        real_fsync(fd)
    monkeypatch.setattr(portable_json.os, "fsync", fail_directory_fsync)
    with pytest.raises(otc.OTCError) as raised:
        _client().materialize(pl.DataFrame({"id": [1]}), to=_uri("json", path), profile=otc.PORTABLE_TABLE_PROFILE_V1, idempotency_key="post")
    assert path.exists()
    assert raised.value.result.commit is otc.CommitState.COMMITTED
    assert raised.value.result.verification is otc.VerificationState.FAILED
    assert raised.value.result.error.code is otc.ErrorCode.READBACK_MISMATCH
    assert [receipt.operation for receipt in raised.value.result.receipts] == ["table.materialize.create"]


def test_prepublication_failure_leaves_no_destination(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "pre.json"
    monkeypatch.setattr(portable_json.os, "fsync", lambda _: (_ for _ in ()).throw(OSError("injected")))
    with pytest.raises(otc.OTCError):
        _client().materialize(pl.DataFrame({"id": [1]}), to=_uri("json", path), profile=otc.PORTABLE_TABLE_PROFILE_V1, idempotency_key="pre")
    assert not path.exists()


def test_file_json_destination_is_portable_base_mode(tmp_path: Path) -> None:
    path = tmp_path / "file.json"
    source = pl.DataFrame({"all_null": [None, None], "label": ["a", "b"]}, schema={"all_null": pl.String, "label": pl.String})
    result = _client().materialize(source, to=path.as_uri(), profile=otc.PORTABLE_TABLE_PROFILE_V1, idempotency_key="file")
    assert result.require_value()._binding.mode is otc.TableMode.BASE_MODE
    assert _client().open(path.as_uri()).require_value().read().require_value().equals(source)


def test_portable_profile_rejects_nanosecond_datetime_before_publication(tmp_path: Path) -> None:
    path = tmp_path / "nanoseconds.json"
    source = pl.DataFrame({"when": [1]}, schema={"when": pl.Datetime("ns", "UTC")})
    with pytest.raises(otc.OTCError) as raised:
        _client().materialize(source, to=_uri("json", path), profile=otc.PORTABLE_TABLE_PROFILE_V1, idempotency_key="ns")
    assert raised.value.result.error.code is otc.ErrorCode.INVALID_SCHEMA
    assert not path.exists()


def test_two_process_creators_have_one_winner_and_one_create_only_loser(tmp_path: Path) -> None:
    path = tmp_path / "race.json"
    context = get_context("spawn")
    queue = context.Queue()
    processes = [context.Process(target=_race_materialize, args=(_uri("json", path), queue)) for _ in range(2)]
    for process in processes:
        process.start()
    for process in processes:
        process.join(20)
        assert process.exitcode == 0
    assert sorted(queue.get(timeout=2) for _ in processes) == ["destination_exists", "succeeded"]
    assert _client().open(_uri("json", path)).require_value().read().require_value().to_dicts() == [{"id": 1}]
