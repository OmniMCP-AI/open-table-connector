"""Create-only lexical worksheet tables through the existing workbook provider."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

import polars as pl
from open_table_connector.sdk._excel_table import table_address, table_matrix
from open_table_connector.sdk.model import DirectDestination
from open_table_connector.sdk.result import (
    CommitState,
    ErrorCode,
    ErrorInfo,
    OperationResult,
    OTCError,
    Outcome,
    VerificationState,
)
from open_table_connector.spreadsheets import ArtifactLimits


def create_excel_table(connector, source, destination):
    # Late SDK import avoids the connector registration import cycle.
    from open_table_connector.sdk import Client, ConnectorRegistry

    client = None
    book = None
    written = None
    receipts = ()
    try:
        if not isinstance(destination, DirectDestination):
            raise ValueError('Excel materialization requires DirectDestination')
        uri = destination.uri
        parsed = urlsplit(uri.value)
        selectors = parse_qsl(parsed.fragment, keep_blank_values=True)
        if (parsed.scheme != 'file' or parsed.netloc not in ('', 'localhost') or parsed.query
                or len(selectors) != 1 or selectors[0][0] != 'sheet' or not selectors[0][1]):
            raise ValueError('Excel materialization requires file:///absolute/book.xlsx#sheet=Name')
        path = Path(unquote(parsed.path))
        sheet = selectors[0][1]
        if not path.is_absolute() or path.suffix.lower() != '.xlsx':
            raise ValueError('Excel materialization requires an absolute .xlsx file')
        limits = ArtifactLimits()
        if (source.height + 1) * source.width > limits.cells:
            raise ValueError('Excel table exceeds cell limit')
        matrix = table_matrix(source)
        # Preserve Excel aggregation for safe integer columns; wider integers
        # stay text so serialization cannot silently round them.
        for column, dtype in enumerate(source.dtypes):
            if dtype.is_integer():
                for index, value in enumerate(source.get_column(source.columns[column])):
                    if value is not None and len(str(abs(value))) <= 15:
                        matrix[index + 1][column] = value
        if any(all(value is None for value in row) for row in matrix[1:]):
            raise ValueError('worksheet table cannot preserve all-null rows')
        client = Client(registry=ConnectorRegistry([connector]))
        book = (client.workbook.open(path.as_uri()) if path.exists()
                else client.workbook.create(path.as_uri(), profile='general/1.0'))
        if sheet.casefold() in {name.casefold() for name in book.worksheet.list()}:
            raise ValueError('Excel destination worksheet already exists')
        target = book.worksheet.create(sheet)
        target.range(table_address(len(matrix), source.width)).write(matrix)
        written = book.write()
        receipts = written.receipts
        if (written.outcome is not Outcome.SUCCEEDED or written.commit is not CommitState.COMMITTED
                or written.verification is not VerificationState.PASSED):
            return replace(written, value=None)
        opened = connector.open_table(uri.value)
        receipts += opened.receipts
        binding = opened.require_value()
        readback = connector.read_table(binding)
        receipts += readback.receipts
        observed = readback.require_value().to_polars()
        if not observed.equals(source.cast(pl.String)):
            raise ValueError('persisted Excel table differs from submitted lexical values')
        return OperationResult(binding, Outcome.SUCCEEDED, CommitState.COMMITTED,
                               VerificationState.PASSED, receipts)
    except Exception as exc:
        if written is not None:
            return OperationResult(
                None, Outcome.FAILED, written.commit, VerificationState.FAILED, receipts,
                error=ErrorInfo(ErrorCode.EXECUTION_FAILED, 'Excel table readback failed',
                                {'cause': str(exc), 'commit': written.commit.value}),
            )
        if isinstance(exc, OTCError):
            return exc.result
        return OperationResult(
            None, Outcome.REJECTED, CommitState.NOT_STARTED, VerificationState.SKIPPED, (),
            error=ErrorInfo(ErrorCode.INVALID_TARGET, str(exc)),
        )
    finally:
        if book is not None:
            book.close()
        if client is not None:
            client.close()
