from __future__ import annotations

from argparse import Namespace
from dataclasses import dataclass
from io import StringIO
import json
from pathlib import Path
import sqlite3
from typing import Any, Callable, Iterable, Mapping

from openpyxl import Workbook
import pyarrow as pa

from open_table_connector.cli.adapters import (
    FeishuBitableAdapter,
    GoogleSheetsAdapter,
    LocalAdapter,
    MaybeSheetAdapter,
)
from open_table_connector.cli.commands import run_command
from open_table_connector.cli.model import CliOptions, Endpoint, parse_endpoint
from open_table_connector.cli.registry import ConnectorRegistry
from open_table_connector.contract import (
    ArrowReadResult,
    BaseConvention,
    CapabilityIdentity,
    ConnectorIdentity,
    NeutralReceipt,
    TableInspection,
    TableMode,
    TableURI,
    TableWriteResult,
)
from open_table_connector.contract.fingerprints import (
    arrow_content_fingerprint,
    arrow_schema_fingerprint,
)


@dataclass(frozen=True)
class RecordedRequest:
    method: str
    url: str
    headers: dict[str, str]
    body: dict[str, Any] | None
    timeout: int | None


@dataclass(frozen=True)
class RecordedProcessCall:
    argv: tuple[str, ...]
    credentials: dict[str, str]
    stdin: str | None
    timeout: int | float | None


def _copy_payload(payload: Any) -> Any:
    return json.loads(json.dumps(payload, ensure_ascii=False, default=str))


class RecordingSheetsTransport:
    def __init__(
        self,
        responses: Mapping[
            str,
            Mapping[str, Any] | Iterable[Mapping[str, Any]],
        ],
        *,
        failure: BaseException | None = None,
    ) -> None:
        self._responses: dict[str, tuple[Mapping[str, Any], ...]] = {}
        for method, payload in responses.items():
            values = (payload,) if isinstance(payload, Mapping) else tuple(payload)
            if not values:
                raise ValueError(f"{method} requires at least one recorded response")
            self._responses[str(method)] = tuple(_copy_payload(item) for item in values)
        self._response_indexes = {method: 0 for method in self._responses}
        self._failure = failure
        self.requests: list[RecordedRequest] = []

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        body: Mapping[str, Any] | None = None,
        timeout: int | None = None,
    ) -> Mapping[str, Any]:
        self.requests.append(
            RecordedRequest(
                method=method,
                url=url,
                headers=dict(headers),
                body=None if body is None else dict(body),
                timeout=timeout,
            )
        )
        if self._failure is not None:
            raise self._failure
        try:
            responses = self._responses[method]
        except KeyError as exc:
            raise KeyError(f"missing recorded response for method {method!r}") from exc
        index = self._response_indexes[method]
        if index >= len(responses):
            raise AssertionError(
                f"recorded responses for method {method!r} were over-consumed"
            )
        self._response_indexes[method] = index + 1
        return _copy_payload(responses[index])


class _ObservedFieldValues(dict[str, Any]):
    def __init__(self, values: Mapping[str, Any], field_reads: list[str]) -> None:
        super().__init__((str(key), value) for key, value in values.items())
        self._field_reads = field_reads

    def get(self, key: str, default: Any = None) -> Any:
        self._field_reads.append(str(key))
        return super().get(key, default)


class RecordingFeishuTransport(RecordingSheetsTransport):
    def __init__(
        self,
        responses: Mapping[
            str,
            Mapping[str, Any] | Iterable[Mapping[str, Any]],
        ],
        *,
        failure: BaseException | None = None,
    ) -> None:
        super().__init__(responses, failure=failure)
        self._field_reads: list[str] = []

    @property
    def used_fields(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(self._field_reads))

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        body: Mapping[str, Any] | None = None,
        timeout: int | None = None,
    ) -> Mapping[str, Any]:
        payload = dict(
            super().request(
                method,
                url,
                headers=headers,
                body=body,
                timeout=timeout,
            )
        )
        data = payload.get("data")
        if not isinstance(data, Mapping):
            return payload
        copied_data = dict(data)
        items = copied_data.get("items")
        if not isinstance(items, list):
            return payload
        copied_items: list[Any] = []
        for item in items:
            if not isinstance(item, Mapping):
                copied_items.append(item)
                continue
            copied_item = dict(item)
            fields = copied_item.get("fields")
            if isinstance(fields, Mapping):
                copied_item["fields"] = _ObservedFieldValues(
                    fields,
                    self._field_reads,
                )
            copied_items.append(copied_item)
        copied_data["items"] = copied_items
        payload["data"] = copied_data
        return payload


class RawProviderFailure(RuntimeError):
    def __init__(self, message: str, *, credential: str) -> None:
        super().__init__(message)
        self.credential = credential


@dataclass(frozen=True)
class ProviderFailureProbe:
    raw_failure: BaseException | Mapping[str, Any]
    fixture_secret: str
    invoke: Callable[[], object]


@dataclass(frozen=True)
class HttpProviderFixture:
    transport: RecordingSheetsTransport
    failure: ProviderFailureProbe


@dataclass(frozen=True)
class ProcessProviderFixture:
    process: RecordingProcessClient
    failure: ProviderFailureProbe


class RecordingProcessClient:
    def __init__(
        self,
        responses: Mapping[str, Mapping[str, Any]],
        *,
        failure: BaseException | None = None,
    ) -> None:
        self._responses = {
            str(operation): _copy_payload(payload)
            for operation, payload in responses.items()
        }
        self._failure = failure
        self.calls: list[RecordedProcessCall] = []

    def run(
        self,
        argv: tuple[str, ...],
        *,
        credentials: Mapping[str, str] | None = None,
        stdin: Iterable[str] | str | None = None,
        timeout: int | float | None = None,
    ) -> Mapping[str, Any]:
        stdin_text: str | None
        if stdin is None or isinstance(stdin, str):
            stdin_text = stdin
        else:
            stdin_text = "".join(str(item) for item in stdin)
        self.calls.append(
            RecordedProcessCall(
                argv=tuple(argv),
                credentials={str(key): str(value) for key, value in (credentials or {}).items()},
                stdin=stdin_text,
                timeout=timeout,
            )
        )
        if self._failure is not None:
            raise self._failure
        if len(argv) < 3:
            raise KeyError(f"missing MaybeSheet operation in argv: {argv!r}")
        operation = argv[2]
        operation_key = f"{argv[1]}:{operation}"
        try:
            payload = self._responses[operation_key]
        except KeyError:
            try:
                payload = self._responses[operation]
            except KeyError as exc:
                raise KeyError(
                    f"missing recorded process response for operation {operation_key!r}"
                ) from exc
        return _copy_payload(payload)


@dataclass(frozen=True)
class CliRunResult:
    exit_code: int
    stdout: str
    stderr: str


def run_cli_command(args: Namespace, registry: ConnectorRegistry) -> CliRunResult:
    stdout = StringIO()
    stderr = StringIO()
    exit_code = run_command(args, registry, stdout, stderr)
    return CliRunResult(exit_code, stdout.getvalue(), stderr.getvalue())


@dataclass(frozen=True)
class RecordedCliCall:
    endpoint: Endpoint
    options: CliOptions
    table: pa.Table | None = None


class RecordingCliAdapter:
    def __init__(
        self,
        *,
        connector_id: str,
        schemes: tuple[str, ...],
        capabilities: tuple[str, ...],
        table: pa.Table,
        failures: Mapping[str, BaseException] | None = None,
        vendor_receipt_ref: str | None = None,
    ) -> None:
        self.identity = ConnectorIdentity(connector_id, "1.0.0", "1.0")
        self.schemes = tuple(schemes)
        self.capabilities = tuple(
            CapabilityIdentity(capability, "1.0") for capability in capabilities
        )
        self.modes = (TableMode.BASE,)
        self.provider_owned_fields: tuple[str, ...] = ()
        self._table = table
        self._failures = dict(failures or {})
        self._vendor_receipt_ref = vendor_receipt_ref
        self.read_calls: list[RecordedCliCall] = []
        self.inspect_calls: list[RecordedCliCall] = []
        self.preflight_calls: list[RecordedCliCall] = []
        self.write_calls: list[RecordedCliCall] = []

    def _raise_failure(self, operation: str) -> None:
        failure = self._failures.get(operation)
        if failure is not None:
            raise failure

    @staticmethod
    def _safe_uri(endpoint: Endpoint) -> TableURI:
        if endpoint.uri is not None:
            return endpoint.uri
        if endpoint.path is not None:
            return TableURI(endpoint.path.resolve().as_uri())
        return TableURI("stdio://fixture")

    def _receipt(
        self,
        endpoint: Endpoint,
        table: pa.Table,
        operation: str,
        capability: str,
    ) -> NeutralReceipt:
        schema = arrow_schema_fingerprint(table.schema)
        content = arrow_content_fingerprint(table)
        source_revision = f"{self.identity.connector_id}-{operation}-revision"
        return NeutralReceipt(
            self.identity,
            CapabilityIdentity(capability, "1.0"),
            f"{self.identity.connector_id}-{operation}-operation",
            self._safe_uri(endpoint),
            TableMode.BASE,
            source_revision,
            schema,
            content,
            BaseConvention(ordinal_snapshot_id=source_revision),
            table.num_rows,
            1,
            vendor_receipt_ref=self._vendor_receipt_ref,
        )

    def read(self, endpoint: Endpoint, options: CliOptions) -> ArrowReadResult:
        self.read_calls.append(RecordedCliCall(endpoint, options))
        self._raise_failure("read")
        table = self._table if options.limit is None else self._table.slice(0, options.limit)
        return ArrowReadResult(
            table,
            self._receipt(endpoint, table, "read", "table.read.arrow"),
        )

    def inspect(self, endpoint: Endpoint, options: CliOptions) -> TableInspection:
        self.inspect_calls.append(RecordedCliCall(endpoint, options))
        self._raise_failure("inspect")
        table = self._table if options.limit is None else self._table.slice(0, options.limit)
        receipt = self._receipt(endpoint, table, "inspect", "table.inspect")
        return TableInspection(
            receipt.safe_uri,
            TableMode.BASE,
            tuple(table.column_names),
            receipt.schema_fingerprint,
            table.num_rows,
            receipt.coordinate_convention,
            {"provider": self.identity.connector_id},
        )

    def preflight_write(self, endpoint: Endpoint, options: CliOptions) -> None:
        self.preflight_calls.append(RecordedCliCall(endpoint, options))
        self._raise_failure("preflight")

    def write(
        self,
        endpoint: Endpoint,
        table: pa.Table,
        options: CliOptions,
    ) -> TableWriteResult:
        self.write_calls.append(RecordedCliCall(endpoint, options, table))
        self._raise_failure("write")
        return TableWriteResult(
            self._receipt(endpoint, table, "write", "table.write"),
            table.num_rows,
        )


@dataclass(frozen=True)
class CliRegistryBridge:
    registry: ConnectorRegistry
    cases: Mapping[str, Any]
    adapters: Mapping[str, Any]
    sources: Mapping[str, str]
    endpoints: Mapping[str, Endpoint]


def build_cli_registry_bridge(*case_names: str) -> CliRegistryBridge:
    from .cases import case

    names = case_names or (
        "google_sheets",
        "feishu_bitable",
        "maybesheet",
        "local_files",
    )
    registry = ConnectorRegistry()
    selected_cases: dict[str, Any] = {}
    adapters: dict[str, Any] = {}
    sources: dict[str, str] = {}
    endpoints: dict[str, Endpoint] = {}
    for name in names:
        connector_case = case(name)
        if name == "google_sheets":
            assert connector_case.http_fixture is not None
            adapter = GoogleSheetsAdapter(
                connector_case.connector,
                transport=connector_case.http_fixture.transport,
            )
        elif name == "feishu_bitable":
            assert connector_case.http_fixture is not None
            adapter = FeishuBitableAdapter(
                connector_case.connector,
                transport=connector_case.http_fixture.transport,
            )
        elif name == "maybesheet":
            adapter = MaybeSheetAdapter(connector_case.connector)
        elif name == "local_files":
            adapter = LocalAdapter()
        else:
            raise KeyError(f"connector case has no CLI bridge: {name}")
        source = connector_case.table_uri.value
        endpoint = parse_endpoint(source)
        registry.register(adapter)
        selected_cases[name] = connector_case
        adapters[name] = adapter
        sources[name] = source
        endpoints[name] = endpoint
    return CliRegistryBridge(registry, selected_cases, adapters, sources, endpoints)


@dataclass(frozen=True)
class UniversalFixtureBundle:
    csv_path: Path
    xlsx_path: Path
    sqlite_path: Path
    dbt_project_dir: Path


def build_fixture_bundle(root: Path) -> UniversalFixtureBundle:
    root.mkdir(parents=True, exist_ok=True)
    csv_path = root / "orders.csv"
    csv_path.write_text(
        "id,amount,note\n1,2.50,first\n2,,\n3,7.00,last\n",
        encoding="utf-8",
    )

    xlsx_path = root / "orders.xlsx"
    workbook = Workbook()
    workbook.active.title = "orders"
    workbook.active.append(["id", "amount", "note"])
    workbook.active.append(["1", 2.5, "first"])
    workbook.active.append(["2", None, None])
    workbook.active.append(["3", 7, "last"])
    refunds = workbook.create_sheet("refunds")
    refunds.append(["refund_id", "amount"])
    refunds.append(["r1", "1.00"])
    workbook.save(xlsx_path)

    sqlite_path = root / "fixture.sqlite"
    connection = sqlite3.connect(sqlite_path)
    connection.execute("create table orders (id text, amount text)")
    connection.executemany(
        "insert into orders values (?, ?)",
        [("a", "1.00"), ("b", None)],
    )
    connection.execute(
        'create table "main.table" (default_id text, label text)'
    )
    connection.executemany(
        'insert into "main.table" values (?, ?)',
        [("default-a", "default resource")],
    )
    connection.commit()
    connection.close()

    dbt_project_dir = root / "dbt_project"
    (dbt_project_dir / "models").mkdir(parents=True, exist_ok=True)
    (dbt_project_dir / "target").mkdir(parents=True, exist_ok=True)
    (dbt_project_dir / "dbt_project.yml").write_text(
        "name: fixture_project\nversion: '1.0'\nprofile: fixture\nconfig-version: 2\n",
        encoding="utf-8",
    )
    (dbt_project_dir / "models" / "orders.sql").write_text("select 1 as id\n", encoding="utf-8")
    return UniversalFixtureBundle(
        csv_path=csv_path,
        xlsx_path=xlsx_path,
        sqlite_path=sqlite_path,
        dbt_project_dir=dbt_project_dir,
    )


@dataclass(frozen=True)
class RecordedSqlCall:
    statement: str
    parameters: tuple[Any, ...]
    kind: str


_POSTGRES_SELECT_STATEMENTS = {
    "SELECT id, amount FROM orders",
    "SELECT id, amount FROM orders WHERE id = %s",
    "SELECT * FROM public.orders",
    "SELECT * FROM public.table",
}
_POSTGRES_EXECUTE_STATEMENTS = {
    "UPDATE public.orders SET amount = %s WHERE id = %s",
    'DROP TABLE IF EXISTS "public"."orders"',
    'CREATE TABLE IF NOT EXISTS "public"."orders" '
    '("id" TEXT, "amount" TEXT)',
    'CREATE TABLE "public"."orders" ("id" TEXT, "amount" TEXT)',
}
_POSTGRES_EXECUTEMANY_STATEMENTS = {
    'INSERT INTO "public"."orders" ("id", "amount") VALUES (%s, %s)',
}


class RecordingPostgresCursor:
    def __init__(
        self,
        rows: Iterable[tuple[Any, ...]],
        *,
        default_rows: Iterable[tuple[Any, ...]],
        connection_is_closed: Callable[[], bool],
        execution_failure: BaseException | None = None,
    ) -> None:
        self._description = [("id",), ("amount",)]
        self._rows = [tuple(row) for row in rows]
        self._default_rows = [tuple(row) for row in default_rows]
        self._remaining: list[tuple[Any, ...]] | None = None
        self._connection_is_closed = connection_is_closed
        self._execution_failure = execution_failure
        self.calls: list[RecordedSqlCall] = []
        self.fetchmany_sizes: list[int] = []
        self.description_reads = 0
        self.rowcount_reads = 0
        self.close_calls = 0
        self.closed = False
        self._rowcount = -1

    def _ensure_open(self) -> None:
        if self.closed:
            raise AssertionError("recorded DB-API used a closed cursor")
        if self._connection_is_closed():
            raise AssertionError("recorded DB-API used a closed connection")

    @property
    def description(self) -> list[tuple[str, ...]]:
        self._ensure_open()
        self.description_reads += 1
        return list(self._description)

    def execute(self, statement: str, parameters: tuple[Any, ...]) -> None:
        self._ensure_open()
        normalized_parameters = tuple(parameters)
        self.calls.append(
            RecordedSqlCall(statement, normalized_parameters, "execute")
        )
        if statement not in _POSTGRES_SELECT_STATEMENTS | _POSTGRES_EXECUTE_STATEMENTS:
            raise AssertionError(f"unexpected recorded SQL: {statement!r}")
        if self._execution_failure is not None:
            raise self._execution_failure
        if statement in _POSTGRES_SELECT_STATEMENTS:
            if statement == "SELECT * FROM public.table":
                self._description = [("default_id",), ("label",)]
                rows = list(self._default_rows)
            else:
                self._description = [("id",), ("amount",)]
                rows = list(self._rows)
            if statement == "SELECT id, amount FROM orders WHERE id = %s":
                if len(normalized_parameters) != 1:
                    raise AssertionError(
                        "recorded filtered SELECT requires exactly one parameter"
                    )
                rows = [row for row in rows if row[0] == normalized_parameters[0]]
            elif normalized_parameters:
                raise AssertionError(
                    f"recorded SELECT did not expect parameters: {statement!r}"
                )
            self._remaining = rows
            self._rowcount = len(rows)
            return
        if normalized_parameters and statement != (
            "UPDATE public.orders SET amount = %s WHERE id = %s"
        ):
            raise AssertionError(
                f"recorded statement did not expect parameters: {statement!r}"
            )
        if statement == 'CREATE TABLE "public"."orders" ("id" TEXT, "amount" TEXT)':
            raise RuntimeError('relation "public.orders" already exists')
        self._remaining = None
        self._rowcount = 1

    def executemany(self, statement: str, rows: Iterable[tuple[Any, ...]]) -> None:
        self._ensure_open()
        materialized = tuple(tuple(row) for row in rows)
        self.calls.append(RecordedSqlCall(statement, materialized, "executemany"))
        if statement not in _POSTGRES_EXECUTEMANY_STATEMENTS:
            raise AssertionError(f"unexpected recorded SQL: {statement!r}")
        if self._execution_failure is not None:
            raise self._execution_failure
        self._remaining = None
        self._rowcount = len(materialized)

    def fetchmany(self, size: int) -> list[tuple[Any, ...]]:
        self._ensure_open()
        if self._remaining is None:
            raise AssertionError("recorded fetchmany requires a preceding SELECT")
        if not isinstance(size, int) or size <= 0 or size > 1000:
            raise AssertionError(f"unexpected recorded fetchmany size: {size!r}")
        self.fetchmany_sizes.append(size)
        batch = self._remaining[:size]
        self._remaining = self._remaining[size:]
        return batch

    @property
    def rowcount(self) -> int:
        self._ensure_open()
        self.rowcount_reads += 1
        return self._rowcount

    def close(self) -> None:
        self._ensure_open()
        self.close_calls += 1
        self.closed = True


class RecordingPostgresConnection:
    def __init__(
        self,
        rows: Iterable[tuple[Any, ...]],
        *,
        default_rows: Iterable[tuple[Any, ...]],
        execution_failure: BaseException | None = None,
    ) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.cursor_calls = 0
        self.close_calls = 0
        self.closed = False
        self._rows = [tuple(row) for row in rows]
        self._default_rows = [tuple(row) for row in default_rows]
        self._execution_failure = execution_failure
        self.cursors: list[RecordingPostgresCursor] = []

    def _ensure_open(self) -> None:
        if self.closed:
            raise AssertionError("recorded DB-API used a closed connection")

    def cursor(self) -> RecordingPostgresCursor:
        self._ensure_open()
        self.cursor_calls += 1
        cursor = RecordingPostgresCursor(
            self._rows,
            default_rows=self._default_rows,
            connection_is_closed=lambda: self.closed,
            execution_failure=self._execution_failure,
        )
        self.cursors.append(cursor)
        return cursor

    def commit(self) -> None:
        self._ensure_open()
        self.commits += 1

    def rollback(self) -> None:
        self._ensure_open()
        self.rollbacks += 1

    def close(self) -> None:
        self._ensure_open()
        self.close_calls += 1
        self.closed = True


class RecordingPostgresFactory:
    def __init__(
        self,
        rows: Iterable[tuple[Any, ...]] = (("a", "1.00"), ("b", None)),
        *,
        default_rows: Iterable[tuple[Any, ...]] = (
            ("default-a", "default resource"),
        ),
        connection_failure: BaseException | None = None,
        execution_failure: BaseException | None = None,
    ) -> None:
        self._rows = [tuple(row) for row in rows]
        self._default_rows = [tuple(row) for row in default_rows]
        self._connection_failure = connection_failure
        self._execution_failure = execution_failure
        self.calls: list[dict[str, Any]] = []
        self.connections: list[RecordingPostgresConnection] = []

    def __call__(self, **kwargs: Any) -> RecordingPostgresConnection:
        recorded_kwargs = dict(kwargs)
        self.calls.append(recorded_kwargs)
        unexpected_keys = set(recorded_kwargs) - {
            "host",
            "port",
            "dbname",
            "user",
            "password",
            "sslmode",
        }
        if unexpected_keys:
            raise AssertionError(
                f"unexpected recorded connection arguments: {sorted(unexpected_keys)!r}"
            )
        if recorded_kwargs.get("host") != "fixture.local":
            raise AssertionError(
                f"recording Postgres factory refuses external host: {recorded_kwargs.get('host')!r}"
            )
        if self._connection_failure is not None:
            raise self._connection_failure
        connection = RecordingPostgresConnection(
            self._rows,
            default_rows=self._default_rows,
            execution_failure=self._execution_failure,
        )
        self.connections.append(connection)
        return connection


@dataclass(frozen=True)
class DatabaseProviderFixture:
    connection_factory: RecordingPostgresFactory


@dataclass(frozen=True)
class RecordedDbtCall:
    argv: tuple[str, ...]
    project_dir: Path


class RecordingDbtRunner:
    def __init__(
        self,
        *,
        credentials: Mapping[str, str] | None = None,
        failures: Mapping[str, BaseException] | None = None,
        expected_project_dir: Path | None = None,
    ) -> None:
        self.credentials = {
            str(key): str(value)
            for key, value in (
                {} if credentials is None else credentials
            ).items()
        }
        self._failures = dict(failures or {})
        self._expected_project_dir = (
            None if expected_project_dir is None else Path(expected_project_dir)
        )
        self.calls: list[RecordedDbtCall] = []
        self.readback_relations: list[str] = []

    def __call__(self, argv: tuple[str, ...], project_dir: Path) -> Mapping[str, Any]:
        recorded_project_dir = Path(project_dir)
        self.calls.append(RecordedDbtCall(tuple(argv), recorded_project_dir))
        if (
            self._expected_project_dir is not None
            and recorded_project_dir != self._expected_project_dir
        ):
            raise AssertionError(
                "recording dbt runner received an unexpected project directory: "
                f"{recorded_project_dir!s}"
            )
        if len(argv) < 2:
            raise KeyError(f"missing dbt operation in argv: {argv!r}")
        operation = argv[1]
        failure = self._failures.get(operation)
        if failure is not None:
            raise failure
        if operation == "compile":
            return {
                "artifacts": {"manifest.json": b'{"nodes":{"model.fixture.orders":{}}}'},
                "status": "completed",
                "artifact_refs": {"manifest.json": "manifest.json"},
                "adapter_type": "fixture",
            }
        if operation == "run":
            return {
                "status": "success",
                "run_results": b'{"results":[]}',
                "artifact_refs": {"run_results.json": "run_results.json"},
            }
        if operation == "cancel":
            return {"run_results": b'{"status":"cancelled"}'}
        raise KeyError(f"missing recorded dbt response for operation {operation!r}")

    def readback(self, relation: str) -> Mapping[str, Any]:
        self.readback_relations.append(str(relation))
        if relation != "analytics.orders":
            raise KeyError(f"missing recorded dbt readback for relation {relation!r}")
        return {
            "relation": "analytics.orders",
            "database": "fixture_warehouse",
            "schema": "analytics",
            "identifier": "orders",
            "row_count": 2,
        }


@dataclass(frozen=True)
class DbtProviderFixture:
    runner: RecordingDbtRunner
    project_dir: Path

    def recorded_call(self, argv: tuple[str, ...]) -> RecordedDbtCall:
        return RecordedDbtCall(tuple(argv), self.project_dir)
