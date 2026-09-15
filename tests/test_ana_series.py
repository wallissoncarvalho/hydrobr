"""Testes de cobertura, paginação e equivalência das séries diárias."""

from unittest.mock import Mock
import pandas as pd
import pytest

from hydrobr import ANA, get_data
from hydrobr.ana.series import daily_series, date_windows, records
from hydrobr.ana import ANAResponseError


@pytest.fixture(autouse=True)
def clean_credentials(monkeypatch):
    monkeypatch.delenv("HYDROBR_ANA_IDENTIFIER", raising=False)
    monkeypatch.delenv("HYDROBR_ANA_PASSWORD", raising=False)


def test_windows_cover_leap_year_without_gaps():
    start, end = pd.Timestamp('2019-05-15'), pd.Timestamp('2021-02-10')
    windows = list(date_windows(start, end))
    days = [day for begin, finish in windows for day in pd.date_range(begin, finish)]
    assert days == list(pd.date_range(start, end))
    assert max((finish - begin).days + 1 for begin, finish in windows) <= 366


def test_normalizers_preserve_consistency_missing_and_partial_month():
    rest = Mock()
    rest.json.return_value = {'items': [
        {'Data_Hora_Dado': '2020-02-01', 'Nivel_Consistencia': '1', 'Vazao_28': '10', 'Vazao_29': '11'},
        {'Data_Hora_Dado': '2020-02-01', 'nivelconsistencia': '2', 'Vazao_28': '12', 'Vazao_29': None}]}
    xml = Mock(content=b'<DataTable xmlns="http://MRCS/"><SerieHistorica><DataHora>2020-02-01</DataHora>'
                       b'<NivelConsistencia>2</NivelConsistencia><Vazao28>12</Vazao28></SerieHistorica></DataTable>')
    args = ('flow', '65310001', pd.Timestamp('2020-02-28'), pd.Timestamp('2020-02-29'))
    a = daily_series(records(rest, 'rest', ''), *args)
    b = daily_series(records(xml, 'legacy', 'SerieHistorica'), *args)
    pd.testing.assert_series_equal(a, b)
    assert a.iloc[0] == 12 and pd.isna(a.iloc[1])


def test_inventory_precedes_all_years_even_after_empty_response():
    session = Mock()
    def reply(url, **kwargs):
        if 'OAUth' in url:
            payload = {'items': {'token': 'test-token'}}
        elif 'Inventario' in url:
            payload = {'items': [{'codigoestacao': '65310001', 'Data_Periodo_Escala_Inicio': '2019-06-01',
                                  'Data_Periodo_Escala_Fim': '2021-02-28'}]}
        else:
            year = kwargs['params']['Data Inicial (yyyy-MM-dd)'][:4]
            payload = {'items': [] if year != '2021' else [
                {'Data_Hora_Dado': '2021-02-01', 'Nivel_Consistencia': '1', 'Vazao_01': '7'}]}
        return Mock(status_code=200, json=Mock(return_value=payload))
    session.get.side_effect = reply
    data = ANA('id', 'password', session=session).flow('65310001')
    calls = session.get.call_args_list
    assert 'Inventario' in calls[1].args[0]
    assert [c.kwargs['params']['Data Inicial (yyyy-MM-dd)'] for c in calls[2:]] == ['2019-06-01', '2020-01-01', '2021-01-01']
    assert data.loc['2021-02-01', '65310001'] == 7
    assert data.index[0] == pd.Timestamp('2019-06-01')
    assert data.index[-1] == pd.Timestamp('2021-02-28')
    assert data.notna().sum().iloc[0] == 1


def test_no_consisted_data_is_all_nan():
    row = {'datahora': '2020-01-01', 'nivelconsistencia': '1', 'chuva01': '3'}
    data = daily_series([row], 'prec', '00000001', pd.Timestamp('2020-01-01'), pd.Timestamp('2020-01-03'), True)
    assert len(data) == 3 and data.isna().all()


def test_legacy_entrypoint_delegates(monkeypatch):
    flow = Mock(return_value='result')
    monkeypatch.setattr(ANA, 'flow', flow)
    assert get_data.ANA.flow('65310001', source='legacy', start='2005-01-01') == 'result'
    flow.assert_called_once_with('65310001', only_consisted=False, start='2005-01-01', end=None)


def test_errors_are_not_interpreted_as_missing_data():
    response = Mock(json=Mock(return_value={'code': 500, 'items': []}))
    with pytest.raises(ANAResponseError):
        records(response, 'rest', '')
    with pytest.raises(ANAResponseError):
        records(Mock(content=b'<html>Maintenance</html>'), 'legacy', 'SerieHistorica')


def test_comparison_includes_exclusive_days():
    index = pd.date_range('2020-01-01', periods=3)
    rest = pd.DataFrame({'station': [1., 2., float('nan')]}, index=index)
    legacy = pd.DataFrame({'station': [1.004, float('nan'), 3.]}, index=index)
    row = ANA.compare(rest, legacy).iloc[0]
    assert row['common'] == row['only_rest'] == row['only_legacy'] == 1
    assert row['above_tolerance'] == 0


def test_missing_inventory_start_requires_explicit_date(monkeypatch):
    ana = ANA(source='legacy')
    monkeypatch.setattr(ana, 'inventory', lambda station: {})
    with pytest.raises(ValueError, match='Início não cadastrado'):
        ana.flow('65310001')
