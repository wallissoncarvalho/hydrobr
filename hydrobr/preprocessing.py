import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta
from tqdm import tqdm


class PreProcessing:

    @staticmethod
    def stations_filter(data, n_years=10, missing_percentage=5, start_date=False, end_date=False):
        """
        A composed method to filter stations. 
        
        First, the method filters the stations data by the Start Date and the End Date, it its passed. After that, the 
        is selected only the stations with at least a defined number of years between the first date and the last date
        of the station. At the end is selected the stations that contains at least one window of data with the number of
        years and a maximum missing data percentage. 

        Parameters
        ----------
        data : pandas DataFrame
            A Pandas daily DataFrame with DatetimeIndex where each column corresponds to a station.
        n_years: int, default 10
            The minimum number of years of registered data for the station between the first date and the end date.
        missing_percentage: int, default 5
             The maximum missing data percentage in a window with n_years.
             A number between 0 and 100
        start_date : int, float, str, default False
            The desired start date for the output DataFrame.
            See: pandas.to_datetime documentation if have doubts about the date format
        end_date: int, float, str, default False
            The desired end date for the output DataFrame.
            See: pandas.to_datetime documentation if have doubts about the date format

        Returns
        -------
        data : pandas DataFrame
            A pandas DataFrame with only the filtered stations
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
    def daily_to_monthly(data, method='sum'):
        """
        Transform a time series of daily data into a time series monthly data.

        In the conversion process a month with a day missing data is considered as a missing month.

        Parameters
        ----------
        data : pandas DataFrame
            A Pandas daily DataFrame with DatetimeIndex where each column corresponds to a station.
        method: str, default sum
            The method used to convert. If 'sum', the monthly data will be the sum of the daily data. If 'mean', the
            monthly data will be the mean of the daily data.

        Returns
        -------
        monthly_data : pandas DataFrame
            The  monthly pandas DataFrame
        """

        monthly_data = pd.DataFrame()
        for column in data.columns:
            series = data[column]
            if method == 'sum':
                monthly_series = series.groupby(pd.Grouper(freq='1MS')).sum().to_frame()
            elif method == 'mean':
                monthly_series = series.groupby(pd.Grouper(freq='1MS')).mean().to_frame()
            else:
                raise Exception('Please, select a valid method.')
            missing = series.isnull().groupby(pd.Grouper(freq='1MS')).sum().to_frame()
            to_drop = missing.loc[missing[column] > 0]  # A month with a missing data is a missing month
            monthly_series = monthly_series.drop(index=to_drop.index).sort_index()
            data_index = pd.date_range(monthly_series.index[0], monthly_series.index[-1], freq='MS')
            monthly_series = monthly_series.reindex(data_index)
            monthly_data = pd.concat([monthly_data, monthly_series], axis=1)
        return monthly_data
