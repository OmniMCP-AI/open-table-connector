
import polars as pl
import pytest
from open_table_connector.local_files import LocalFilesConnector
from open_table_connector.sdk import Client, ConnectorRegistry, OTCError


def client():
    return Client(registry=ConnectorRegistry([LocalFilesConnector()]))


def test_range_table_roundtrip(tmp_path):
    c = client()
    b = c.workbook.create((tmp_path / 'r.xlsx').as_uri(), profile='general/1.0')
    r = b.worksheet.create('Report').range('B2:C4')
    frame = pl.DataFrame({'label': ['=1+2', None], 'amount': ['9007199254740993', None]})
    r.write_table(frame)
    assert r.read_table().require_value().equals(frame)
    b.write()
    reopened = c.workbook.open((tmp_path / 'r.xlsx').as_uri(), profile='general/1.0')
    assert reopened.worksheet('Report').range('B2:C4').read_table().require_value().equals(frame)


def test_range_shape_rejected_before_queue(tmp_path):
    b = client().workbook.create((tmp_path / 'r.xlsx').as_uri(), profile='general/1.0')
    r = b.worksheet.create('Report').range('A1:B2')
    with pytest.raises(ValueError, match='shape'):
        r.write_table(pl.DataFrame({'a': ['1']}))


def test_materialize_preserves_workbook_and_returns_readable_table(tmp_path):
    c = client()
    path = tmp_path / 'book.xlsx'
    b = c.workbook.create(path.as_uri(), profile='general/1.0')
    sheet = b.worksheet.create('Report')
    sheet.range('A1').write('Title', style={'bold': True})
    sheet.formulas().set('B1', '=1+2')
    b.write()
    frame = pl.DataFrame({'label': ['=1+2', '', '@x'], 'amount': [9007199254740993, None, -1]})
    result = c.materialize(frame, to=f'file://{path}#sheet=Base')
    assert result.commit.value == 'committed'
    assert result.verification.value == 'passed'
    assert result.require_value().read().require_value().equals(frame.cast(pl.String))
    reopened = c.workbook.open(path.as_uri())
    assert reopened.worksheet('Report').range('A1:B1').read().require_value() == [['Title', '=1+2']]
    before = path.read_bytes()
    with pytest.raises((OTCError, ValueError)):
        c.materialize(frame, to=f'file://{path}#sheet=base')
    assert path.read_bytes() == before


def test_materialize_new_and_empty(tmp_path):
    path = tmp_path / 'empty.xlsx'
    c = client()
    frame = pl.DataFrame(schema={'id': pl.String, 'value': pl.String})
    result = c.materialize(frame, to=f'file://{path}#sheet=Base')
    assert result.require_value().read().require_value().equals(frame)


@pytest.mark.parametrize('suffix', ['', '#sheet=', '#sheet=A&sheet=B', '?secret=x#sheet=A'])
def test_invalid_destination_has_no_effect(tmp_path, suffix):
    path = tmp_path / 'invalid.xlsx'
    with pytest.raises((OTCError, ValueError)):
        client().materialize(pl.DataFrame({'id': ['a']}), to=f'file://{path}{suffix}')
    assert not path.exists()


@pytest.mark.parametrize('values', [[None], ['x' * 32768], ['\x01'], [[1, 2]]])
def test_invalid_table_has_no_effect(tmp_path, values):
    path = tmp_path / 'invalid.xlsx'
    with pytest.raises((OTCError, ValueError, TypeError)):
        client().materialize(pl.DataFrame({'id': values}), to=f'file://{path}#sheet=Base')
    assert not path.exists()


def test_materialize_integers_remain_usable_by_excel_aggregates(tmp_path):
    c = client()
    path = tmp_path / 'numbers.xlsx'
    result = c.materialize(pl.DataFrame({'value': [120, -4]}), to=f'file://{path}#sheet=Base')
    assert result.require_value().read().require_value()['value'].to_list() == ['120', '-4']
    b = c.workbook.open(path.as_uri())
    assert b.worksheet('Base').range('A2:A3').read().require_value() == [[120], [-4]]


def test_postcommit_readback_failure_keeps_committed_evidence(tmp_path, monkeypatch):
    connector = LocalFilesConnector()
    c = Client(registry=ConnectorRegistry([connector]))
    path = tmp_path / 'readback.xlsx'
    def fail(*args, **kwargs):
        raise RuntimeError('injected persisted read failure')
    monkeypatch.setattr(connector, 'read_table', fail)
    with pytest.raises(OTCError) as caught:
        c.materialize(pl.DataFrame({'id': ['x']}), to=f'file://{path}#sheet=Base')
    assert path.exists()
    assert caught.value.result.commit.value == 'committed'
    assert caught.value.result.verification.value == 'failed'
    assert caught.value.result.receipts


def test_materialize_stale_revision_preserves_competing_writer(tmp_path, monkeypatch):
    from open_table_connector.local_files.spreadsheet_workbook import LocalSpreadsheetProvider
    c = client()
    path = tmp_path / 'race.xlsx'
    b = c.workbook.create(path.as_uri(), profile='general/1.0')
    b.worksheet.create('Report').range('A1').write('before')
    b.write()
    original = LocalSpreadsheetProvider.commit
    competing = []
    def race(self, binding, changes, **kwargs):
        monkeypatch.setattr(LocalSpreadsheetProvider, 'commit', original)
        writer = client().workbook.open(path.as_uri())
        writer.worksheet('Report').range('A1').write('winner')
        writer.write()
        competing.append(path.read_bytes())
        return original(self, binding, changes, **kwargs)
    monkeypatch.setattr(LocalSpreadsheetProvider, 'commit', race)
    with pytest.raises(OTCError):
        c.materialize(pl.DataFrame({'id': ['x']}), to=f'file://{path}#sheet=Base')
    assert path.read_bytes() == competing[0]


def test_range_bad_headers_and_literal_profile(tmp_path):
    c = client()
    b = c.workbook.create((tmp_path / 'literal.xlsx').as_uri())
    r = b.worksheet.create('Report').range('A1:B2')
    frame = pl.DataFrame({'label': ['=1+2'], 'value': ['9007199254740993']})
    r.write_table(frame)
    b.write()
    assert r.read_table().require_value().equals(frame)
    g = c.workbook.create((tmp_path / 'headers.xlsx').as_uri(), profile='general/1.0')
    bad = g.worksheet.create('Bad').range('A1:B2')
    bad.write([['duplicate', 'duplicate'], ['1', '2']])
    with pytest.raises(ValueError, match='headers'):
        bad.read_table()


def test_range_bounds_and_headerless(tmp_path):
    from open_table_connector.spreadsheets import ArtifactLimits
    b = client().workbook.create((tmp_path / 'bounds.xlsx').as_uri(),
                                 profile='general/1.0', limits=ArtifactLimits(cells=4))
    s = b.worksheet.create('Report')
    with pytest.raises(OTCError):
        s.range('A1:A5').write_table(pl.DataFrame({'a': ['x'] * 4}))
    s.range('B1:B2').write_table(pl.DataFrame({'a': ['x', 'y']}), header=False)
    result = s.range('B1:B2').read_table(header=False)
    assert result.require_value().to_dict(as_series=False) == {'column_1': ['x', 'y']}
    assert result.commit.value == 'not_applicable'
    assert result.verification.value == 'unavailable'


def test_discovered_client_materializes_and_reopens(tmp_path):
    from open_table_connector.sdk import load_client_config
    c = Client.from_config(load_client_config())
    path = tmp_path / 'discovered.xlsx'
    uri = path.as_uri() + '#sheet=Base'
    frame = pl.DataFrame({'id': ['x'], 'amount': ['120']})
    result = c.materialize(frame, to=uri)
    assert result.require_value().read().require_value().equals(frame)
    assert c.open(uri).require_value().read().require_value().equals(frame)
