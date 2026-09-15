"""Versioned portable-table JSON and JSONL encoding plus create-only publication."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import unquote, urlsplit

import polars as pl
from open_table_connector.contract import PROVIDER_JSON, PROVIDER_JSONL, SCHEME_FILE, TableURI
from open_table_connector.sdk.materialization import PORTABLE_TABLE_PROFILE_V1

SCHEMA_VERSION = "otc.table-json/v1"
JSONL_SCHEMA_VERSION = "otc.table-jsonl/v1"


class PublicationError(RuntimeError):
    def __init__(self, revision: str) -> None:
        self.revision = revision


class ResourceLimitError(ValueError):
    """The portable payload exceeded a pre-publication bound."""


class IdempotencyConflict(ValueError):
    """A durable replay key was reused for another request."""


MAX_ROWS = 1_000_000
MAX_BYTES = 128 * 1024 * 1024


def destination_path(uri: TableURI) -> tuple[Path, str]:
    parsed = urlsplit(uri.value)
    if parsed.scheme not in {SCHEME_FILE, PROVIDER_JSON, PROVIDER_JSONL} or parsed.username or parsed.password:
        raise ValueError("portable JSON destination must be a credential-free file, json, or jsonl URI")
    if parsed.netloc not in {"", "localhost"} or parsed.query or parsed.fragment:
        raise ValueError("portable JSON destination cannot contain host, query, or fragment")
    path = Path(unquote(parsed.path))
    if not path.is_absolute() or ".." in path.parts or path.is_symlink():
        raise ValueError("portable JSON destination must be an absolute non-symlink file")
    parent = path.parent
    if not parent.is_dir() or parent.is_symlink():
        raise ValueError("portable JSON destination parent must be an existing non-symlink directory")
    mode = PROVIDER_JSONL if parsed.scheme == PROVIDER_JSONL or path.suffix.lower() == ".jsonl" else PROVIDER_JSON
    if path.suffix.lower() not in {".json", ".jsonl"} or (parsed.scheme == PROVIDER_JSON and path.suffix.lower() != ".json") or (parsed.scheme == PROVIDER_JSONL and path.suffix.lower() != ".jsonl"):
        raise ValueError("portable JSON destination scheme and suffix must agree")
    return path, mode


def _schema(frame: pl.DataFrame) -> dict[str, list[dict[str, object]]]:
    return {
        "fields": [
            {
                "name": name,
                "type": str(dtype),
                "nullable": frame.get_column(name).null_count() > 0,
            }
            for name, dtype in frame.schema.items()
        ]
    }


def _value(value: object, dtype: pl.DataType) -> object:
    if value is None:
        return None
    rendered = str(dtype)
    if rendered.startswith("Decimal"):
        return format(value, "f")
    if rendered == "Date":
        return value.isoformat()
    if rendered.startswith("Datetime"):
        assert isinstance(value, datetime)
        value = value.astimezone(UTC)
        return value.strftime("%Y-%m-%dT%H:%M:%S.") + f"{value.microsecond:06d}Z"
    return value


def encode(frame: pl.DataFrame, mode: str) -> bytes:
    if frame.height > MAX_ROWS:
        raise ResourceLimitError("portable JSON materialization exceeds the row limit")
    schema = _schema(frame)
    names = [field["name"] for field in schema["fields"]]
    rows = [
        {
            name: _value(value, dtype)
            for name, value, dtype in zip(names, row, frame.dtypes, strict=True)
        }
        for row in frame.iter_rows()
    ]
    def dump(value: object) -> str:
        return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    if mode == PROVIDER_JSON:
        payload = {"schemaVersion": SCHEMA_VERSION, "profile": PORTABLE_TABLE_PROFILE_V1, "schema": schema, "rows": rows}
        data = (dump(payload) + "\n").encode("utf-8")
    else:
        metadata = {"$otc": {"schemaVersion": JSONL_SCHEMA_VERSION, "profile": PORTABLE_TABLE_PROFILE_V1, "schema": schema}}
        data = (dump(metadata) + "\n" + "".join(dump(row) + "\n" for row in rows)).encode("utf-8")
    if len(data) > MAX_BYTES:
        raise ResourceLimitError("portable JSON materialization exceeds the encoded byte limit")
    return data


def _dtype(name: str) -> pl.DataType:
    if name in {"String", "Boolean", "Int64", "Float64", "Date"}:
        return getattr(pl, name)
    if name.startswith("Decimal(precision="):
        precision, scale = name.removeprefix("Decimal(precision=").removesuffix(")").split(", scale=")
        return pl.Decimal(int(precision), int(scale))
    if name.startswith("Datetime(") and "time_zone='UTC'" in name:
        unit = name.split("time_unit='")[1].split("'", 1)[0]
        return pl.Datetime(unit, "UTC")
    raise ValueError(f"portable JSON schema type is unsupported: {name}")


def _parsed(value: object, dtype: pl.DataType) -> object:
    if value is None:
        return None
    rendered = str(dtype)
    if rendered.startswith("Decimal"):
        return Decimal(value)
    if rendered == "Date":
        return date.fromisoformat(value)
    if rendered.startswith("Datetime"):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


def decode(payload: object, *, mode: str) -> pl.DataFrame | None:
    if mode == PROVIDER_JSON:
        if not isinstance(payload, dict) or payload.get("schemaVersion") != SCHEMA_VERSION:
            return None
        metadata, rows = payload, payload.get("rows")
    else:
        if not isinstance(payload, list) or not payload or not isinstance(payload[0], dict) or set(payload[0]) != {"$otc"}:
            return None
        metadata, rows = payload[0]["$otc"], payload[1:]
    expected_version = SCHEMA_VERSION if mode == PROVIDER_JSON else JSONL_SCHEMA_VERSION
    required = {"schemaVersion", "profile", "schema", "rows"} if mode == PROVIDER_JSON else {"schemaVersion", "profile", "schema"}
    schema_payload = metadata.get("schema") if isinstance(metadata, dict) else None
    if not isinstance(metadata, dict) or set(metadata) != required or metadata.get("schemaVersion") != expected_version or metadata.get("profile") != PORTABLE_TABLE_PROFILE_V1 or not isinstance(schema_payload, dict) or set(schema_payload) != {"fields"} or not isinstance(schema_payload["fields"], list) or not isinstance(rows, list):
        raise ValueError("portable JSON envelope is invalid")
    fields = schema_payload["fields"]
    schema: dict[str, pl.DataType] = {}
    nullable: dict[str, bool] = {}
    for field in fields:
        if (
            not isinstance(field, dict)
            or set(field) != {"name", "type", "nullable"}
            or not isinstance(field["name"], str)
            or not isinstance(field["type"], str)
            or not isinstance(field["nullable"], bool)
        ):
            raise ValueError("portable JSON schema fields are invalid")
        schema[field["name"]] = _dtype(field["type"])
        nullable[field["name"]] = field["nullable"]
    if len(schema) != len(fields) or any(not isinstance(row, dict) or set(row) != set(schema) for row in rows):
        raise ValueError("portable JSON rows do not match schema")
    names = list(schema)
    for row in rows:
        if any(row[name] is None and not nullable[name] for name in names):
            raise ValueError("portable JSON row contains null in a non-nullable field")
    return pl.DataFrame([{name: _parsed(row[name], schema[name]) for name in names} for row in rows], schema=schema)


@contextmanager
def replay_lock(path: Path):
    """Serialize replay lookup/publication for one canonical destination."""
    import fcntl

    lock_path = path.with_name(path.name + ".otc-lock")
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def replay_path(path: Path, identity: str | None = None) -> Path:
    suffix = ".otc-replay.json" if identity is None else f".otc-replay-{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:16]}.json"
    return path.with_name(path.name + suffix)


def replay_index_path(path: Path) -> Path:
    return path.parent / ".otc-portable-replay-index.json"


@contextmanager
def replay_transaction(path: Path):
    with replay_lock(path), replay_lock(replay_index_path(path)):
        yield


def _replay_index_key(
    path: Path, connector_id: str, idempotency_key: str, scope: str | None = None
) -> str:
    canonical_scope = scope or str(path.resolve())
    return hashlib.sha256(
        f"{connector_id}\0{canonical_scope}\0{idempotency_key}".encode()
    ).hexdigest()


def load_replay_index(
    path: Path,
    connector_id: str,
    idempotency_key: str,
    scope: str | None = None,
) -> dict[str, object] | None:
    try:
        payload = json.loads(replay_index_path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("portable replay index is invalid") from exc
    if not isinstance(payload, dict):
        raise ValueError("portable replay index is invalid")
    record = payload.get(_replay_index_key(path, connector_id, idempotency_key, scope))
    if record is None:
        return None
    if not isinstance(record, dict):
        raise ValueError("portable replay index is invalid")
    return record


def store_replay_index(
    path: Path, connector_id: str, record: dict[str, object], scope: str | None = None
) -> None:
    index = replay_index_path(path)
    try:
        payload = json.loads(index.read_text(encoding="utf-8"))
    except FileNotFoundError:
        payload = {}
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("portable replay index is invalid") from exc
    if not isinstance(payload, dict):
        raise ValueError("portable replay index is invalid")
    key = record.get("idempotency_key")
    if not isinstance(key, str):
        raise ValueError("portable replay record is invalid")
    payload[_replay_index_key(path, connector_id, key, scope)] = record
    temporary = index.with_name(f".{index.name}.{secrets.token_hex(8)}")
    data = (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    try:
        with temporary.open("xb") as stream:
            os.chmod(temporary, 0o600)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, index)
        directory = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def load_replay(path: Path, identity: str | None = None) -> dict[str, object] | None:
    try:
        payload = json.loads(replay_path(path, identity).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("portable JSON replay record is invalid") from exc
    if not isinstance(payload, dict) or set(payload) != {"destination", "profile", "idempotency_key", "schema_fingerprint", "content_fingerprint", "revision", "row_count", "bytes"}:
        raise ValueError("portable JSON replay record is invalid")
    return payload


def store_replay(path: Path, record: dict[str, object], identity: str | None = None) -> None:
    destination = replay_path(path, identity)
    temporary = destination.with_name(f".{destination.name}.{secrets.token_hex(8)}")
    data = (json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    try:
        with temporary.open("xb") as stream:
            os.chmod(temporary, 0o600)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        directory = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def publish(path: Path, data: bytes) -> str:
    directory_flag = getattr(os, "O_DIRECTORY", None)
    nofollow_flag = getattr(os, "O_NOFOLLOW", None)
    if directory_flag is None or nofollow_flag is None:
        raise ValueError("portable JSON publication requires directory no-follow support on this platform")
    flags = os.O_RDONLY | directory_flag | nofollow_flag
    directory = os.open(path.parent, flags)
    temporary = f".{path.name}.{secrets.token_hex(16)}"
    descriptor = -1
    linked = False
    revision = f"sha256:{hashlib.sha256(data).hexdigest()}"
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=directory)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path.name, src_dir_fd=directory, dst_dir_fd=directory, follow_symlinks=False)
            linked = True
        except FileExistsError:
            raise
        finally:
            os.unlink(temporary, dir_fd=directory)
        os.fsync(directory)
    except BaseException as exc:
        if linked:
            raise PublicationError(revision) from exc
        raise
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        os.close(directory)
    return revision
