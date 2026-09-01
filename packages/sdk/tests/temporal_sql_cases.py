from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from open_table_connector.timeseries import (
    BucketAggregate,
    GapFill,
    Latest,
    ScanRange,
)

START = "2026-08-29T00:00:00.000000000Z"
END = "2026-08-29T00:10:00.000000000Z"
PARAMETERS: dict[str, Any] = {"1": START, "2": END}


@dataclass(frozen=True)
class SqlCase:
    name: str
    statement: str
    parameters: dict[str, Any]
    operation_type: type
    output_fields: tuple[str, ...]


@dataclass(frozen=True)
class RejectedSqlCase:
    name: str
    statement: str
    parameters: dict[str, Any]


def _aggregate(function: str, output: str = "value") -> str:
    value = "*" if function == "count" else "price"
    arguments = f"{value}, ts" if function in {"first", "last"} else value
    return (
        f"SELECT time_bucket('5 minutes', ts) AS bucket, symbol, "
        f"{function}({arguments}) AS {output} FROM series "
        "WHERE ts >= $1 AND ts < $2 GROUP BY bucket, symbol "
        "ORDER BY symbol, bucket LIMIT 100"
    )


ACCEPTED_CASES = (
    SqlCase(
        "bounded_scan",
        "SELECT ts, symbol, price FROM series WHERE ts >= $1 AND ts < $2 ORDER BY symbol, ts LIMIT 100",
        PARAMETERS,
        ScanRange,
        ("ts", "symbol", "price"),
    ),
    SqlCase(
        "equality_filter",
        "SELECT ts, symbol, price FROM series WHERE ts >= $1 AND ts < $2 AND venue = $3 ORDER BY symbol, ts LIMIT 100",
        {**PARAMETERS, "3": "XNAS"},
        ScanRange,
        ("ts", "symbol", "price"),
    ),
    SqlCase(
        "in_filter",
        "SELECT ts, symbol, price FROM series WHERE ts >= $1 AND ts < $2 AND symbol IN ($3, $4) ORDER BY symbol, ts LIMIT 100",
        {**PARAMETERS, "3": "AAPL", "4": "MSFT"},
        ScanRange,
        ("ts", "symbol", "price"),
    ),
    SqlCase(
        "latest_lookup",
        "SELECT symbol, last(price, ts) AS price FROM series WHERE ts <= $1 GROUP BY symbol ORDER BY symbol LIMIT 100",
        {"1": END},
        Latest,
        ("symbol", "price"),
    ),
    *(
        SqlCase(
            f"aggregate_{function}",
            _aggregate(function),
            PARAMETERS,
            BucketAggregate,
            ("symbol", "bucket", "value"),
        )
        for function in ("count", "min", "max", "sum", "avg", "first", "last")
    ),
    SqlCase(
        "gapfill_locf",
        "SELECT time_bucket_gapfill('1 hour', ts) AS bucket, symbol, locf(avg(price)) AS mean_value FROM series WHERE ts >= $1 AND ts < $2 GROUP BY bucket, symbol ORDER BY symbol, bucket LIMIT 100",
        PARAMETERS,
        GapFill,
        ("symbol", "bucket", "mean_value"),
    ),
    SqlCase(
        "gapfill_interpolate",
        "SELECT time_bucket_gapfill('1 hour', ts) AS bucket, symbol, interpolate(avg(price)) AS mean_value FROM series WHERE ts >= $1 AND ts < $2 GROUP BY bucket, symbol ORDER BY symbol, bucket LIMIT 100",
        PARAMETERS,
        GapFill,
        ("symbol", "bucket", "mean_value"),
    ),
)


_BASE = (
    "SELECT ts, symbol, price FROM series WHERE ts >= $1 AND ts < $2 ORDER BY symbol, ts LIMIT 100"
)


REJECTED_CASES = (
    RejectedSqlCase(
        "between", _BASE.replace("ts >= $1 AND ts < $2", "ts BETWEEN $1 AND $2"), PARAMETERS
    ),
    RejectedSqlCase("comments", _BASE + " -- not allowed", PARAMETERS),
    RejectedSqlCase("physical_name", _BASE.replace("FROM series", "FROM ticks"), PARAMETERS),
    RejectedSqlCase(
        "multiple_sources", _BASE.replace("FROM series", "FROM series, other"), PARAMETERS
    ),
    RejectedSqlCase(
        "join",
        _BASE.replace("FROM series", "FROM series JOIN other ON series.symbol = other.symbol"),
        PARAMETERS,
    ),
    RejectedSqlCase("cte", "WITH series AS (SELECT * FROM source) " + _BASE, PARAMETERS),
    RejectedSqlCase(
        "subquery", _BASE.replace("FROM series", "FROM (SELECT * FROM series)"), PARAMETERS
    ),
    RejectedSqlCase("union", _BASE + " UNION " + _BASE, PARAMETERS),
    RejectedSqlCase(
        "window",
        _BASE.replace("ts, symbol, price", "ts, row_number() OVER () AS row_number, price"),
        PARAMETERS,
    ),
    RejectedSqlCase(
        "having", _BASE.replace("ORDER BY", "HAVING count(*) > 0 ORDER BY"), PARAMETERS
    ),
    RejectedSqlCase("distinct", _BASE.replace("SELECT", "SELECT DISTINCT"), PARAMETERS),
    RejectedSqlCase("offset", _BASE.replace("LIMIT 100", "LIMIT 100 OFFSET 1"), PARAMETERS),
    RejectedSqlCase("ddl", "CREATE TABLE series (ts timestamp)", {}),
    RejectedSqlCase("dml", "INSERT INTO series VALUES ($1)", {"1": START}),
    RejectedSqlCase("provider_setting", "SET enable_seqscan = off", {}),
    RejectedSqlCase("expression", _BASE.replace("price", "price + 1"), PARAMETERS),
    RejectedSqlCase("wildcard", _BASE.replace("ts, symbol, price", "*"), PARAMETERS),
    RejectedSqlCase("missing_lower_bound", _BASE.replace("ts >= $1 AND ", ""), {"2": END}),
    RejectedSqlCase("wrong_upper_bound", _BASE.replace("ts < $2", "ts <= $2"), PARAMETERS),
    RejectedSqlCase(
        "literal_predicate", _BASE.replace("ts < $2", "ts < $2 AND symbol = 'AAPL'"), PARAMETERS
    ),
    RejectedSqlCase("named_parameter", _BASE.replace("$1", ":start"), {"start": START}),
    RejectedSqlCase("zero_parameter", _BASE.replace("$1", "$0"), {"0": START, "2": END}),
    RejectedSqlCase("leading_zero_parameter", _BASE.replace("$1", "$01"), {"01": START, "2": END}),
    RejectedSqlCase("missing_parameter", _BASE, {"1": START}),
    RejectedSqlCase("extra_parameter", _BASE, {**PARAMETERS, "3": "unused"}),
    RejectedSqlCase(
        "mixed_in",
        _BASE.replace("ts < $2", "ts < $2 AND symbol IN ($3, 'MSFT')"),
        {**PARAMETERS, "3": "AAPL"},
    ),
    RejectedSqlCase("missing_limit", _BASE.replace(" LIMIT 100", ""), PARAMETERS),
    RejectedSqlCase("zero_limit", _BASE.replace("LIMIT 100", "LIMIT 0"), PARAMETERS),
    RejectedSqlCase(
        "parameter_limit", _BASE.replace("LIMIT 100", "LIMIT $3"), {**PARAMETERS, "3": 100}
    ),
    RejectedSqlCase("fractional_limit", _BASE.replace("LIMIT 100", "LIMIT 1.0"), PARAMETERS),
    RejectedSqlCase(
        "incomplete_order", _BASE.replace("ORDER BY symbol, ts", "ORDER BY symbol"), PARAMETERS
    ),
    RejectedSqlCase(
        "incomplete_group",
        _aggregate("sum").replace("GROUP BY bucket, symbol", "GROUP BY symbol"),
        PARAMETERS,
    ),
    RejectedSqlCase(
        "duplicate_alias",
        _aggregate("sum").replace(
            "sum(price) AS value", "sum(price) AS value, avg(price) AS value"
        ),
        PARAMETERS,
    ),
    RejectedSqlCase(
        "nested_fill",
        _aggregate("sum").replace("sum(price) AS value", "locf(interpolate(sum(price))) AS value"),
        PARAMETERS,
    ),
    RejectedSqlCase(
        "as_of_sql",
        "SELECT ts, symbol, price FROM series AS OF $1 ORDER BY symbol, ts LIMIT 100",
        {"1": END},
    ),
)
