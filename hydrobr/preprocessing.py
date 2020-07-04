import pandas as pd
import numpy as np
from dateutil.relativedelta import relativedelta
from tqdm import tqdm


class PreProcessing:
    def __init__(self):
        pass

    @staticmethod
    def stations_filter(data, n_years=10, missing_percentage=5, start_date=False, end_date=False):
        """
        A composed method to select stations.
        :param data:A Pandas daily DataFrame with DatetimeIndex where each column corresponds to a station.
        :param n_years:int, optional, default: 10
        To select the station that contain at least a number of years between the first date and the last date.
        :param missing_percentage: int,float, optional, default: 5
        To select the stations that contain until a chosen percentage of missing values. A number between 0 and 100
        :param start_date:int, float, str, optional, default: False
        The desired start date for the output DataFrame
        :param end_date: int, float, str, optional, default: False
        The desired end date for the output DataFrame
        For start_date and end_date format, see: pandas.to_datetime documentation
        :return: Pandas DataFrame after going through the filtering methods
        """
        # If the start and/or end date is given this step selects the temporal window in the dataset
        if start_date != False and end_date != False:
            start_date = pd.to_datetime([start_date])
            end_date = pd.to_datetime([end_date])
            data = data.loc[start_date[0]:end_date[0]]
        elif start_date:
            start_date = pd.to_datetime([start_date])
            data = data.loc[start_date[0]:]
        elif end_date:
            end_date = pd.to_datetime([end_date])
            data = data.loc[:end_date[0]]

        # This step selects the stations with at least n_years between the first date and the last date of the station.
        stations = []
        for column in data.columns:
            series = data[column]
            series_drop = series.dropna()
            if len(series_drop) > 0:
                years = (series_drop.index[-1] - series_drop.index[0]) / np.timedelta64(1, 'Y')
                if years >= n_years:
                    stations.append(column)
        data = data[stations]

        # This last step looks for at least a temporal window with until missing_percentage of missing data.
        stations = []
        state = 0
        for column in tqdm(data.columns):
            series = data[column]
            series_drop = series.dropna()
            periods = []
            start1 = series_drop.index[0]
            finish1 = 0
            for i in range(len(series_drop)):
                if i != 0 and (series_drop.index[i] - series_drop.index[i - 1]) / np.timedelta64(1, 'D') != 1:
                    finish1 = series_drop.index[i - 1]
                    periods.append(
                        dict(Start=start1, Finish=finish1, Interval=(finish1 - start1) / np.timedelta64(1, 'Y')))
                    start1 = series_drop.index[i]
                    finish1 = 0
            finish1 = series_drop.index[-1]
            periods.append(dict(Start=start1, Finish=finish1, Interval=(finish1 - start1) / np.timedelta64(1, 'Y')))
            periods = pd.DataFrame(periods)
            if len(periods[periods['Interval'] >= n_years]) > 0:
                stations.append(column)
            else:
                j = 0
                aux = 0
                while j < len(periods) and aux == 0:
                    j += 1
                    if periods['Start'][j] + relativedelta(years=n_years) <= periods['Finish'][periods.index[-1]]:
                        series_period = series.loc[
                                        periods['Start'][j]:periods['Start'][j] + relativedelta(years=n_years)]
                        missing = series_period.isnull().sum() / len(series_period)
                        if missing <= missing_percentage / 100 and aux == 0:
                            aux = 1
                            stations.append(column)
                    else:
                        aux = 1
            state += 1
        data = data[stations]
        return data

    @staticmethod
    def daily_to_monthly(data):
        """
        Transform a time series of daily data into a time series accumulated monthly. A month with a day missing data is
         considered as a missing month in the conversion process.
        :param data: A Pandas daily DataFrame with DatetimeIndex where each column corresponds to a station.
        :return: A pandas monthly DataFrame.
        """
        monthly_data = pd.DataFrame()
        for column in data.columns:
            series = data[column]
            monthly_series = series.groupby(pd.Grouper(freq='1MS')).sum().to_frame()
            missing = series.isnull().groupby(pd.Grouper(freq='1MS')).sum().to_frame()
            to_drop = missing.loc[missing[column] > 0]  # A month with a missing data is a missing month
            monthly_series = monthly_series.drop(index=to_drop.index).sort_index()
            data_index = pd.date_range(monthly_series.index[0], monthly_series.index[-1], freq='MS')
            monthly_series = monthly_series.reindex(data_index)
            monthly_data = pd.concat([monthly_data, monthly_series], axis=1)
        return monthly_data
