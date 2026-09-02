from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

import polars as pl
import pyarrow as pa
from open_table_connector.contract import (
    PROVIDER_FEISHU_BITABLE,
    SCHEME_FEISHU,
    ArrowReadResult,
    ArrowTableReader,
    BaseConvention,
    CapabilityIdentity,
    CapabilityManifest,
    ConnectorError,
    ConnectorErrorCode,
    ConnectorIdentity,
    InspectRequest,
    PolarsReadResult,
    PolarsTableReader,
    ResolveContext,
    ResolvedTable,
    TableInspection,
    TableInspector,
    TableMode,
    TableReadRequest,
    TableURI,
    TableWriter,
    TableWriteRequest,
    TableWriteResult,
    URIResolver,
)
from open_table_connector.contract.fingerprints import (
    arrow_content_fingerprint,
    arrow_schema_fingerprint,
    operation_identity,
)

from .identity import FEISHU_RECORD_ID_FIELD

CONNECTOR_IDENTITY = ConnectorIdentity(PROVIDER_FEISHU_BITABLE, "0.1.0", "1.0")
FEISHU_API_ENDPOINT = "https://open.feishu.cn/open-apis/bitable/v1"
URI_RESOLVER_CAPABILITY = CapabilityIdentity("uri.resolve", "1.0")
TABLE_INSPECT_CAPABILITY = CapabilityIdentity("table.inspect", "1.0")
TABLE_READ_ARROW_CAPABILITY = CapabilityIdentity("table.read.arrow", "1.0")
TABLE_READ_POLARS_CAPABILITY = CapabilityIdentity("table.read.polars", "1.0")
TABLE_WRITE_CAPABILITY = CapabilityIdentity("table.write", "1.0")
FEISHU_BATCH_CREATE_LIMIT = 500
FEISHU_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
CAPABILITY_MANIFEST = CapabilityManifest(CONNECTOR_IDENTITY, (URI_RESOLVER_CAPABILITY, TABLE_INSPECT_CAPABILITY, TABLE_READ_ARROW_CAPABILITY, TABLE_READ_POLARS_CAPABILITY, TABLE_WRITE_CAPABILITY), (TableMode.BASE,), (SCHEME_FEISHU, PROVIDER_FEISHU_BITABLE))


class FeishuTransport(Protocol):
    def request(self, method: str, url: str, *, headers: Mapping[str, str], body: Mapping[str, Any] | None = None, timeout: int | None = None) -> Mapping[str, Any]: ...


class UrllibFeishuTransport:
    def request(self, method, url, *, headers, body=None, timeout=None):
        data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
        request = Request(url, data=data, headers={**headers, "Content-Type": "application/json; charset=utf-8"}, method=method)
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = response.read(FEISHU_MAX_RESPONSE_BYTES + 1)
                if len(payload) > FEISHU_MAX_RESPONSE_BYTES:
                    raise ConnectorError(
                        ConnectorErrorCode.RESOURCE_LIMIT_EXCEEDED,
                        "Feishu Bitable response exceeded the configured byte limit",
                        {"max_bytes": FEISHU_MAX_RESPONSE_BYTES},
                    )
                return json.loads(payload)
        except HTTPError as exc:
            code = (
                ConnectorErrorCode.AUTHENTICATION
                if exc.code in {401, 403}
                else ConnectorErrorCode.EXECUTION_FAILED
            )
            raise ConnectorError(code, "Feishu Bitable request failed", {"status": exc.code}) from None
        except URLError as exc:
            if _looks_like_timeout(exc.reason):
                raise ConnectorError(ConnectorErrorCode.TIMEOUT, "Feishu Bitable request timed out", {}) from None
            raise ConnectorError(ConnectorErrorCode.EXECUTION_FAILED, "Feishu Bitable request failed", {"reason": "unexpected transport exception"}) from None
        except TimeoutError:
            raise ConnectorError(ConnectorErrorCode.TIMEOUT, "Feishu Bitable request timed out", {}) from None
        except ConnectorError:
            raise
        except Exception:
            raise ConnectorError(ConnectorErrorCode.EXECUTION_FAILED, "Feishu Bitable request failed", {"reason": "unexpected transport exception"}) from None


def _looks_like_timeout(reason: object) -> bool:
    if isinstance(reason, TimeoutError):
        return True
    if isinstance(reason, OSError) and isinstance(getattr(reason, "strerror", None), str):
        return "timed out" in reason.strerror.casefold()
    return "timed out" in str(reason).casefold()


@dataclass(frozen=True)
class FeishuBitableReadOptions:
    field_names: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "field_names", tuple(str(item) for item in self.field_names))


@dataclass(frozen=True)
class FeishuBitableTableReadRequest(TableReadRequest):
    options: FeishuBitableReadOptions = field(default_factory=FeishuBitableReadOptions)


@dataclass(frozen=True)
class ResolvedFeishuBitable:
    app_token: str
    table_id: str


def _arrow_from_records(records: list[Mapping[str, Any]], field_names: tuple[str, ...] = ()) -> pa.Table:
    names = [FEISHU_RECORD_ID_FIELD]
    selected = set(field_names)
    for record in records:
        for name in dict(record.get("fields", {})):
            if (not selected or str(name) in selected) and str(name) not in names:
                names.append(str(name))
    columns: dict[str, list[Any]] = {name: [] for name in names}
    for record in records:
        columns[FEISHU_RECORD_ID_FIELD].append(record.get("record_id"))
        fields = record.get("fields", {})
        for name in names[1:]:
            value = fields.get(name)
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False, sort_keys=True)
            columns[name].append(value)
    arrays = {}
    for name, values in columns.items():
        try:
            arrays[name] = pa.array(values)
        except (pa.ArrowInvalid, pa.ArrowTypeError):
            arrays[name] = pa.array([None if value is None else str(value) for value in values], type=pa.string())
    return pa.table(arrays)


class FeishuBitableConnector(URIResolver, TableInspector, ArrowTableReader, PolarsTableReader, TableWriter):
    identity = CONNECTOR_IDENTITY
    manifest = CAPABILITY_MANIFEST

    def formula_extension_for(self):
        from open_table_connector.formulas import CompositeFormulaConnectorExtension

        from .formula import FeishuBitableFieldFormulaExtension

        return CompositeFormulaConnectorExtension(
            field=FeishuBitableFieldFormulaExtension(self),
        )

    def __init__(
        self,
        transport: FeishuTransport | None = None,
        *,
        tenant_access_token: str | None = None,
        timeout: int = 30,
        api_endpoint: str = FEISHU_API_ENDPOINT,
    ):
        self._transport = transport or UrllibFeishuTransport()
        self._tenant_access_token = tenant_access_token
        self._timeout = timeout
        self._api_endpoint = api_endpoint.rstrip("/")

    def _url(self, suffix: str) -> str:
        return f"{self._api_endpoint}/{suffix.lstrip('/') }"

    def resolve(self, uri: TableURI, context: ResolveContext) -> ResolvedTable:
        parsed = urlsplit(uri.value)
        if uri.scheme not in {SCHEME_FEISHU, PROVIDER_FEISHU_BITABLE} or not parsed.netloc or not parsed.path.strip("/"):
            raise ConnectorError(ConnectorErrorCode.INVALID_URI, "Feishu Bitable URI must be feishu://app_token/table_id", {"scheme": uri.scheme})
        parts = parsed.path.strip("/").split("/")
        if len(parts) != 1 or not parts[0]:
            raise ConnectorError(ConnectorErrorCode.INVALID_URI, "Feishu Bitable URI requires one table ID", {})
        return ResolvedTable(uri, TableMode.BASE, ResolvedFeishuBitable(parsed.netloc, parts[0]))

    def _headers(self):
        if not self._tenant_access_token:
            raise ConnectorError.authentication("Feishu tenant access token is not configured")
        return {"Authorization": f"Bearer {self._tenant_access_token}"}

    def _read(self, request: FeishuBitableTableReadRequest):
        resource = self.resolve(request.uri, ResolveContext()).resource
        records: list[Mapping[str, Any]] = []
        page_token: str | None = None
        while True:
            query = "page_size=500"
            if page_token:
                query += "&page_token=" + quote(page_token, safe="")
            url = self._url(
                f"apps/{quote(resource.app_token, safe='')}/tables/"
                f"{quote(resource.table_id, safe='')}/records?{query}"
            )
            payload = self._transport.request("GET", url, headers=self._headers(), timeout=request.resource_limits.timeout_seconds or self._timeout)
            if payload.get("code", 0) != 0:
                raise ConnectorError(ConnectorErrorCode.EXECUTION_FAILED, "Feishu Bitable read failed", {"code": payload.get("code")})
            data = payload.get("data", {})
            records.extend(data.get("items", []))
            if request.resource_limits.max_rows and len(records) >= request.resource_limits.max_rows:
                records = records[:request.resource_limits.max_rows]
                break
            if not data.get("has_more"):
                break
            page_token = data.get("page_token")
            if not page_token:
                break
        table = _arrow_from_records(records, request.options.field_names)
        revision = "sha256:" + sha256(json.dumps(records, sort_keys=True, default=str).encode()).hexdigest()
        return table, revision, resource

    def _receipt(self, request, table, revision, capability):
        schema = arrow_schema_fingerprint(table.schema)
        content = arrow_content_fingerprint(table)
        operation = operation_identity(connector=CONNECTOR_IDENTITY, capability=TABLE_READ_ARROW_CAPABILITY, uri=request.uri, source_revision=revision, schema_fingerprint=schema, content_fingerprint=content, parameters={"fields": request.options.field_names})
        from open_table_connector.contract import NeutralReceipt
        return NeutralReceipt(
            CONNECTOR_IDENTITY,
            capability,
            operation,
            request.uri,
            TableMode.BASE,
            revision,
            schema,
            content,
            BaseConvention(record_id_field=FEISHU_RECORD_ID_FIELD, ordinal_snapshot_id=revision),
            table.num_rows,
            1,
        )

    def read_arrow(self, request):
        request = request if isinstance(request, FeishuBitableTableReadRequest) else FeishuBitableTableReadRequest(request.uri, request.resource_limits)
        table, revision, _ = self._read(request)
        return ArrowReadResult(table, self._receipt(request, table, revision, TABLE_READ_ARROW_CAPABILITY))

    def read_polars(self, request):
        result = self.read_arrow(request)
        return PolarsReadResult(pl.from_arrow(result.table), result.receipt)

    def inspect(self, request: InspectRequest):
        result = self.read_arrow(request)
        return TableInspection(request.uri, TableMode.BASE, tuple(result.table.column_names), result.receipt.schema_fingerprint, result.table.num_rows, result.receipt.coordinate_convention, {"provider": PROVIDER_FEISHU_BITABLE})

    def write(self, request: TableWriteRequest) -> TableWriteResult:
        if request.if_exists == "error":
            raise ConnectorError(
                ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
                "Feishu Bitable cannot enforce create-if-empty atomically",
                {"if_exists": request.if_exists},
            )
        if request.if_exists not in {"append"}:
            raise ConnectorError(ConnectorErrorCode.UNSUPPORTED_CAPABILITY, "Feishu Bitable only supports append writes", {"if_exists": request.if_exists})
        resource = self.resolve(request.uri, ResolveContext()).resource
        records = [
            {
                "fields": {
                    name: value
                    for name, value in zip(request.frame.columns, row, strict=False)
                }
            }
            for row in request.frame.rows()
        ]
        url = self._url(
            f"apps/{quote(resource.app_token, safe='')}/tables/"
            f"{quote(resource.table_id, safe='')}/records/batch_create"
        )
        payloads: list[Mapping[str, Any]] = []
        for start in range(0, len(records), FEISHU_BATCH_CREATE_LIMIT):
            payload = self._transport.request(
                "POST",
                url,
                headers=self._headers(),
                body={"records": records[start : start + FEISHU_BATCH_CREATE_LIMIT]},
                timeout=self._timeout,
            )
            if payload.get("code", 0) != 0:
                raise ConnectorError(
                    ConnectorErrorCode.EXECUTION_FAILED,
                    "Feishu Bitable write failed",
                    {"code": payload.get("code")},
                )
            payloads.append(payload)
        revision = "sha256:" + sha256(json.dumps(payloads, sort_keys=True, default=str).encode()).hexdigest()
        table = pa.Table.from_pydict({name: request.frame.get_column(name).to_list() for name in request.frame.columns})
        schema = arrow_schema_fingerprint(table.schema)
        content = arrow_content_fingerprint(table)
        operation = operation_identity(connector=CONNECTOR_IDENTITY, capability=TABLE_WRITE_CAPABILITY, uri=request.uri, source_revision=revision, schema_fingerprint=schema, content_fingerprint=content, parameters={"if_exists": request.if_exists})
        from open_table_connector.contract import NeutralReceipt
        receipt = NeutralReceipt(CONNECTOR_IDENTITY, TABLE_WRITE_CAPABILITY, operation, request.uri, TableMode.BASE, revision, schema, content, BaseConvention(record_id_field="_record_id", ordinal_snapshot_id=revision), table.num_rows, 1)
        return TableWriteResult(receipt, request.frame.height)
