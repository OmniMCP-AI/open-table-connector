"""Portable SQL preparation and local execution."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from math import ceil
from time import monotonic_ns
from typing import TYPE_CHECKING, Any

import polars as pl
import sqlglot
from open_table_connector.contract import (
    ArrowReadResult,
    ConnectorError,
    ConnectorErrorCode,
    ExecutionRequest,
    ExecutionResult,
    ResourceLimits,
    TableURI,
)
from sqlglot import exp

from .query import Query, QueryLane, SqlResourceLimits
from .result import (
    CommitState,
    ErrorCode,
    ErrorInfo,
    OperationResult,
    OTCError,
    Outcome,
    Receipt,
    ReconciliationReference,
    VerificationState,
)

if TYPE_CHECKING:
    from .client import Client


class SqlResourceLimitError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class NativeSqlResourceLimits:
    max_rows: int = 100_000
    max_bytes: int = 128 * 1024 * 1024
    max_duration_ms: int = 30_000

    def __post_init__(self) -> None:
        for field_name in ("max_rows", "max_bytes", "max_duration_ms"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{field_name} must be a positive integer")

    def to_wire(self) -> dict[str, int]:
        return asdict(self)


def _frame_bytes(frame: pl.DataFrame) -> int:
    return int(frame.estimated_size())


def _check_limit(observed: int, allowed: int, label: str) -> None:
    if observed > allowed:
        raise SqlResourceLimitError(f"query exceeded {label}")


def _required_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


@dataclass(frozen=True, slots=True)
class _ColumnRef:
    source_name: str
    column_name: str

    @property
    def physical_name(self) -> str:
        return f"{self.source_name}__{self.column_name}"


@dataclass(frozen=True, slots=True)
class _LiteralValue:
    value: Any


@dataclass(frozen=True, slots=True)
class _ParameterRef:
    name: str


@dataclass(frozen=True, slots=True)
class _Predicate:
    operator: str
    left: Any
    right: Any


@dataclass(frozen=True, slots=True)
class _AggregateExpr:
    function: str
    argument: _ColumnRef


@dataclass(frozen=True, slots=True)
class _Projection:
    expression: Any
    output_name: str


@dataclass(frozen=True, slots=True)
class _JoinPlan:
    kind: str
    source_name: str
    left_key: _ColumnRef
    right_key: _ColumnRef


@dataclass(frozen=True, slots=True)
class _OrderKey:
    expression: Any
    descending: bool


@dataclass(frozen=True, slots=True)
class _RelationalPlan:
    base_source: str
    projections: tuple[_Projection, ...]
    joins: tuple[_JoinPlan, ...]
    where: _Predicate | None
    group_by: tuple[_ColumnRef, ...]
    order_by: tuple[_OrderKey, ...]
    limit: int | None


def _invalid_sql(message: str, **details: object) -> OTCError:
    result = OperationResult[None](
        value=None,
        outcome=Outcome.REJECTED,
        commit=CommitState.NOT_STARTED,
        verification=VerificationState.SKIPPED,
        receipts=(),
        error=ErrorInfo(code=ErrorCode.INVALID_SQL, message=message, safe_details=details),
    )
    return OTCError(message, result)


def _native_error(
    message: str,
    code: ErrorCode,
    *,
    dispatched: bool = False,
    reconciliation: ReconciliationReference | None = None,
    **details: object,
) -> OTCError:
    result = OperationResult[None](
        value=None,
        outcome=Outcome.UNKNOWN if dispatched else Outcome.REJECTED,
        commit=CommitState.UNKNOWN if dispatched else CommitState.NOT_STARTED,
        verification=(VerificationState.UNAVAILABLE if dispatched else VerificationState.SKIPPED),
        receipts=(),
        error=ErrorInfo(
            code=code,
            message=message,
            safe_details=details,
            reconciliation=reconciliation,
        ),
    )
    return OTCError(message, result)


def _connector_error_code(code: ConnectorErrorCode) -> ErrorCode:
    return {
        ConnectorErrorCode.UNSUPPORTED_CAPABILITY: ErrorCode.UNSUPPORTED_CAPABILITY,
        ConnectorErrorCode.AUTHENTICATION: ErrorCode.AUTHENTICATION,
        ConnectorErrorCode.TIMEOUT: ErrorCode.TIMEOUT,
        ConnectorErrorCode.CANCELLED: ErrorCode.CANCELLED,
        ConnectorErrorCode.RESOURCE_LIMIT_EXCEEDED: ErrorCode.RESOURCE_LIMIT,
        ConnectorErrorCode.IDEMPOTENCY_CONFLICT: ErrorCode.IDEMPOTENCY_CONFLICT,
        ConnectorErrorCode.CONFIGURATION: ErrorCode.INVALID_CONFIGURATION,
    }.get(code, ErrorCode.EXECUTION_FAILED)


def _statement_hash(statement: str) -> str:
    normalized = sqlglot.parse_one(statement).sql(pretty=False)
    return "sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _single_native_statement(statement: str) -> exp.Expression:
    try:
        parsed = sqlglot.parse(statement)
    except sqlglot.errors.ParseError as exc:
        raise _invalid_sql("provider-native SQL could not be parsed safely") from exc
    if len(parsed) != 1:
        raise _invalid_sql("provider-native SQL accepts exactly one statement")
    return parsed[0]


def _validate_native_read_only(statement: str) -> None:
    expression = _single_native_statement(statement)
    if not isinstance(expression, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        raise _invalid_sql("native query accepts only a read-only SELECT")
    if any(isinstance(node, (exp.DML, exp.DDL)) for node in expression.walk()):
        raise _invalid_sql("native query rejects nested mutating statements")
    if expression.args.get("into") is not None or next(expression.find_all(exp.Lock), None):
        raise _invalid_sql("native query rejects SELECT INTO and locking clauses")
    volatile_names = {
        "current_date",
        "current_time",
        "current_timestamp",
        "now",
        "random",
        "rand",
        "uuid",
        "uuid_generate_v4",
    }
    safe_anonymous_functions = {
        "abs",
        "avg",
        "coalesce",
        "count",
        "length",
        "lower",
        "max",
        "min",
        "nullif",
        "round",
        "sum",
        "trim",
        "upper",
    }
    for function in expression.find_all(exp.Func):
        function_name = function.sql_name().casefold()
        if function_name in volatile_names:
            raise _invalid_sql("native query rejects volatile functions")
        if isinstance(function, exp.Anonymous) and function.name.casefold() not in (
            safe_anonymous_functions
        ):
            raise _invalid_sql("native query rejects unproven provider functions")


def _validate_native_execute(statement: str) -> None:
    expression = _single_native_statement(statement)
    if isinstance(expression, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        raise _invalid_sql("native SELECT statements must use native.query()")


def _native_parameters(parameters: Sequence[Any] | None) -> tuple[Any, ...]:
    if parameters is None:
        return ()
    if isinstance(parameters, (str, bytes, bytearray)):
        raise TypeError("native SQL parameters must be a finite sequence")
    return tuple(parameters)


class NativeSql:
    def __init__(self, client: Client, target: str | TableURI) -> None:
        self._client = client
        self._target = target if isinstance(target, TableURI) else TableURI(target)

    def query(
        self,
        statement: str,
        *,
        parameters: Sequence[Any] | None = None,
        limits: NativeSqlResourceLimits | None = None,
    ) -> OperationResult[pl.DataFrame]:
        self._client._assert_open()
        _validate_native_read_only(statement)
        effective = limits or NativeSqlResourceLimits()
        connector = self._client._registry.connector_for(self._target.value)
        read_native_sql = getattr(connector, "read_native_sql", None)
        if not callable(read_native_sql):
            raise _native_error(
                "connector does not support provider-native read-only SQL",
                ErrorCode.UNSUPPORTED_CAPABILITY,
            )
        request = ExecutionRequest(
            uri=self._target,
            statement=statement,
            parameters=_native_parameters(parameters),
            resource_limits=ResourceLimits(
                max_rows=effective.max_rows + 1,
                max_bytes=effective.max_bytes,
                timeout_seconds=max(1, ceil(effective.max_duration_ms / 1000)),
            ),
        )
        started_ns = monotonic_ns()
        try:
            result = read_native_sql(request)
        except ConnectorError as exc:
            raise _native_error(
                exc.message,
                _connector_error_code(exc.code),
                **dict(exc.safe_details),
            ) from exc
        if not isinstance(result, ArrowReadResult):
            raise _native_error(
                "connector returned an invalid native query result",
                ErrorCode.PROTOCOL_FAILURE,
            )
        frame = pl.from_arrow(result.table)
        elapsed_ms = (monotonic_ns() - started_ns) // 1_000_000
        if frame.height > effective.max_rows:
            raise _native_error("native query exceeded max_rows", ErrorCode.RESOURCE_LIMIT)
        if int(frame.estimated_size()) > effective.max_bytes:
            raise _native_error("native query exceeded max_bytes", ErrorCode.RESOURCE_LIMIT)
        if elapsed_ms > effective.max_duration_ms:
            raise _native_error("native query exceeded max_duration_ms", ErrorCode.TIMEOUT)
        from .connector import _receipt_from_legacy

        physical = _receipt_from_legacy(result.receipt)
        evidence = Receipt(
            kind="native-sql-query",
            operation="native.sql.query",
            connector_id=getattr(getattr(connector, "identity", None), "connector_id", None),
            capability="native.sql.query/1.0",
            safe_target=self._target,
            details={
                "statement_hash": _statement_hash(statement),
                "effective_limits": effective.to_wire(),
                "observed_rows": frame.height,
                "observed_bytes": int(frame.estimated_size()),
                "elapsed_ms": elapsed_ms,
                "provider_operation_id": result.receipt.operation_id,
            },
        )
        return OperationResult(
            value=frame,
            outcome=Outcome.SUCCEEDED,
            commit=CommitState.NOT_APPLICABLE,
            verification=VerificationState.PASSED,
            receipts=(physical, evidence),
        )

    def execute(
        self,
        statement: str,
        *,
        parameters: Sequence[Any] | None = None,
        limits: NativeSqlResourceLimits | None = None,
        idempotency_key: str,
    ) -> OperationResult[int]:
        self._client._assert_open()
        _validate_native_execute(statement)
        operation_key = _required_text(idempotency_key, "idempotency_key")
        effective = limits or NativeSqlResourceLimits()
        connector = self._client._registry.connector_for(self._target.value)
        execute = getattr(connector, "execute", None)
        if not callable(execute):
            raise _native_error(
                "connector does not support provider-native SQL execution",
                ErrorCode.UNSUPPORTED_CAPABILITY,
            )
        bound_parameters = _native_parameters(parameters)
        request = ExecutionRequest(
            uri=self._target,
            statement=statement,
            parameters=bound_parameters,
            resource_limits=ResourceLimits(
                max_rows=effective.max_rows,
                max_bytes=effective.max_bytes,
                timeout_seconds=max(1, ceil(effective.max_duration_ms / 1000)),
            ),
        )
        started_ns = monotonic_ns()
        try:
            result = execute(request)
        except ConnectorError as exc:
            reconciliation = ReconciliationReference(
                operation_id=_statement_hash(statement),
                connector_id=getattr(getattr(connector, "identity", None), "connector_id", None),
                idempotency_key=operation_key,
            )
            raise _native_error(
                exc.message,
                ErrorCode.UNCERTAIN_MUTATION,
                dispatched=True,
                reconciliation=reconciliation,
                provider_code=exc.code.value,
                **dict(exc.safe_details),
            ) from exc
        if not isinstance(result, ExecutionResult):
            raise _native_error(
                "connector returned an invalid native execution result",
                ErrorCode.PROTOCOL_FAILURE,
                dispatched=True,
                reconciliation=ReconciliationReference(
                    operation_id=_statement_hash(statement),
                    idempotency_key=operation_key,
                ),
            )
        elapsed_ms = (monotonic_ns() - started_ns) // 1_000_000
        if result.status.casefold() != "completed":
            raise _native_error(
                "native execution outcome is uncertain",
                ErrorCode.UNCERTAIN_MUTATION,
                dispatched=True,
                reconciliation=ReconciliationReference(
                    operation_id=result.operation_id,
                    connector_id=getattr(
                        getattr(connector, "identity", None), "connector_id", None
                    ),
                    idempotency_key=operation_key,
                ),
                provider_status=result.status,
            )
        if elapsed_ms > effective.max_duration_ms:
            raise _native_error(
                "native execution exceeded max_duration_ms after dispatch",
                ErrorCode.UNCERTAIN_MUTATION,
                dispatched=True,
                reconciliation=ReconciliationReference(
                    operation_id=result.operation_id,
                    idempotency_key=operation_key,
                ),
            )
        affected_rows = 0 if result.affected_rows is None else result.affected_rows
        evidence = Receipt(
            kind="native-sql-execution",
            operation="native.sql.execute",
            connector_id=getattr(getattr(connector, "identity", None), "connector_id", None),
            capability="native.sql.execute/1.0",
            safe_target=self._target,
            details={
                "statement_hash": _statement_hash(statement),
                "idempotency_key": operation_key,
                "provider_operation_id": result.operation_id,
                "provider_status": result.status,
                "affected_rows": result.affected_rows,
                "effective_limits": effective.to_wire(),
                "elapsed_ms": elapsed_ms,
                "provider_receipt_present": result.receipt is not None,
            },
        )
        receipts = (evidence,)
        if result.receipt is not None:
            from .connector import _receipt_from_legacy

            receipts = (_receipt_from_legacy(result.receipt), evidence)
        return OperationResult(
            value=affected_rows,
            outcome=Outcome.SUCCEEDED,
            commit=CommitState.COMMITTED,
            verification=(
                VerificationState.PASSED
                if result.receipt is not None
                else VerificationState.UNAVAILABLE
            ),
            receipts=receipts,
        )


def _parse_one(statement: str) -> exp.Expression:
    parsed = sqlglot.parse(statement)
    if len(parsed) != 1:
        raise ValueError("portable SQL accepts exactly one statement")
    return parsed[0]


def _table_name(table: exp.Table) -> str:
    if table.db or table.catalog:
        raise ValueError("portable SQL does not allow dotted table references")
    return _required_text(table.name, "table")


def _source_alias(table: exp.Table) -> str:
    alias = table.alias_or_name
    return _required_text(alias, "source alias")


def _column_ref(node: exp.Expression, source_aliases: dict[str, str]) -> _ColumnRef:
    if not isinstance(node, exp.Column):
        raise ValueError("portable SQL supports only column references in this position")
    if node.db or node.catalog:
        raise ValueError("portable SQL does not allow dotted column references beyond one source")
    table_name = node.table
    column_name = _required_text(node.name, "column")
    if table_name:
        source_name = source_aliases.get(table_name)
        if source_name is None:
            raise ValueError(f"source alias '{table_name}' is not bound")
        return _ColumnRef(source_name=source_name, column_name=column_name)
    if len(source_aliases) != 1:
        raise ValueError("unqualified columns require exactly one bound source")
    source_name = next(iter(source_aliases.values()))
    return _ColumnRef(source_name=source_name, column_name=column_name)


def _scalar_expr(node: exp.Expression, source_aliases: dict[str, str]) -> Any:
    if isinstance(node, exp.Column):
        return _column_ref(node, source_aliases)
    if isinstance(node, exp.Placeholder):
        return _ParameterRef(_required_text(node.name, "parameter"))
    if isinstance(node, exp.Literal):
        return _LiteralValue(node.to_py())
    raise ValueError("portable SQL expression is outside the supported subset")


def _predicate(node: exp.Expression, source_aliases: dict[str, str]) -> _Predicate:
    operator_map = {
        exp.EQ: "eq",
        exp.NEQ: "neq",
        exp.GT: "gt",
        exp.GTE: "gte",
        exp.LT: "lt",
        exp.LTE: "lte",
    }
    for expr_type, operator in operator_map.items():
        if isinstance(node, expr_type):
            return _Predicate(
                operator=operator,
                left=_scalar_expr(node.this, source_aliases),
                right=_scalar_expr(node.expression, source_aliases),
            )
    raise ValueError("portable SQL WHERE clauses support only simple comparisons")


def _aggregate(node: exp.Expression, source_aliases: dict[str, str]) -> _AggregateExpr:
    aggregate_map = {
        exp.Sum: "sum",
        exp.Max: "max",
        exp.Min: "min",
        exp.Avg: "mean",
        exp.Count: "count",
    }
    for expr_type, function_name in aggregate_map.items():
        if isinstance(node, expr_type):
            argument = node.this
            if isinstance(argument, exp.Star):
                raise ValueError("portable SQL does not support COUNT(*) yet")
            return _AggregateExpr(
                function=function_name, argument=_column_ref(argument, source_aliases)
            )
    raise ValueError("portable SQL aggregate is outside the supported subset")


def _projection(node: exp.Expression, source_aliases: dict[str, str]) -> _Projection:
    alias = None
    expression = node
    if isinstance(node, exp.Alias):
        alias = _required_text(node.alias, "projection alias")
        expression = node.this
    if isinstance(expression, exp.Column):
        column = _column_ref(expression, source_aliases)
        return _Projection(expression=column, output_name=alias or column.column_name)
    if isinstance(expression, (exp.Sum, exp.Max, exp.Min, exp.Avg, exp.Count)):
        aggregate = _aggregate(expression, source_aliases)
        return _Projection(
            expression=aggregate,
            output_name=alias or f"{aggregate.function}_{aggregate.argument.column_name}",
        )
    raise ValueError("portable SQL projection is outside the supported subset")


def _order_key(
    node: exp.Ordered, source_aliases: dict[str, str], output_names: set[str]
) -> _OrderKey:
    expression = node.this
    if isinstance(expression, exp.Column):
        if expression.table:
            column = _column_ref(expression, source_aliases)
            return _OrderKey(expression=column, descending=bool(node.args.get("desc")))
        column_name = _required_text(expression.name, "order column")
        if column_name in output_names:
            return _OrderKey(
                expression=_ColumnRef(source_name="", column_name=column_name),
                descending=bool(node.args.get("desc")),
            )
        column = _column_ref(expression, source_aliases)
        return _OrderKey(expression=column, descending=bool(node.args.get("desc")))
    raise ValueError("portable SQL ORDER BY supports only column references")


def _join_plan(
    node: exp.Join, source_aliases: dict[str, str], sources: dict[str, object]
) -> _JoinPlan:
    side = (node.side or "").upper()
    if side in {"RIGHT", "FULL"}:
        raise ValueError("portable SQL does not allow RIGHT or FULL joins")
    kind = side or (node.kind or "INNER").upper()
    if kind not in {"INNER", "LEFT"}:
        raise ValueError("portable SQL supports only INNER and LEFT joins")
    if not isinstance(node.this, exp.Table):
        raise ValueError("portable SQL join source must be a named table")
    source_name = _table_name(node.this)
    alias = _source_alias(node.this)
    if source_name not in sources:
        raise ValueError(f"source '{source_name}' is not bound")
    source_aliases[alias] = source_name
    if not isinstance(node.args.get("on"), exp.EQ):
        raise ValueError("portable SQL joins require one equality condition")
    on = node.args["on"]
    left_key = _column_ref(on.this, source_aliases)
    right_key = _column_ref(on.expression, source_aliases)
    if left_key.source_name == right_key.source_name:
        raise ValueError("portable SQL joins must compare columns from different sources")
    if right_key.source_name != source_name and left_key.source_name == source_name:
        left_key, right_key = right_key, left_key
    if right_key.source_name != source_name:
        raise ValueError("portable SQL join key must reference the joined source")
    return _JoinPlan(
        kind=kind.lower(), source_name=source_name, left_key=left_key, right_key=right_key
    )


def _lower_relational_plan(statement: str, *, sources: dict[str, object]) -> _RelationalPlan:
    expression = _parse_one(statement)
    if not isinstance(expression, exp.Select):
        raise ValueError("portable SQL currently accepts only SELECT statements")
    if expression.args.get("with") is not None:
        raise ValueError("portable SQL does not support WITH yet")
    if next(expression.find_all(exp.Offset), None) is not None:
        raise ValueError("portable SQL does not allow OFFSET")
    if expression.args.get("having") is not None:
        raise ValueError("portable SQL does not support HAVING yet")
    if expression.args.get("distinct") is not None:
        raise ValueError("portable SQL does not support DISTINCT yet")

    from_clause = expression.args.get("from_")
    if not isinstance(from_clause, exp.From) or not isinstance(from_clause.this, exp.Table):
        raise ValueError("portable SQL requires a named FROM source")
    base_source = _table_name(from_clause.this)
    if base_source not in sources:
        raise ValueError(f"source '{base_source}' is not bound")
    source_aliases = {_source_alias(from_clause.this): base_source}

    joins = tuple(
        _join_plan(join, source_aliases, sources) for join in expression.args.get("joins") or ()
    )
    projections = tuple(_projection(item, source_aliases) for item in expression.expressions)
    output_names = {item.output_name for item in projections}

    where_clause = expression.args.get("where")
    where = None if where_clause is None else _predicate(where_clause.this, source_aliases)

    group_expr = expression.args.get("group")
    group_by = ()
    if group_expr is not None:
        group_by = tuple(_column_ref(item, source_aliases) for item in group_expr.expressions)

    order_expr = expression.args.get("order")
    order_by = ()
    if order_expr is not None:
        order_by = tuple(
            _order_key(item, source_aliases, output_names) for item in order_expr.expressions
        )

    limit_expr = expression.args.get("limit")
    limit = None
    if limit_expr is not None:
        if not isinstance(limit_expr.expression, exp.Literal) or limit_expr.expression.is_string:
            raise ValueError("portable SQL LIMIT must be an integer literal")
        limit = int(limit_expr.expression.this)
        if limit < 0:
            raise ValueError("portable SQL LIMIT must be non-negative")

    return _RelationalPlan(
        base_source=base_source,
        projections=projections,
        joins=joins,
        where=where,
        group_by=group_by,
        order_by=order_by,
        limit=limit,
    )


def _resolve_scalar(value: Any, parameters: dict[str, Any]) -> Any:
    if isinstance(value, _LiteralValue):
        return value.value
    if isinstance(value, _ParameterRef):
        if value.name not in parameters:
            raise ValueError(f"missing SQL parameters: {value.name}")
        return parameters[value.name]
    raise TypeError("unexpected scalar value")


def _predicate_expr(predicate: _Predicate, parameters: dict[str, Any]) -> pl.Expr:
    if not isinstance(predicate.left, _ColumnRef):
        raise ValueError("portable SQL predicates require a column on the left side")
    left = pl.col(predicate.left.physical_name)
    right_value = predicate.right
    if isinstance(right_value, _ColumnRef):
        right = pl.col(right_value.physical_name)
    else:
        right = pl.lit(_resolve_scalar(right_value, parameters))
    operator = predicate.operator
    if operator == "eq":
        return left == right
    if operator == "neq":
        return left != right
    if operator == "gt":
        return left > right
    if operator == "gte":
        return left >= right
    if operator == "lt":
        return left < right
    if operator == "lte":
        return left <= right
    raise ValueError(f"unsupported predicate operator: {operator}")


def _rename_source(frame: pl.DataFrame, source_name: str) -> pl.LazyFrame:
    return frame.rename({column: f"{source_name}__{column}" for column in frame.columns}).lazy()


def _aggregate_expr(expression: _AggregateExpr, output_name: str) -> pl.Expr:
    column = pl.col(expression.argument.physical_name)
    function = expression.function
    if function == "sum":
        return column.sum().alias(output_name)
    if function == "max":
        return column.max().alias(output_name)
    if function == "min":
        return column.min().alias(output_name)
    if function == "mean":
        return column.mean().alias(output_name)
    if function == "count":
        return column.count().alias(output_name)
    raise ValueError(f"unsupported aggregate function: {function}")


def _output_name_for_expression(expression: Any) -> str | None:
    if isinstance(expression, _ColumnRef):
        return expression.column_name
    return None


def _sort_column_name(expression: Any) -> str:
    if isinstance(expression, _ColumnRef):
        return expression.column_name if not expression.source_name else expression.physical_name
    raise ValueError("portable SQL ORDER BY supports only columns")


def sql(
    statement: str,
    *,
    sources: dict[str, object],
    parameters: dict[str, Any] | None = None,
    limits: SqlResourceLimits | None = None,
) -> Query:
    bound_sources = dict(sources)
    try:
        plan = _lower_relational_plan(statement, sources=bound_sources)
    except ValueError as exc:
        raise _invalid_sql(str(exc)) from exc
    return Query(
        lane=QueryLane.RELATIONAL,
        statement=statement,
        sources=bound_sources,
        parameters={} if parameters is None else dict(parameters),
        limits=limits or SqlResourceLimits(),
        _definition=plan,
    )


class PolarsPlanMapper:
    def execute(self, query: Query, frames: dict[str, pl.DataFrame]) -> pl.DataFrame:
        started_ns = monotonic_ns()
        plan = query._definition
        if not isinstance(plan, _RelationalPlan):
            plan = _lower_relational_plan(query.statement, sources=dict(query.sources))

        base = frames[plan.base_source]
        intermediate_rows = base.height
        intermediate_bytes = _frame_bytes(base)
        _check_limit(intermediate_rows, query.limits.max_intermediate_rows, "max_intermediate_rows")
        _check_limit(
            intermediate_bytes, query.limits.max_intermediate_bytes, "max_intermediate_bytes"
        )
        frame = _rename_source(base, plan.base_source)
        for join in plan.joins:
            right_frame = frames[join.source_name]
            right = _rename_source(right_frame, join.source_name)
            # V1 fails closed on the Cartesian worst case unless declared
            # intermediate bounds can contain it.
            intermediate_rows *= right_frame.height
            left_row_bytes = intermediate_bytes // max(base.height, 1)
            right_row_bytes = _frame_bytes(right_frame) // max(right_frame.height, 1)
            intermediate_bytes = intermediate_rows * (left_row_bytes + right_row_bytes)
            _check_limit(
                intermediate_rows,
                query.limits.max_intermediate_rows,
                "max_intermediate_rows",
            )
            _check_limit(
                intermediate_bytes,
                query.limits.max_intermediate_bytes,
                "max_intermediate_bytes",
            )
            frame = frame.join(
                right,
                left_on=join.left_key.physical_name,
                right_on=join.right_key.physical_name,
                how=join.kind,
            )

        if plan.where is not None:
            frame = frame.filter(_predicate_expr(plan.where, dict(query.parameters)))

        if plan.group_by:
            group_keys = [pl.col(item.physical_name) for item in plan.group_by]
            aggregations = [
                _aggregate_expr(projection.expression, projection.output_name)
                for projection in plan.projections
                if isinstance(projection.expression, _AggregateExpr)
            ]
            grouped = frame.group_by(group_keys).agg(aggregations)
            rename_map = {item.physical_name: item.column_name for item in plan.group_by}
            frame = grouped.rename(rename_map)
            projection_exprs = []
            for projection in plan.projections:
                if isinstance(projection.expression, _ColumnRef):
                    projection_exprs.append(
                        pl.col(projection.expression.column_name).alias(projection.output_name)
                    )
                else:
                    projection_exprs.append(pl.col(projection.output_name))
            frame = frame.select(projection_exprs)
        else:
            projection_exprs = []
            for projection in plan.projections:
                expression = projection.expression
                if isinstance(expression, _ColumnRef):
                    projection_exprs.append(
                        pl.col(expression.physical_name).alias(projection.output_name)
                    )
                    continue
                raise ValueError("portable SQL aggregates require GROUP BY in this implementation")
            frame = frame.select(projection_exprs)

        result = frame.collect()
        if plan.order_by:
            by: list[str] = []
            descending: list[bool] = []
            for item in plan.order_by:
                name = _sort_column_name(item.expression)
                if name not in result.columns and isinstance(item.expression, _ColumnRef):
                    name = item.expression.column_name
                by.append(name)
                descending.append(item.descending)
            result = result.sort(by=by, descending=descending)
        if plan.limit is not None:
            result = result.head(plan.limit)
        _check_limit(result.height, query.limits.max_output_rows, "max_output_rows")
        _check_limit(_frame_bytes(result), query.limits.max_output_bytes, "max_output_bytes")
        elapsed_ms = (monotonic_ns() - started_ns) // 1_000_000
        _check_limit(elapsed_ms, query.limits.max_duration_ms, "max_duration_ms")
        return result


def execution_receipt(
    query: Query,
    frame: pl.DataFrame,
    *,
    source_rows: int,
    source_bytes: int,
    elapsed_ms: int,
) -> Receipt:
    return Receipt(
        kind="execution",
        operation="query.collect",
        details={
            "execution_location": "sdk-local",
            "lane": query.lane.value,
            "plan_hash": query.plan_hash,
            "definition_hash": query.definition_hash,
            "effective_limits": query.limits.to_wire(),
            "observed": {
                "source_rows": source_rows,
                "source_bytes": source_bytes,
                "output_rows": frame.height,
                "output_bytes": _frame_bytes(frame),
                "elapsed_ms": elapsed_ms,
            },
        },
    )


__all__ = [
    "NativeSql",
    "NativeSqlResourceLimits",
    "PolarsPlanMapper",
    "execution_receipt",
    "sql",
]
