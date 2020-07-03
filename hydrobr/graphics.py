import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from math import ceil, log
from plotly.offline import plot
import plotly.figure_factory as ff
import plotly.graph_objects as go


class Plot:
    def __init__(self):
        pass

    @staticmethod
    def flow_duration_curve(data, y_log_scale=True, **kwargs):
        """
        Make a flow duration curve plot.
        :param data: A Pandas daily DataFrame with DatetimeIndex where each column corresponds to a station.
        :param y_log_scale: boolean, optional, default: True, to set the plotting y-axis in the logarithmic scale.
        Use others parameters from matplotlib.pyplot.figure as kwargs.
        """
        plot_fdc = plt.figure(**kwargs)
        plt.grid(True, which="both", ls="-")
        y_max = 0
        for name in data.columns:
            series = data[name].dropna()
            n = len(series)
            y = np.sort(series)
            y = y[::-1]
            if y_max < y.max():
                y_max = y.max()
            x = (np.arange(1, n + 1) / n) * 100
            _ = plt.plot(x, y, linestyle='-')
        plt.legend(list(data.columns), loc='best')
        plt.margins(0.02)
        if y_log_scale:
            ticks = 10 ** np.arange(1, ceil(log(y_max, 10)) + 1, 1)
            ticks[-1:] += 1
            plt.yticks(list(ticks))
            plt.yscale('log')
            plt.tick_params(axis='y', which='minor')
        plt.xticks(np.arange(0, 101, step=10))
        return plot_fdc

    @staticmethod
    def gantt(data, monthly=True):
        """
        Make the Gantt plot. This graphic shows the temporal data availability for each station.
        :param data:A Pandas daily DataFrame with DatetimeIndex where each column corresponds to a station.
        :param graph_height: int, defines the height of the output graphic
        :param graph_name: str, optional, default: True
        Defines the name of the exported graph
        :param monthly: boolean, optional, default: True
        Defines if the availability count of the data will be monthly to obtain a more fluid graph.
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
        fig.update_layout(font=dict(family="Courier New, monospace", size=25))
        return fig
