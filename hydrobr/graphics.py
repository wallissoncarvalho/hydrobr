import numpy as np
import pandas as pd
import plotly.figure_factory as ff
import plotly.graph_objects as go
from math import ceil, log


class Plot:
    @staticmethod
    def change_point(annual, results, station, test="pettitt"):
        """Série anual, ponto candidato e médias antes/depois do teste escolhido."""
        series = annual[station].dropna()
        row = results.loc[(station, test)]
        years = series.index.year if isinstance(series.index, pd.DatetimeIndex) else series.index
        fig = go.Figure(go.Scatter(x=years, y=series, mode="lines+markers", name="Observado"))
        if pd.notna(row.change_year):
            year = int(row.change_year)
            fig.add_shape(type="line", x0=year, x1=year, y0=0, y1=1, yref="paper", line=dict(color="red", dash="dash"))
            fig.add_trace(go.Scatter(x=years, y=np.where(years <= year, row.mean_before, row.mean_after),
                                     mode="lines", name="Médias por período"))
        fig.update_layout(xaxis_title="Ano", yaxis_title="Valor", title=f"{test}: {station} (p={row.p_value:.3g})")
        return fig

    @staticmethod
    def double_mass(data):
        """Chuva anual acumulada do alvo contra a média acumulada das referências."""
        fig = go.Figure(go.Scatter(x=np.r_[0, data.reference_cumulative_mm], y=np.r_[0, data.target_cumulative_mm],
                                   mode="lines+markers", text=["Início", *data.index.astype(str)], name="Dupla massa"))
        fig.update_layout(xaxis_title="Referências acumuladas (mm)", yaxis_title="Posto-alvo acumulado (mm)",
                          title=f"Curva de dupla massa — {data.attrs.get('target', 'alvo')}")
        return fig

    @staticmethod
    def teleconnections(results, station, lag_years=0):
        """Correlação por índice climático, com significância ajustada indicada no texto."""
        data = results.xs((station, lag_years), level=("station", "lag_years"))
        text = [f"n={row.n}; p ajustado={row.p_adjusted:.3g}" for row in data.itertuples()]
        fig = go.Figure(go.Bar(x=data.index, y=data.correlation, text=text))
        fig.update_layout(xaxis_title="Índice climático", yaxis_title="Correlação",
                          title=f"Teleconexões — {station}; lag={lag_years} ano(s)")
        return fig

    @staticmethod
    def trend(annual, station, result=None):
        """Série anual e reta de Sen; `result` é a saída de HydroAnalysis.trends()."""
        from hydrobr.analysis import HydroAnalysis

        series = annual[station].dropna()
        if series.empty:
            raise ValueError("A estação não possui máximas anuais válidas.")
        result = HydroAnalysis.trends(annual) if result is None else result
        years = series.index.year if isinstance(series.index, pd.DatetimeIndex) else series.index.astype(float)
        fig = go.Figure(go.Scatter(x=years, y=series, mode="markers+lines", name="Observado"))
        slope, intercept = result.loc[station, ["slope_per_year", "intercept"]]
        if pd.notna(slope):
            fig.add_trace(go.Scatter(x=years, y=intercept + slope * years, mode="lines", name="Sen"))
        fig.update_layout(xaxis_title="Ano hidrológico", yaxis_title="Máxima anual", title=f"Tendência — {station}")
        return fig

    @staticmethod
    def cluster_scores(scores):
        """Silhouette e Davies–Bouldin por método e número de grupos."""
        from plotly.subplots import make_subplots

        titles = ("Silhouette (maior é melhor)", "Davies–Bouldin (menor é melhor)")
        fig = make_subplots(rows=1, cols=2, subplot_titles=titles)
        for method in scores.index.get_level_values("method").unique():
            subset = scores.loc[method]
            fig.add_trace(go.Scatter(x=subset.index, y=subset.silhouette, mode="lines+markers", name=method),
                          row=1, col=1)
            fig.add_trace(go.Scatter(x=subset.index, y=subset.davies_bouldin, mode="lines+markers",
                                     name=method, showlegend=False), row=1, col=2)
        fig.update_xaxes(title_text="Número de grupos")
        return fig

    @staticmethod
    def fdc(data, y_log_scale=True):
        """
        Make a flow duration curve plot.

        Parameters
        ----------
        data : pandas DataFrame
            A Pandas daily DataFrame with DatetimeIndex where each column corresponds to a station..
        y_log_scale : boolean, default True
            Defines if the the plotting y-axis will be in the logarithmic scale.

        Returns
        -------
        fig : plotly Figure
        """

        fig = go.Figure()
        y_max = 0
        for name in data.columns:
            series = data[name].dropna()
            n = len(series)
            y = np.sort(series)
            y = y[::-1]
            if y_max < y.max():
                y_max = y.max()
            x = (np.arange(1, n + 1) / n) * 100
            fig.add_trace(go.Scatter(x=x, y=y, mode="lines", name=name))

        if y_log_scale:
            ticks = 10 ** np.arange(1, ceil(log(y_max, 10)) + 1, 1)
            ticks[-1:] += 1
            fig.update_layout(yaxis=dict(tickmode="array", tickvals=ticks, dtick=2), yaxis_type="log")
        fig.update_layout(xaxis=dict(tickmode="array", tickvals=np.arange(0, 101, step=10)))
        return fig

    @staticmethod
    def gantt(data, monthly=True):
        """
        Make a Gantt plot, which shows the temporal data availability for each station.

        Parameters
        ----------
        data : pandas DataFrame
            A Pandas daily DataFrame with DatetimeIndex where each column corresponds to a station..
        monthly : boolean, default True
            Defines if the availability count of the data will be monthly to obtain a more fluid graph.

        Returns
        -------
        fig : plotly Figure
        """

        date_index = pd.date_range(data.index[0], data.index[-1], freq="D")
        data = data.reindex(date_index)
        periods = []
        for column in data.columns:
            series = data[column]
            if monthly:
                missing = series.isnull().groupby(pd.Grouper(freq="1MS")).sum().to_frame()
                series_drop = missing.loc[missing[column] < 7]  # A MONTH WITHOUT 7 DATA IS CONSIDERED A MISSING MONTH
                DELTA = "M"
            else:
                series_drop = series.dropna()
                DELTA = "D"
            if series_drop.shape[0] > 1:
                task = column
                resource = "Available data"
                start = str(series_drop.index[0].year) + "-" + str(series_drop.index[0].month) + "-" + str(series_drop.index[0].day)
                finish = 0
                for i in range(len(series_drop)):
                    if i != 0 and round((series_drop.index[i] - series_drop.index[i - 1]) / np.timedelta64(1, DELTA), 0) != 1:
                        finish = (str(series_drop.index[i - 1].year) + "-" + str(series_drop.index[i - 1].month)
                                  + "-" + str(series_drop.index[i - 1].day))
                        periods.append(dict(Task=task, Start=start, Finish=finish, Resource=resource))
                        start = str(series_drop.index[i].year) + "-" + str(series_drop.index[i].month) + "-" + str(series_drop.index[i].day)
                        finish = 0
                finish = str(series_drop.index[-1].year) + "-" + str(series_drop.index[-1].month) + "-" + str(series_drop.index[-1].day)
                periods.append(dict(Task=task, Start=start, Finish=finish, Resource=resource))
            else:
                print("Station {} has no months with significant data".format(column))
        periods = pd.DataFrame(periods)
        start_year = periods["Start"].apply(lambda x: int(x[:4])).min()
        finish_year = periods["Start"].apply(lambda x: int(x[:4])).max()
        colors = {"Available data": "rgb(0,191,255)"}
        fig = ff.create_gantt(periods, colors=colors, index_col="Resource", show_colorbar=True,
                              showgrid_x=True, showgrid_y=True, group_tasks=True)

        fig.layout.xaxis.tickvals = pd.date_range("1/1/" + str(start_year), "12/31/" + str(finish_year + 1), freq="2AS")
        fig.layout.xaxis.ticktext = pd.date_range("1/1/" + str(start_year),
                                                  "12/31/" + str(finish_year + 1), freq="2AS").year
        return fig

    @staticmethod
    def spatial_stations(list_stations, mapbox_access_token):
        """
        Make a spatial plot of the stations.

        Parameters
        ----------
        list_stations : pandas DataFrame
            A Pandas DataFrame that must contain Latitude, Longitude, Name, and Code columns.
        mapbox_access_token : str
            Mapbox access toke, which can be obtained at https://account.mapbox.com/access-tokens/

        Returns
        -------
        fig : plotly Figure
        """

        if ("Latitude" not in list_stations.columns) or ("Longitude" not in list_stations.columns):
            raise Exception("Longitude and Latitude columns are required")
        list_stations["Text"] = "Name: " + list_stations.Name + "<br>Code: " + list_stations.Code
        list_stations[["Latitude", "Longitude"]] = list_stations[["Latitude", "Longitude"]].apply(pd.to_numeric, errors="coerce")

        # Creating the Figure
        fig = go.Figure(go.Scattermapbox(lat=list_stations.Latitude.to_list(), lon=list_stations.Longitude.to_list(),
                                         mode="markers", marker=go.scattermapbox.Marker(size=5),
                                         text=list_stations.Text.to_list()))

        # Updating the layout
        center = dict(lat=list_stations.Latitude.sum() / len(list_stations),
                      lon=list_stations.Longitude.sum() / len(list_stations))
        fig.update_layout(autosize=True, hovermode="closest",
                          mapbox=dict(accesstoken=mapbox_access_token, bearing=0, center=center, pitch=0, zoom=4))

        return fig
