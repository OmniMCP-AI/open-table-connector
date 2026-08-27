from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable, Mapping

from openpyxl import Workbook


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


@dataclass(frozen=True)
class RecordedSelection:
    fields: tuple[str, ...] = ()
    range: str | None = None


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
        self.selections: list[RecordedSelection] = []

    def record_selection(
        self,
        *,
        fields: Iterable[str] = (),
        range: str | None = None,
    ) -> None:
        self.selections.append(
            RecordedSelection(
                fields=tuple(str(field) for field in fields),
                range=range,
            )
        )

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
        self._response_indexes[method] = index + 1
        return _copy_payload(responses[index % len(responses)])


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
    connection.execute('create table "main.table" (id text, amount text)')
    connection.executemany(
        'insert into "main.table" values (?, ?)',
        [("a", "1.00"), ("b", None)],
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


class RecordingPostgresCursor:
    def __init__(self, rows: Iterable[tuple[Any, ...]]) -> None:
        self.description = [("id",), ("amount",)]
        self._rows = [tuple(row) for row in rows]
        self._remaining = list(self._rows)
        self.calls: list[RecordedSqlCall] = []
        self._rowcount = 0

    def execute(self, statement: str, parameters: tuple[Any, ...]) -> None:
        self.calls.append(RecordedSqlCall(statement, tuple(parameters), "execute"))
        if statement.lstrip().casefold().startswith(("select", "with")):
            self._remaining = list(self._rows)
            self._rowcount = len(self._rows)
        else:
            self._rowcount = 1

    def executemany(self, statement: str, rows: Iterable[tuple[Any, ...]]) -> None:
        materialized = [tuple(row) for row in rows]
        self.calls.append(RecordedSqlCall(statement, tuple(materialized), "executemany"))
        self._rowcount = len(materialized)

    def fetchmany(self, size: int) -> list[tuple[Any, ...]]:
        batch = self._remaining[:size]
        self._remaining = self._remaining[size:]
        return batch

    @property
    def rowcount(self) -> int:
        return self._rowcount


class RecordingPostgresConnection:
    def __init__(self, rows: Iterable[tuple[Any, ...]]) -> None:
        self.cursor_value = RecordingPostgresCursor(rows)
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self) -> RecordingPostgresCursor:
        return self.cursor_value

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True


class RecordingPostgresFactory:
    def __init__(self, rows: Iterable[tuple[Any, ...]] = (("a", "1.00"), ("b", None))) -> None:
        self._rows = [tuple(row) for row in rows]
        self.calls: list[dict[str, Any]] = []
        self.connections: list[RecordingPostgresConnection] = []

    def __call__(self, **kwargs: Any) -> RecordingPostgresConnection:
        self.calls.append(dict(kwargs))
        connection = RecordingPostgresConnection(self._rows)
        self.connections.append(connection)
        return connection


@dataclass(frozen=True)
class RecordedDbtCall:
    argv: tuple[str, ...]
    project_dir: Path


class RecordingDbtRunner:
    def __init__(self) -> None:
        self.calls: list[RecordedDbtCall] = []

    def __call__(self, argv: tuple[str, ...], project_dir: Path) -> Mapping[str, Any]:
        self.calls.append(RecordedDbtCall(tuple(argv), Path(project_dir)))
        if len(argv) < 2:
            raise KeyError(f"missing dbt operation in argv: {argv!r}")
        operation = argv[1]
        if operation == "compile":
            return {
                "artifacts": {"manifest.json": b'{"nodes":{"model.fixture.orders":{}}}'},
                "status": "completed",
                "artifact_refs": {"manifest.json": "manifest.json"},
            }
        if operation == "run":
            return {
                "status": "success",
                "run_results": b'{"results":[]}',
                "artifact_refs": {"run_results.json": "run_results.json"},
            }
        if operation == "cancel":
            return {"run_results": b"cancelled"}
        raise KeyError(f"missing recorded dbt response for operation {operation!r}")
