import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.figure_factory as ff
import plotly.graph_objects as go
from math import ceil, log
from plotly.offline import plot


class Plot:

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
            fig.add_trace(go.Scatter(x=x, y=y, mode='lines', name=name))

        if y_log_scale:
            ticks = 10 ** np.arange(1, ceil(log(y_max, 10)) + 1, 1)
            ticks[-1:] += 1
            fig.update_layout(yaxis=dict(
                tickmode='array', tickvals=ticks, dtick=2), yaxis_type="log")
        fig.update_layout(xaxis=dict(tickmode='array', tickvals=np.arange(0, 101, step=10)))
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

        date_index = pd.date_range(data.index[0], data.index[-1], freq='D')
        data = data.reindex(date_index)
        periods = []
        for column in data.columns:
            series = data[column]
            if monthly:
                missing = series.isnull().groupby(pd.Grouper(freq='1MS')).sum().to_frame()
                series_drop = missing.loc[missing[column] < 7]  # A MONTH WITHOUT 7 DATA IS CONSIDERED A MISSING MONTH
                DELTA = 'M'
            else:
                series_drop = series.dropna()
                DELTA = 'D'
            if series_drop.shape[0] > 1:
                task = column
                resource = 'Available data'
                start = str(series_drop.index[0].year) + '-' + str(series_drop.index[0].month) + '-' + str(
                    series_drop.index[0].day)
                finish = 0
                for i in range(len(series_drop)):
                    if i != 0 and round((series_drop.index[i] - series_drop.index[i - 1]) / np.timedelta64(1, DELTA),
                                        0) != 1:
                        finish = str(series_drop.index[i - 1].year) + '-' + str(
                            series_drop.index[i - 1].month) + '-' + str(
                            series_drop.index[i - 1].day)
                        periods.append(dict(Task=task, Start=start, Finish=finish, Resource=resource))
                        start = str(series_drop.index[i].year) + '-' + str(series_drop.index[i].month) + '-' + str(
                            series_drop.index[i].day)
                        finish = 0
                finish = str(series_drop.index[-1].year) + '-' + str(series_drop.index[-1].month) + '-' + str(
                    series_drop.index[-1].day)
                periods.append(dict(Task=task, Start=start, Finish=finish, Resource=resource))
            else:
                print('Station {} has no months with significant data'.format(column))
        periods = pd.DataFrame(periods)
        start_year = periods['Start'].apply(lambda x: int(x[:4])).min()
        finish_year = periods['Start'].apply(lambda x: int(x[:4])).max()
        colors = {'Available data': 'rgb(0,191,255)'}
        fig = ff.create_gantt(periods, colors=colors, index_col='Resource', show_colorbar=True, showgrid_x=True,
                              showgrid_y=True, group_tasks=True)

        fig.layout.xaxis.tickvals = pd.date_range('1/1/' + str(start_year), '12/31/' + str(finish_year + 1), freq='2AS')
        fig.layout.xaxis.ticktext = pd.date_range('1/1/' + str(start_year), '12/31/' + str(finish_year + 1),
                                                  freq='2AS').year
        fig = go.FigureWidget(fig)
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

        if ('Latitude' not in list_stations.columns) or ('Longitude' not in list_stations.columns):
            raise Exception('Longitude and Latitude columns are required')
        list_stations['Text'] = 'Name: ' + list_stations.Name + '<br>Code: ' + list_stations.Code
        list_stations[['Latitude', 'Longitude']] = list_stations[['Latitude', 'Longitude']].apply(pd.to_numeric,
                                                                                                  errors='coerce')

        # Creating the Figure
        fig = go.Figure(go.Scattermapbox(lat=list_stations.Latitude.to_list(), lon=list_stations.Longitude.to_list(),
                                         mode='markers', marker=go.scattermapbox.Marker(size=5),
                                         text=list_stations.Text.to_list()))

        # Updating the layout
        fig.update_layout(autosize=True, hovermode='closest',
                          mapbox=dict(accesstoken=mapbox_access_token, bearing=0,
                                      center=dict(lat=list_stations.Latitude.sum() / len(list_stations),
                                                  lon=list_stations.Longitude.sum() / len(list_stations)),
                                      pitch=0, zoom=4))

        return fig