"""Contrato diário, flags explícitas e auditoria de cobertura para séries observadas."""

import numpy as np
import pandas as pd


def _frame(data):
    if isinstance(data, pd.Series):
        data = data.to_frame()
    if not isinstance(data, pd.DataFrame) or not isinstance(data.index, pd.DatetimeIndex):
        raise TypeError("Informe Series/DataFrame com DatetimeIndex diário.")
    if data.empty or data.columns.has_duplicates or data.index.has_duplicates or data.index.isna().any():
        raise ValueError("A série não pode ser vazia nem conter datas/estações duplicadas ou datas inválidas.")
    if data.index.tz is not None or not data.index.equals(data.index.normalize()):
        raise ValueError("Use datas locais sem fuso e sem horário; agregue observações subdiárias antes.")
    result = data.apply(pd.to_numeric, errors="raise").sort_index().copy()
    if np.isinf(result.to_numpy(dtype=float)).any():
        raise ValueError("Valores infinitos não são permitidos.")
    return result


class HydroSeries:
    """Série diária com unidade, origem e máscara manual; valores brutos nunca são preenchidos."""

    def __init__(self, data, variable, unit, source, flags=None):
        if not all(isinstance(value, str) and value.strip() for value in (variable, unit, source)):
            raise ValueError("variable, unit e source devem ser textos não vazios.")
        raw = _frame(data)
        if flags is None:
            marked = pd.DataFrame(False, index=raw.index, columns=raw.columns)
        else:
            if isinstance(flags, pd.Series):
                flags = flags.to_frame()
            if not isinstance(flags, pd.DataFrame) or not flags.index.equals(raw.index) or not flags.columns.equals(raw.columns):
                raise ValueError("flags deve ter as mesmas datas e colunas de data; True significa dado excluído.")
            valid_flags = flags.isna() | flags.eq(True) | flags.eq(False)
            if not valid_flags.to_numpy().all():
                raise ValueError("flags deve conter apenas booleanos ou NA.")
            marked = flags.fillna(False).astype(bool).copy()
        dates = pd.date_range(raw.index.min(), raw.index.max(), freq="D")
        self.data = raw.reindex(dates)
        self.flags = marked.reindex(dates, fill_value=False)
        self.variable, self.unit, self.source = variable.strip(), unit.strip(), source.strip()
        self.first_record, self.last_record = raw.index.min(), raw.index.max()

    def clean(self):
        """Valores prontos para análise; precipitação/vazão negativas e flags manuais tornam-se NaN."""
        invalid = self.flags.copy()
        if self.variable in ("precipitation", "flow"):
            invalid |= self.data.lt(0)
        result = self.data.mask(invalid)
        result.attrs.update(variable=self.variable, unit=self.unit, source=self.source,
                            first_record=self.first_record, last_record=self.last_record)
        return result

    def audit(self, period="year", year_start_month=1, min_coverage=1.0):
        """Cobertura por estação e mês/ano completo, incluindo dias fora dos limites do arquivo."""
        if period not in ("year", "month") or not isinstance(year_start_month, int) or not 1 <= year_start_month <= 12:
            raise ValueError("period deve ser year/month e year_start_month deve estar entre 1 e 12.")
        if not 0 < min_coverage <= 1:
            raise ValueError("min_coverage deve estar em (0, 1].")
        if period == "month":
            starts = pd.date_range(self.data.index.min().to_period("M").start_time,
                                   self.data.index.max().to_period("M").start_time, freq="MS")
        else:
            first = self.data.index.min()
            last = self.data.index.max()
            first_year = first.year if first.month >= year_start_month else first.year - 1
            last_year = last.year if last.month >= year_start_month else last.year - 1
            starts = [pd.Timestamp(year, year_start_month, 1) for year in range(first_year, last_year + 1)]
        clean = self.clean()
        rows = []
        for start in starts:
            end = start + (pd.DateOffset(months=1) if period == "month" else pd.DateOffset(years=1)) - pd.Timedelta(days=1)
            dates = pd.date_range(start, end, freq="D")
            for station in self.data:
                raw = self.data[station].reindex(dates)
                flagged = self.flags[station].reindex(dates, fill_value=False)
                valid = clean[station].reindex(dates).notna().sum()
                rows.append(dict(period=start, station=station, start=start, end=end, expected_days=len(dates),
                                 valid_days=int(valid), missing_days=int(raw.isna().sum()),
                                 negative_days=int(raw.lt(0).sum()) if self.variable in ("precipitation", "flow") else 0,
                                 flagged_days=int((flagged & raw.notna()).sum()), coverage=valid / len(dates),
                                 accepted=bool(valid / len(dates) >= min_coverage),
                                 variable=self.variable, unit=self.unit, source=self.source))
        result = pd.DataFrame(rows).set_index(["period", "station"])
        result.attrs.update(period=period, year_start_month=year_start_month, min_coverage=min_coverage,
                            note="Flags, negativos e ausências podem se sobrepor; dias válidos contam uma vez.")
        return result
