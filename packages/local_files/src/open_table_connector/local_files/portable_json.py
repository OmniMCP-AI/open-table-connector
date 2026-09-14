"""Versioned portable-table JSON and JSONL encoding plus create-only publication."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
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
    mode = "jsonl" if parsed.scheme == PROVIDER_JSONL or path.suffix.lower() == ".jsonl" else "json"
    if path.suffix.lower() not in {".json", ".jsonl"} or (parsed.scheme == PROVIDER_JSON and path.suffix.lower() != ".json") or (parsed.scheme == PROVIDER_JSONL and path.suffix.lower() != ".jsonl"):
        raise ValueError("portable JSON destination scheme and suffix must agree")
    return path, mode


def _schema(frame: pl.DataFrame) -> list[dict[str, str]]:
    return [{"name": name, "type": str(dtype)} for name, dtype in frame.schema.items()]


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
    fields = _schema(frame)
    rows = [[_value(value, dtype) for value, dtype in zip(row, frame.dtypes, strict=True)] for row in frame.iter_rows()]
    def dump(value: object) -> str:
        return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    if mode == "json":
        payload = {"schemaVersion": SCHEMA_VERSION, "profile": PORTABLE_TABLE_PROFILE_V1, "schema": fields, "rows": rows}
        return (dump(payload) + "\n").encode("utf-8")
    metadata = {"$otc": {"schemaVersion": JSONL_SCHEMA_VERSION, "profile": PORTABLE_TABLE_PROFILE_V1, "schema": fields}}
    return (dump(metadata) + "\n" + "".join(dump(row) + "\n" for row in rows)).encode("utf-8")


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
    if mode == "json":
        if not isinstance(payload, dict) or payload.get("schemaVersion") != SCHEMA_VERSION:
            return None
        metadata, rows = payload, payload.get("rows")
    else:
        if not isinstance(payload, list) or not payload or not isinstance(payload[0], dict) or set(payload[0]) != {"$otc"}:
            return None
        metadata, rows = payload[0]["$otc"], payload[1:]
    expected_version = SCHEMA_VERSION if mode == "json" else JSONL_SCHEMA_VERSION
    required = {"schemaVersion", "profile", "schema", "rows"} if mode == "json" else {"schemaVersion", "profile", "schema"}
    if not isinstance(metadata, dict) or set(metadata) != required or metadata.get("schemaVersion") != expected_version or metadata.get("profile") != PORTABLE_TABLE_PROFILE_V1 or not isinstance(metadata.get("schema"), list) or not isinstance(rows, list):
        raise ValueError("portable JSON envelope is invalid")
    fields = metadata["schema"]
    schema = {field["name"]: _dtype(field["type"]) for field in fields if isinstance(field, dict) and set(field) == {"name", "type"}}
    if len(schema) != len(fields) or any(not isinstance(row, list) or len(row) != len(schema) for row in rows):
        raise ValueError("portable JSON rows do not match schema")
    names = list(schema)
    return pl.DataFrame([{name: _parsed(value, schema[name]) for name, value in zip(names, row, strict=True)} for row in rows], schema=schema, orient="row")


def publish(path: Path, data: bytes) -> str:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
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
