import os
import pandas as pd
import locale


class SaveAs:

    @staticmethod
    def asc_daily_prec(data, path_save):
        """
        Save each column of the precipitation stations DataFrame into a ".txt" file in the ASCII standard.

        Parameters
        ----------
        data : pandas DataFrame
            A Pandas daily DataFrame with DatetimeIndex where each column corresponds to a station.
        path_save: string
            The computer location where the ".txt" files will be saved.

        Returns
        -------
        """

        if not os.path.exists(path_save):
            os.makedirs(path_save)
        stations = list(data.columns.values)
        for i in range(len(stations)):
            file_name = str(stations[i])
            while len(file_name) < 8:
                file_name = '0' + file_name
            file_name = file_name + '.txt'
            df = data[stations[i]].to_frame().round(2)
            df = df.dropna()
            date_index = pd.date_range(df.index[0], df.index[-1], freq='D')
            df = df.reindex(date_index)
            df = df.fillna(-1.00)
            df = df.round(decimals=2)
            arq = open(os.path.join(os.path.join(os.getcwd(), path_save), file_name), 'w')
            list_dado = []
            for j in df.index:
                dado = df[stations[i]][j]
                list_dado.append(dado)
                arq.write('{:>6}{:>6}{:>6}{:>12}\n'.format(j.day, j.month, j.year, format(dado, '.2f')))
            arq.close()

    @staticmethod
    def asc_daily_flow(data, path_save):
        """
        Save each column of the flow stations DataFrame into a ".txt" file in the ASCII standard.

        Parameters
        ----------
        data : pandas DataFrame
            A Pandas daily DataFrame with DatetimeIndex where each column corresponds to a station.
        path_save: string
            The computer location where the ".txt" files will be saved.

        Returns
        -------
        """

        locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
        if not os.path.exists(path_save):
            os.makedirs(path_save)
        stations = list(data.columns.values)
        for i in range(len(stations)):
            file_name = str(stations[i])
            while len(file_name) < 8:
                file_name = '0' + file_name
            file_name = file_name + '.txt'
            df = data[stations[i]].to_frame().round(6)
            df = df.dropna()
            date_index = pd.date_range(df.index[0], df.index[-1], freq='D')
            df = df.reindex(date_index)
            df = df.fillna(-1.00)
            df = df.round(decimals=6)
            arq = open(os.path.join(os.path.join(os.getcwd(), path_save), file_name), 'w')
            for j in df.index:
                dado = df[stations[i]][j]
                dado = locale.format_string('%.6f', dado, True)
                if len(dado) < 11:
                    arq.write('{:>6}{:>6}{:>6}{:>16}\n'.format(j.day, j.month, j.year, dado))
                else:
                    arq.write('{:>6}{:>6}{:>6}{:>18}\n'.format(j.day, j.month, j.year, dado))
            arq.close()
