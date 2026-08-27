from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from types import MappingProxyType
from typing import Any, Callable, Mapping

import polars as pl

from open_connectors.contract import (
    ArrowReadResult,
    CapabilityIdentity,
    ConnectorIdentity,
    ExecutionRequest,
    InspectRequest,
    PolarsReadResult,
    ResolveContext,
    ResourceLimits,
    TableInspection,
    TableMode,
    TableURI,
    TableWriteRequest,
    TableWriteResult,
)
from open_connectors.dbt import DbtCompileRequest, DbtConnector, DbtPreparedOperation
from open_connectors.dbt.identity import (
    CONNECTOR_IDENTITY as DBT_IDENTITY,
    DBT_ARTIFACT_READ_CAPABILITY,
    DBT_CANCEL_CAPABILITY,
    DBT_COMPILE_CAPABILITY,
    DBT_RUN_CAPABILITY,
)
from open_connectors.feishu_bitable import (
    FeishuBitableConnector,
    FeishuBitableReadOptions,
    FeishuBitableTableReadRequest,
)
from open_connectors.feishu_bitable.connector import CAPABILITY_MANIFEST as FEISHU_MANIFEST
from open_connectors.google_sheets import (
    GoogleSheetsConnector,
    GoogleSheetsReadOptions,
    GoogleSheetsTableReadRequest,
)
from open_connectors.google_sheets.connector import CAPABILITY_MANIFEST as GOOGLE_MANIFEST
from open_connectors.local_files import LocalFilesConnector, LocalTableReadRequest
from open_connectors.maybesheet import MaybeSheetConnector, MaybeSheetReadRequest
from open_connectors.maybesheet.identity import (
    BASE_INSPECT_CAPABILITY,
    BASE_READ_CAPABILITY,
    CONNECTOR_IDENTITY as MAYBE_IDENTITY,
    SHEET_INSPECT_CAPABILITY,
    SHEET_READ_CAPABILITY,
    TABLE_WRITE_CAPABILITY as MAYBE_TABLE_WRITE_CAPABILITY,
)
from open_connectors.postgres import (
    CONNECTOR_IDENTITY as POSTGRES_IDENTITY,
    PostgresConnector,
    PostgresReadOptions,
    PostgresTableReadRequest,
    TABLE_EXECUTE_CAPABILITY as POSTGRES_EXECUTE_CAPABILITY,
    TABLE_INSPECT_CAPABILITY as POSTGRES_INSPECT_CAPABILITY,
    TABLE_READ_ARROW_CAPABILITY as POSTGRES_READ_ARROW_CAPABILITY,
    TABLE_READ_POLARS_CAPABILITY as POSTGRES_READ_POLARS_CAPABILITY,
    TABLE_WRITE_CAPABILITY as POSTGRES_WRITE_CAPABILITY,
)
from open_connectors.sqlite import (
    CONNECTOR_IDENTITY as SQLITE_IDENTITY,
    SQLiteConnector,
    SQLiteReadOptions,
    SQLiteTableReadRequest,
    TABLE_EXECUTE_CAPABILITY as SQLITE_EXECUTE_CAPABILITY,
    TABLE_INSPECT_CAPABILITY as SQLITE_INSPECT_CAPABILITY,
    TABLE_READ_ARROW_CAPABILITY as SQLITE_READ_ARROW_CAPABILITY,
    TABLE_READ_POLARS_CAPABILITY as SQLITE_READ_POLARS_CAPABILITY,
    TABLE_WRITE_CAPABILITY as SQLITE_WRITE_CAPABILITY,
)

from .fixtures import (
    RecordingDbtRunner,
    RecordingPostgresFactory,
    RecordingProcessClient,
    RecordingSheetsTransport,
    UniversalFixtureBundle,
    build_fixture_bundle,
)


@dataclass(frozen=True)
class CapabilityBinding:
    capability: str
    identity: CapabilityIdentity | None = None
    expected_mode: TableMode | None = None
    make_request: Callable[[ResourceLimits], object] | None = None
    read_arrow: Callable[[ResourceLimits], ArrowReadResult] | None = None
    read_polars: Callable[[ResourceLimits], PolarsReadResult] | None = None
    inspect: Callable[[ResourceLimits], TableInspection] | None = None
    write: Callable[[pl.DataFrame, str], TableWriteResult] | None = None
    invoke: Callable[[], Any] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.capability, str) or not self.capability.strip():
            raise ValueError("capability binding requires a non-empty capability ID")
        if self.identity is not None and self.identity.capability_id != self.capability:
            raise ValueError("capability binding identity does not match capability ID")
        if all(
            helper is None
            for helper in (
                self.make_request,
                self.read_arrow,
                self.read_polars,
                self.inspect,
                self.write,
                self.invoke,
            )
        ):
            raise ValueError(f"{self.capability} binding requires at least one helper")


@dataclass(frozen=True)
class ConnectorCase:
    name: str
    connector: object
    identity: ConnectorIdentity
    capabilities: frozenset[str]
    modes: frozenset[TableMode]
    schemes: frozenset[str]
    table_uri: TableURI
    make_read_request: Callable[[ResourceLimits], object] | None
    make_inspect_request: Callable[[ResourceLimits], object] | None
    make_write_request: Callable[[pl.DataFrame, str], TableWriteRequest] | None
    read_arrow: Callable[[ResourceLimits], ArrowReadResult] | None
    read_polars: Callable[[ResourceLimits], PolarsReadResult] | None
    inspect: Callable[[ResourceLimits], TableInspection] | None
    write: Callable[[pl.DataFrame, str], TableWriteResult] | None
    capability_bindings: Mapping[str, CapabilityBinding] = field(default_factory=dict)

    def __post_init__(self) -> None:
        connector_identity = getattr(self.connector, "identity", None)
        if connector_identity is not None and connector_identity != self.identity:
            raise ValueError(f"{self.name} identity does not match connector identity")
        manifest = getattr(self.connector, "manifest", None)
        if manifest is not None:
            expected_capabilities = frozenset(
                item.capability_id for item in manifest.capabilities
            )
            if expected_capabilities != self.capabilities:
                raise ValueError(f"{self.name} capabilities do not match manifest")
            if frozenset(manifest.modes) != self.modes:
                raise ValueError(f"{self.name} modes do not match manifest")
            if frozenset(manifest.uri_schemes) != self.schemes:
                raise ValueError(f"{self.name} schemes do not match manifest")

        bindings = dict(self.capability_bindings)
        if set(bindings) != set(self.capabilities):
            raise ValueError(f"{self.name} capability bindings do not match capabilities")
        for capability, binding in bindings.items():
            if binding.capability != capability:
                raise ValueError(f"{self.name} binding key does not match capability {capability}")
            if binding.expected_mode is not None and binding.expected_mode not in self.modes:
                raise ValueError(f"{self.name} binding mode does not match case modes")
        object.__setattr__(self, "capability_bindings", MappingProxyType(bindings))

    def capability_binding(self, capability: str) -> CapabilityBinding:
        try:
            return self.capability_bindings[capability]
        except KeyError as exc:
            raise KeyError(f"unknown connector case capability: {self.name}:{capability}") from exc


_FIXTURE_BUNDLE: UniversalFixtureBundle | None = None
_FIXTURE_DIRECTORY: TemporaryDirectory[str] | None = None


def configure_fixture_bundle(bundle: UniversalFixtureBundle) -> None:
    global _FIXTURE_BUNDLE
    _FIXTURE_BUNDLE = bundle


def _fixture_bundle() -> UniversalFixtureBundle:
    global _FIXTURE_BUNDLE, _FIXTURE_DIRECTORY
    if _FIXTURE_BUNDLE is None:
        if _FIXTURE_DIRECTORY is None:
            _FIXTURE_DIRECTORY = TemporaryDirectory(prefix="open-table-connectors-universal-")
        _FIXTURE_BUNDLE = build_fixture_bundle(Path(_FIXTURE_DIRECTORY.name))
    return _FIXTURE_BUNDLE


def _capabilities(*items: CapabilityIdentity) -> frozenset[str]:
    return frozenset(item.capability_id for item in items)


def _binding(
    capability: CapabilityIdentity | str,
    *,
    expected_mode: TableMode | None = None,
    make_request: Callable[[ResourceLimits], object] | None = None,
    read_arrow: Callable[[ResourceLimits], ArrowReadResult] | None = None,
    read_polars: Callable[[ResourceLimits], PolarsReadResult] | None = None,
    inspect: Callable[[ResourceLimits], TableInspection] | None = None,
    write: Callable[[pl.DataFrame, str], TableWriteResult] | None = None,
    invoke: Callable[[], Any] | None = None,
) -> CapabilityBinding:
    capability_id = capability if isinstance(capability, str) else capability.capability_id
    return CapabilityBinding(
        capability=capability_id,
        identity=capability if isinstance(capability, CapabilityIdentity) else None,
        expected_mode=expected_mode,
        make_request=make_request,
        read_arrow=read_arrow,
        read_polars=read_polars,
        inspect=inspect,
        write=write,
        invoke=invoke,
    )


def _local_case(bundle: UniversalFixtureBundle) -> ConnectorCase:
    connector = LocalFilesConnector()
    table_uri = TableURI(bundle.csv_path.as_uri())

    def make_read_request(resource_limits: ResourceLimits) -> LocalTableReadRequest:
        return LocalTableReadRequest(table_uri, resource_limits)

    def make_inspect_request(resource_limits: ResourceLimits) -> InspectRequest:
        return InspectRequest(table_uri, resource_limits)

    capability_bindings = {
        "uri.resolve": _binding(
            "uri.resolve",
            invoke=lambda: connector.resolve(table_uri, ResolveContext()),
        ),
        "table.read.arrow": _binding(
            "table.read.arrow",
            expected_mode=TableMode.SHEET,
            make_request=make_read_request,
            read_arrow=lambda resource_limits: connector.read_arrow(make_read_request(resource_limits)),
        ),
        "table.read.polars": _binding(
            "table.read.polars",
            expected_mode=TableMode.SHEET,
            make_request=make_read_request,
            read_polars=lambda resource_limits: connector.read_polars(make_read_request(resource_limits)),
        ),
        "table.inspect": _binding(
            "table.inspect",
            expected_mode=TableMode.SHEET,
            make_request=make_inspect_request,
            inspect=lambda resource_limits: connector.inspect(make_inspect_request(resource_limits)),
        ),
    }

    return ConnectorCase(
        name="local_files",
        connector=connector,
        identity=connector.identity,
        capabilities=_capabilities(*connector.manifest.capabilities),
        modes=frozenset(connector.manifest.modes),
        schemes=frozenset(connector.manifest.uri_schemes),
        table_uri=table_uri,
        make_read_request=make_read_request,
        make_inspect_request=make_inspect_request,
        make_write_request=None,
        read_arrow=capability_bindings["table.read.arrow"].read_arrow,
        read_polars=capability_bindings["table.read.polars"].read_polars,
        inspect=capability_bindings["table.inspect"].inspect,
        write=None,
        capability_bindings=capability_bindings,
    )


def _google_case(_bundle: UniversalFixtureBundle) -> ConnectorCase:
    transport = RecordingSheetsTransport(
        {
            "GET": {
                "range": "Orders!A1:B3",
                "values": [["id", "amount"], ["a", 1], ["b", 2]],
            },
            "PUT": {"updatedRange": "Orders!A1:B3", "updatedRows": 2, "updatedColumns": 2},
            "POST": {"updatedRange": "Orders!A1:B3", "updatedRows": 2, "updatedColumns": 2},
        }
    )
    connector = GoogleSheetsConnector(transport=transport, access_token="fixture-token")
    table_uri = TableURI("gsheets://fixture-spreadsheet/Orders")

    def make_read_request(resource_limits: ResourceLimits) -> GoogleSheetsTableReadRequest:
        return GoogleSheetsTableReadRequest(
            table_uri,
            resource_limits,
            GoogleSheetsReadOptions(sheet="Orders"),
        )

    def make_inspect_request(resource_limits: ResourceLimits) -> InspectRequest:
        return InspectRequest(table_uri, resource_limits)

    def make_write_request(frame: pl.DataFrame, if_exists: str) -> TableWriteRequest:
        return TableWriteRequest(table_uri, frame, if_exists=if_exists, table="Orders")

    capability_bindings = {
        "uri.resolve": _binding(
            "uri.resolve",
            invoke=lambda: connector.resolve(table_uri, ResolveContext()),
        ),
        "table.read.arrow": _binding(
            "table.read.arrow",
            expected_mode=TableMode.SHEET,
            make_request=make_read_request,
            read_arrow=lambda resource_limits: connector.read_arrow(make_read_request(resource_limits)),
        ),
        "table.read.polars": _binding(
            "table.read.polars",
            expected_mode=TableMode.SHEET,
            make_request=make_read_request,
            read_polars=lambda resource_limits: connector.read_polars(make_read_request(resource_limits)),
        ),
        "table.inspect": _binding(
            "table.inspect",
            expected_mode=TableMode.SHEET,
            make_request=make_inspect_request,
            inspect=lambda resource_limits: connector.inspect(make_inspect_request(resource_limits)),
        ),
        "table.write": _binding(
            "table.write",
            expected_mode=TableMode.SHEET,
            write=lambda frame, if_exists: connector.write(make_write_request(frame, if_exists)),
        ),
    }

    return ConnectorCase(
        name="google_sheets",
        connector=connector,
        identity=GOOGLE_MANIFEST.connector,
        capabilities=_capabilities(*GOOGLE_MANIFEST.capabilities),
        modes=frozenset(GOOGLE_MANIFEST.modes),
        schemes=frozenset(GOOGLE_MANIFEST.uri_schemes),
        table_uri=table_uri,
        make_read_request=make_read_request,
        make_inspect_request=make_inspect_request,
        make_write_request=make_write_request,
        read_arrow=capability_bindings["table.read.arrow"].read_arrow,
        read_polars=capability_bindings["table.read.polars"].read_polars,
        inspect=capability_bindings["table.inspect"].inspect,
        write=capability_bindings["table.write"].write,
        capability_bindings=capability_bindings,
    )


def _feishu_case(_bundle: UniversalFixtureBundle) -> ConnectorCase:
    transport = RecordingSheetsTransport(
        {
            "GET": {
                "code": 0,
                "data": {
                    "items": [
                        {"record_id": "rec_1", "fields": {"name": "Ada", "score": 10}},
                        {"record_id": "rec_2", "fields": {"name": "Lin", "score": 9}},
                    ],
                    "has_more": False,
                },
            },
            "POST": {"code": 0, "data": {"records": [{"record_id": "rec_3"}]}},
        }
    )
    connector = FeishuBitableConnector(
        transport=transport,
        tenant_access_token="fixture-token",
    )
    table_uri = TableURI("feishu://fixture-app/orders")

    def make_read_request(resource_limits: ResourceLimits) -> FeishuBitableTableReadRequest:
        return FeishuBitableTableReadRequest(
            table_uri,
            resource_limits,
            FeishuBitableReadOptions(),
        )

    def make_inspect_request(resource_limits: ResourceLimits) -> InspectRequest:
        return InspectRequest(table_uri, resource_limits)

    def make_write_request(frame: pl.DataFrame, if_exists: str) -> TableWriteRequest:
        return TableWriteRequest(table_uri, frame, if_exists=if_exists)

    capability_bindings = {
        "uri.resolve": _binding(
            "uri.resolve",
            invoke=lambda: connector.resolve(table_uri, ResolveContext()),
        ),
        "table.read.arrow": _binding(
            "table.read.arrow",
            expected_mode=TableMode.BASE,
            make_request=make_read_request,
            read_arrow=lambda resource_limits: connector.read_arrow(make_read_request(resource_limits)),
        ),
        "table.read.polars": _binding(
            "table.read.polars",
            expected_mode=TableMode.BASE,
            make_request=make_read_request,
            read_polars=lambda resource_limits: connector.read_polars(make_read_request(resource_limits)),
        ),
        "table.inspect": _binding(
            "table.inspect",
            expected_mode=TableMode.BASE,
            make_request=make_inspect_request,
            inspect=lambda resource_limits: connector.inspect(make_inspect_request(resource_limits)),
        ),
        "table.write": _binding(
            "table.write",
            expected_mode=TableMode.BASE,
            write=lambda frame, if_exists: connector.write(make_write_request(frame, if_exists)),
        ),
    }

    return ConnectorCase(
        name="feishu_bitable",
        connector=connector,
        identity=FEISHU_MANIFEST.connector,
        capabilities=_capabilities(*FEISHU_MANIFEST.capabilities),
        modes=frozenset(FEISHU_MANIFEST.modes),
        schemes=frozenset(FEISHU_MANIFEST.uri_schemes),
        table_uri=table_uri,
        make_read_request=make_read_request,
        make_inspect_request=make_inspect_request,
        make_write_request=make_write_request,
        read_arrow=capability_bindings["table.read.arrow"].read_arrow,
        read_polars=capability_bindings["table.read.polars"].read_polars,
        inspect=capability_bindings["table.inspect"].inspect,
        write=capability_bindings["table.write"].write,
        capability_bindings=capability_bindings,
    )


def _maybe_case(_bundle: UniversalFixtureBundle) -> ConnectorCase:
    process = RecordingProcessClient(
        {
            "db-table:read": {
                "rows": [{"id": "1", "amount": "2.50"}],
                "source_revision": "fixture-maybe-base-rev",
                "receipt_id": "fixture-base-read-ref",
            },
            "excel-worksheet:read": {
                "rows": [{"id": "sheet-1", "amount": "7.00"}],
                "source_revision": "fixture-maybe-sheet-rev",
                "receipt_id": "fixture-sheet-read-ref",
            },
            "db-table:write": {"rows_written": 1, "receipt_id": "fixture-write-ref"},
        }
    )
    connector = MaybeSheetConnector(process)
    table_uri = TableURI("https://www.maybe.ai/docs/spreadsheets/d/fixture-doc")

    def make_base_read_request(resource_limits: ResourceLimits) -> MaybeSheetReadRequest:
        return MaybeSheetReadRequest(table_uri, TableMode.BASE, "R_orders", resource_limits)

    def make_sheet_read_request(resource_limits: ResourceLimits) -> MaybeSheetReadRequest:
        return MaybeSheetReadRequest(table_uri, TableMode.SHEET, "Orders", resource_limits)

    def make_write_request(frame: pl.DataFrame, if_exists: str) -> TableWriteRequest:
        return TableWriteRequest(table_uri, frame, if_exists=if_exists, table="R_orders")

    capability_bindings = {
        "base.read": _binding(
            BASE_READ_CAPABILITY,
            expected_mode=TableMode.BASE,
            make_request=make_base_read_request,
            read_arrow=lambda resource_limits: connector.read_arrow(make_base_read_request(resource_limits)),
            read_polars=lambda resource_limits: connector.read_polars(make_base_read_request(resource_limits)),
        ),
        "base.inspect": _binding(
            BASE_INSPECT_CAPABILITY,
            expected_mode=TableMode.BASE,
            make_request=make_base_read_request,
            inspect=lambda resource_limits: connector.inspect(make_base_read_request(resource_limits)),
        ),
        "sheet.read": _binding(
            SHEET_READ_CAPABILITY,
            expected_mode=TableMode.SHEET,
            make_request=make_sheet_read_request,
            read_arrow=lambda resource_limits: connector.read_arrow(make_sheet_read_request(resource_limits)),
            read_polars=lambda resource_limits: connector.read_polars(make_sheet_read_request(resource_limits)),
        ),
        "sheet.inspect": _binding(
            SHEET_INSPECT_CAPABILITY,
            expected_mode=TableMode.SHEET,
            make_request=make_sheet_read_request,
            inspect=lambda resource_limits: connector.inspect(make_sheet_read_request(resource_limits)),
        ),
        "table.write": _binding(
            MAYBE_TABLE_WRITE_CAPABILITY,
            expected_mode=TableMode.BASE,
            write=lambda frame, if_exists: connector.write(make_write_request(frame, if_exists)),
        ),
    }

    return ConnectorCase(
        name="maybesheet",
        connector=connector,
        identity=MAYBE_IDENTITY,
        capabilities=_capabilities(
            BASE_READ_CAPABILITY,
            BASE_INSPECT_CAPABILITY,
            SHEET_READ_CAPABILITY,
            SHEET_INSPECT_CAPABILITY,
            MAYBE_TABLE_WRITE_CAPABILITY,
        ),
        modes=frozenset({TableMode.BASE, TableMode.SHEET}),
        schemes=frozenset({"https", "maybe"}),
        table_uri=table_uri,
        make_read_request=make_base_read_request,
        make_inspect_request=make_base_read_request,
        make_write_request=make_write_request,
        read_arrow=capability_bindings["base.read"].read_arrow,
        read_polars=capability_bindings["base.read"].read_polars,
        inspect=capability_bindings["base.inspect"].inspect,
        write=capability_bindings["table.write"].write,
        capability_bindings=capability_bindings,
    )


def _sqlite_case(bundle: UniversalFixtureBundle) -> ConnectorCase:
    connector = SQLiteConnector(connection_factory=sqlite3.connect)
    table_uri = TableURI(f"sqlite://{bundle.sqlite_path.as_posix()}")

    def make_read_request(resource_limits: ResourceLimits) -> SQLiteTableReadRequest:
        return SQLiteTableReadRequest(
            table_uri,
            resource_limits,
            SQLiteReadOptions(table="orders", record_id_field="id"),
        )

    def make_inspect_request(resource_limits: ResourceLimits) -> InspectRequest:
        return InspectRequest(table_uri, resource_limits)

    def make_write_request(frame: pl.DataFrame, if_exists: str) -> TableWriteRequest:
        return TableWriteRequest(table_uri, frame, if_exists=if_exists, table="orders")

    capability_bindings = {
        "table.read.arrow": _binding(
            SQLITE_READ_ARROW_CAPABILITY,
            expected_mode=TableMode.BASE,
            make_request=make_read_request,
            read_arrow=lambda resource_limits: connector.read_arrow(make_read_request(resource_limits)),
        ),
        "table.read.polars": _binding(
            SQLITE_READ_POLARS_CAPABILITY,
            expected_mode=TableMode.BASE,
            make_request=make_read_request,
            read_polars=lambda resource_limits: connector.read_polars(make_read_request(resource_limits)),
        ),
        "table.inspect": _binding(
            SQLITE_INSPECT_CAPABILITY,
            expected_mode=TableMode.BASE,
            make_request=make_inspect_request,
            inspect=lambda resource_limits: connector.inspect(make_inspect_request(resource_limits)),
        ),
        "table.execute": _binding(
            SQLITE_EXECUTE_CAPABILITY,
            invoke=lambda: connector.execute(
                ExecutionRequest(
                    table_uri,
                    "UPDATE orders SET amount = ? WHERE id = ?",
                    ("2.00", "a"),
                )
            ),
        ),
        "table.write": _binding(
            SQLITE_WRITE_CAPABILITY,
            expected_mode=TableMode.BASE,
            write=lambda frame, if_exists: connector.write(make_write_request(frame, if_exists)),
        ),
    }

    return ConnectorCase(
        name="sqlite",
        connector=connector,
        identity=SQLITE_IDENTITY,
        capabilities=_capabilities(
            SQLITE_READ_ARROW_CAPABILITY,
            SQLITE_READ_POLARS_CAPABILITY,
            SQLITE_INSPECT_CAPABILITY,
            SQLITE_EXECUTE_CAPABILITY,
            SQLITE_WRITE_CAPABILITY,
        ),
        modes=frozenset({TableMode.BASE}),
        schemes=frozenset({"sqlite"}),
        table_uri=table_uri,
        make_read_request=make_read_request,
        make_inspect_request=make_inspect_request,
        make_write_request=make_write_request,
        read_arrow=capability_bindings["table.read.arrow"].read_arrow,
        read_polars=capability_bindings["table.read.polars"].read_polars,
        inspect=capability_bindings["table.inspect"].inspect,
        write=capability_bindings["table.write"].write,
        capability_bindings=capability_bindings,
    )


def _postgres_case(_bundle: UniversalFixtureBundle) -> ConnectorCase:
    factory = RecordingPostgresFactory()
    connector = PostgresConnector(connection_factory=factory)
    table_uri = TableURI("postgres://fixture.local/analytics")

    def make_read_request(resource_limits: ResourceLimits) -> PostgresTableReadRequest:
        return PostgresTableReadRequest(
            table_uri,
            resource_limits=resource_limits,
            options=PostgresReadOptions(
                query="SELECT id, amount FROM orders",
                key_fields=("id",),
            ),
        )

    def make_inspect_request(resource_limits: ResourceLimits) -> InspectRequest:
        return InspectRequest(table_uri, resource_limits)

    def make_write_request(frame: pl.DataFrame, if_exists: str) -> TableWriteRequest:
        return TableWriteRequest(table_uri, frame, if_exists=if_exists, table="public.orders")

    capability_bindings = {
        "table.read.arrow": _binding(
            POSTGRES_READ_ARROW_CAPABILITY,
            expected_mode=TableMode.BASE,
            make_request=make_read_request,
            read_arrow=lambda resource_limits: connector.read_arrow(make_read_request(resource_limits)),
        ),
        "table.read.polars": _binding(
            POSTGRES_READ_POLARS_CAPABILITY,
            expected_mode=TableMode.BASE,
            make_request=make_read_request,
            read_polars=lambda resource_limits: connector.read_polars(make_read_request(resource_limits)),
        ),
        "table.inspect": _binding(
            POSTGRES_INSPECT_CAPABILITY,
            expected_mode=TableMode.BASE,
            make_request=make_inspect_request,
            inspect=lambda resource_limits: connector.inspect(make_inspect_request(resource_limits)),
        ),
        "table.execute": _binding(
            POSTGRES_EXECUTE_CAPABILITY,
            invoke=lambda: connector.execute(
                ExecutionRequest(
                    table_uri,
                    "UPDATE public.orders SET amount = %s WHERE id = %s",
                    ("2.00", "a"),
                )
            ),
        ),
        "table.write": _binding(
            POSTGRES_WRITE_CAPABILITY,
            expected_mode=TableMode.BASE,
            write=lambda frame, if_exists: connector.write(make_write_request(frame, if_exists)),
        ),
    }

    return ConnectorCase(
        name="postgres",
        connector=connector,
        identity=POSTGRES_IDENTITY,
        capabilities=_capabilities(
            POSTGRES_READ_ARROW_CAPABILITY,
            POSTGRES_READ_POLARS_CAPABILITY,
            POSTGRES_INSPECT_CAPABILITY,
            POSTGRES_EXECUTE_CAPABILITY,
            POSTGRES_WRITE_CAPABILITY,
        ),
        modes=frozenset({TableMode.BASE}),
        schemes=frozenset({"postgres", "postgresql"}),
        table_uri=table_uri,
        make_read_request=make_read_request,
        make_inspect_request=make_inspect_request,
        make_write_request=make_write_request,
        read_arrow=capability_bindings["table.read.arrow"].read_arrow,
        read_polars=capability_bindings["table.read.polars"].read_polars,
        inspect=capability_bindings["table.inspect"].inspect,
        write=capability_bindings["table.write"].write,
        capability_bindings=capability_bindings,
    )


def _dbt_compile_operation(connector: DbtConnector, project_dir: Path) -> DbtPreparedOperation:
    return connector.compile(
        DbtCompileRequest(
            project_dir=project_dir,
            select=("model.fixture.orders",),
            target="fixture",
            vars={"currency": "USD"},
        )
    )


def _dbt_case(bundle: UniversalFixtureBundle) -> ConnectorCase:
    runner = RecordingDbtRunner()
    connector = DbtConnector(runner)
    table_uri = TableURI(bundle.dbt_project_dir.as_uri())

    capability_bindings = {
        "dbt.compile": _binding(
            DBT_COMPILE_CAPABILITY,
            invoke=lambda: _dbt_compile_operation(connector, bundle.dbt_project_dir),
        ),
        "dbt.run": _binding(
            DBT_RUN_CAPABILITY,
            invoke=lambda: connector.run(_dbt_compile_operation(connector, bundle.dbt_project_dir)),
        ),
        "dbt.cancel": _binding(
            DBT_CANCEL_CAPABILITY,
            invoke=lambda: connector.cancel(_dbt_compile_operation(connector, bundle.dbt_project_dir)),
        ),
        "dbt.artifact.read": _binding(
            DBT_ARTIFACT_READ_CAPABILITY,
            invoke=lambda: connector.read_artifact(
                _dbt_compile_operation(connector, bundle.dbt_project_dir),
                "manifest.json",
            ),
        ),
    }

    return ConnectorCase(
        name="dbt",
        connector=connector,
        identity=DBT_IDENTITY,
        capabilities=_capabilities(
            DBT_COMPILE_CAPABILITY,
            DBT_RUN_CAPABILITY,
            DBT_CANCEL_CAPABILITY,
            DBT_ARTIFACT_READ_CAPABILITY,
        ),
        modes=frozenset(),
        schemes=frozenset({"file"}),
        table_uri=table_uri,
        make_read_request=None,
        make_inspect_request=None,
        make_write_request=None,
        read_arrow=None,
        read_polars=None,
        inspect=None,
        write=None,
        capability_bindings=capability_bindings,
    )


def _all_cases(bundle: UniversalFixtureBundle) -> tuple[ConnectorCase, ...]:
    return (
        _local_case(bundle),
        _google_case(bundle),
        _feishu_case(bundle),
        _maybe_case(bundle),
        _sqlite_case(bundle),
        _postgres_case(bundle),
        _dbt_case(bundle),
    )


def all_cases() -> tuple[ConnectorCase, ...]:
    return _all_cases(_fixture_bundle())


def case(name: str) -> ConnectorCase:
    for item in all_cases():
        if item.name == name:
            return item
    raise KeyError(f"unknown connector case: {name}")


def cases_with(capability: str) -> tuple[ConnectorCase, ...]:
    return tuple(item for item in all_cases() if capability in item.capabilities)
