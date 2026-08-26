import pytest

from open_connectors.contract import ConnectorError, ConnectorErrorCode, TableMode, TableURI
from open_connectors.maybesheet import MaybeSheetConnector, MaybeSheetReadRequest


class Process:
    def __init__(self): self.calls = []
    def run(self, argv, *, credentials=None):
        self.calls.append((argv, credentials))
        return {"rows": [{"id": "1", "amount": "2.50"}], "source_revision": "rev-1", "receipt_id": "safe-ref"}


def test_maybesheet_has_explicit_base_and_sheet_argv_and_receipts() -> None:
    process = Process()
    connector = MaybeSheetConnector(process)
    request = MaybeSheetReadRequest(TableURI("https://www.maybe.ai/docs/spreadsheets/d/doc"), TableMode.BASE, "R_orders")

    result = connector.read_polars(request)

    assert result.frame.to_dicts() == [{"id": "1", "amount": "2.50"}]
    assert process.calls[0][0][:3] == ("mbs", "db-table", "read")
    assert result.receipt.vendor_receipt_ref == "safe-ref"


def test_maybesheet_non_read_capabilities_fail_explicitly() -> None:
    connector = MaybeSheetConnector(Process())
    with pytest.raises(ConnectorError) as error:
        connector.read_formula_values(object())
    assert error.value.code is ConnectorErrorCode.UNSUPPORTED_CAPABILITY
