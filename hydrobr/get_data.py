import calendar
import datetime
import json
import pandas as pd
import requests
import xml.etree.ElementTree as ET
from tqdm import tqdm
import numpy as np
from multiprocessing.pool import ThreadPool
import warnings


class ANA:
    """
    It provides a connection with the Brazilian National Water Agency (Agência Nacional de Águas - ANA) database
    """

    @staticmethod
    def __list_ana(params, telemetry=False):
        if telemetry:
            response = requests.get('http://telemetriaws1.ana.gov.br/ServiceANA.asmx/ListaEstacoesTelemetricas', params,
                                    timeout=120.0)
            tree = ET.ElementTree(ET.fromstring(response.content))
            root = tree.getroot()
            list_stations = pd.DataFrame()
            index = 1
            for station in tqdm(root.iter('Table')):
                list_stations.at[index, 'Name'] = station.find('NomeEstacao').text
                code = station.find('CodEstacao').text
                list_stations.at[index, 'Code'] = f'{int(code):08}'
                list_stations.at[index, 'Status'] = station.find('StatusEstacao').text
                list_stations.at[index, 'SubBasin'] = station.find('SubBacia').text
                try:
                    list_stations.at[index, 'City-State'] = station.find('Municipio-UF').text
                except AttributeError:
                    list_stations.at[index, 'City-State'] = np.nan
                list_stations.at[index, 'Origem'] = station.find('Origem').text
                list_stations.at[index, 'Responsible'] = station.find('Responsavel').text
                list_stations.at[index, 'Elevation'] = station.find('Altitude').text
                list_stations.at[index, 'Latitude'] = float(station.find('Latitude').text)
                list_stations.at[index, 'Longitude'] = float(station.find('Longitude').text)
                index += 1
        else:
            check_params = ['codEstDE', 'codEstATE', 'tpEst', 'nmEst', 'nmRio', 'codSubBacia',
                            'codBacia', 'nmMunicipio', 'nmEstado', 'sgResp', 'sgOper', 'telemetrica']
            if list(params.keys()) != check_params:
                raise Exception('You must pass the dictionary with the standard keys.')
            response = requests.get('http://telemetriaws1.ana.gov.br/ServiceANA.asmx/HidroInventario', params,
                                    timeout=120.0)
            tree = ET.ElementTree(ET.fromstring(response.content))
            root = tree.getroot()
            list_stations = pd.DataFrame()
            index = 1
            if params['tpEst'] != '1' and params['tpEst'] != '2':
                raise Exception('Please choose a station type on the tpEst parameter.')
            for station in tqdm(root.iter('Table')):
                list_stations.at[index, 'Name'] = station.find('Nome').text
                code = station.find('Codigo').text
                list_stations.at[index, 'Code'] = f'{int(code):08}'
                list_stations.at[index, 'Type'] = station.find('TipoEstacao').text
                if params['tpEst'] == '1':
                    list_stations.at[index, 'DrainageArea'] = station.find('AreaDrenagem').text
                list_stations.at[index, 'SubBasin'] = station.find('SubBaciaCodigo').text
                list_stations.at[index, 'City'] = station.find('nmMunicipio').text
                list_stations.at[index, 'State'] = station.find('nmEstado').text
                list_stations.at[index, 'Responsible'] = station.find('ResponsavelSigla').text
                list_stations.at[index, 'Latitude'] = float(station.find('Latitude').text)
                list_stations.at[index, 'Longitude'] = float(station.find('Longitude').text)
                index += 1
        return list_stations

    @staticmethod
    def list_flow_stations(state='', city='', source='ANAF'):
        raise DeprecationWarning('The method name have changed. Use list_flow() instead of list_flow_stations()')

    @staticmethod
    def list_prec_stations(state='', city='', source='ANAF'):
        raise DeprecationWarning('The method name have changed. Use list_prec() instead of list_prec_stations()')

    @staticmethod
    def list_flow(state='', city='', source='ANAF'):
        """
        Searches for flow/stage stations registered at the Brazilian National Agency of Water inventory.

        Parameters
        ----------
        state : string
            Brazilian state name where the stations are located (e.g., Rio de Janeiro)
        city : string
            Brazilian city name where the stations are located (e.g., Rio de Itaperuna)
        source: string, default 'ANAF'
            The source to look for the data. 'ANA' to get the list of stations from the Brazilian National Water Agency
            (ANA) database, or 'ANAF' to get the filtered list of stations that contain only the stations from ANA
            with registered data.
            More information about ANAF: https://doi.org/10.5281/zenodo.3755065

        Returns
        -------
        list_stations : pandas DataFrame
            The selected list of stations as a pandas DataFrame
        """

        if source == 'ANA':
            params = {'codEstDE': '', 'codEstATE': '', 'tpEst': '1', 'nmEst': '', 'nmRio': '', 'codSubBacia': '',
                      'codBacia': '', 'nmMunicipio': city, 'nmEstado': state, 'sgResp': '', 'sgOper': '',
                      'telemetrica': ''}
            list_stations = ANA.__list_ana(params)
        elif source == 'ANAF':
            list_stations = pd.read_csv('http://raw.githubusercontent.com/wallissoncarvalho/hydrobr/master/hydrobr/'
                                        'resources/ANAF_flow_stations.csv')
            list_stations.Code = list_stations.Code.apply(lambda x: f'{int(x):08}')
            if city != '':
                list_stations = list_stations[list_stations['City'] == city]
            if state != '':
                list_stations = list_stations[list_stations['State'] == state]

        else:
            raise Exception('Please, select a valid source.')

        return list_stations

    @staticmethod
    def list_prec(state='', city='', source='ANAF'):
        """
        Searches for precipitation stations registered at the Brazilian National Agency of Water (ANA)

        Parameters
        ----------
        state : string
            Brazilian state name where the stations are located (e.g., Rio de Janeiro)
        city : string
            Brazilian city name where the stations are located (e.g., Rio de Itaperuna)
        source: string, default 'ANA'
            The source to look for the data. 'ANA' to get the list of stations from the Brazilian National Water Agency
            (ANA) database, or 'ANAF' to get the filtered list of stations that contain only the stations from ANA
            with registered data.
            More information about ANAF: https://doi.org/10.5281/zenodo.3755065

        Returns
        -------
        list_stations : pandas DataFrame
            The selected list of stations as a pandas DataFrame
        """
        if source == 'ANA':
            params = {'codEstDE': '', 'codEstATE': '', 'tpEst': '2', 'nmEst': '', 'nmRio': '', 'codSubBacia': '',
                      'codBacia': '', 'nmMunicipio': city, 'nmEstado': state, 'sgResp': '', 'sgOper': '',
                      'telemetrica': ''}
            list_stations = ANA.__list_ana(params)
        elif source == 'ANAF':
            list_stations = pd.read_csv('http://raw.githubusercontent.com/wallissoncarvalho/hydrobr/master/hydrobr/'
                                        'resources/ANAF_prec_stations.csv')
            list_stations.Code = list_stations.Code.apply(lambda x: f'{int(x):08}')
            if city != '':
                list_stations = list_stations[list_stations['City'] == city]
            if state != '':
                list_stations = list_stations[list_stations['State'] == state]
        else:
            raise Exception('Please, select a valid source.')

        return list_stations

    @staticmethod
    def list_telemetric():
        """
        Searches for the telemetry stations registered at the Brazilian National Agency of Water inventory.

        Parameters
        ----------

        Returns
        -------
        list_stations : pandas DataFrame
            The list of  all telemtry stations as a pandas DataFrame
        """
        params = {'statusEstacoes': '', 'origem': ''}
        list_stations = ANA.__list_ana(params, telemetry=True)
        return list_stations

    @staticmethod
    def __data_ana(list_station, data_type, only_consisted, threads=10):
        if type(list_station) is not list:
            list_station = [list_station]
        params = {'codEstacao': '', 'dataInicio': '', 'dataFim': '', 'tipoDados': data_type, 'nivelConsistencia': ''}
        data_types = {'3': ['Vazao{:02}'], '2': ['Chuva{:02}'], '1': ['Cota{:02}']}

        def __call_request(station):
            params['codEstacao'] = str(station)
            try:
                response = requests.get('http://telemetriaws1.ana.gov.br/ServiceANA.asmx/HidroSerieHistorica', params,
                                        timeout=120.0)
            except (
                    requests.ConnectTimeout, requests.HTTPError, requests.ReadTimeout, requests.Timeout,
                    requests.ConnectionError):
                return pd.DataFrame()
            except http.client.IncompleteRead:
                try:
                    response = requests.get('http://telemetriaws1.ana.gov.br/ServiceANA.asmx/HidroSerieHistorica',
                                            params,
                                            timeout=120.0)
                except:
                    print('It was not possible to get the station {} data'.format(station))
                    return pd.DataFrame()
            except:
                print('It was not possible to get the station {} data'.format(station))
                return pd.DataFrame()
            try:
                tree = ET.ElementTree(ET.fromstring(response.content))
                root = tree.getroot()
            except:
                return pd.DataFrame()

            df = []
            for month in root.iter('SerieHistorica'):
                code = month.find('EstacaoCodigo').text
                code = f'{int(code):08}'
                consist = int(month.find('NivelConsistencia').text)
                date = pd.to_datetime(month.find('DataHora').text, dayfirst=True)
                date = pd.Timestamp(date.year, date.month, 1, 0)
                last_day = calendar.monthrange(date.year, date.month)[1]
                month_dates = pd.date_range(date, periods=last_day, freq='D')
                data = []
                list_consist = []
                for i in range(last_day):
                    value = data_types[params['tipoDados']][0].format(i + 1)
                    try:
                        data.append(float(month.find(value).text))
                        list_consist.append(consist)
                    except TypeError:
                        data.append(month.find(value).text)
                        list_consist.append(consist)
                    except AttributeError:
                        data.append(None)
                        list_consist.append(consist)
                index_multi = list(zip(month_dates, list_consist))
                index_multi = pd.MultiIndex.from_tuples(index_multi, names=["Date", "Consistence"])
                df.append(pd.DataFrame({code: data}, index=index_multi))
            if (len(df)) == 0:
                return pd.DataFrame()
            df = pd.concat(df)
            df = df.sort_index()
            if not only_consisted:
                drop_index = df.reset_index(level=1, drop=True).index.duplicated(keep='last')
                df = df[~drop_index]
                df = df.reset_index(level=1, drop=True)
            else:
                df = df[df.index.get_level_values(1) == 2]
                df = df.reset_index(level=1, drop=True)
                if (len(df)) == 0:
                    return pd.DataFrame()
            series = df[code]
            date_index = pd.date_range(series.index[0], series.index[-1], freq='D')
            series = series.reindex(date_index)
            return series

        if len(list_station) < threads:
            threads = len(list_station)

        with ThreadPool(threads) as pool:
            responses = list(tqdm(pool.imap(__call_request, list_station), total=len(list_station)))
        responses = [response for response in responses if not response.empty]
        data_stations = pd.concat(responses, axis=1)
        date_index = pd.date_range(data_stations.index[0], data_stations.index[-1], freq='D')
        data_stations = data_stations.reindex(date_index)
        return data_stations

    @staticmethod
    def prec_data(list_station, only_consisted=False):
        raise DeprecationWarning('The method name have changed. Use prec() instead of prec_data()')

    @staticmethod
    def stage_data(list_station, only_consisted=False):
        raise DeprecationWarning('The method name have changed. Use stage() instead of stage_data()')

    @staticmethod
    def flow_data(list_station, only_consisted=False):
        raise DeprecationWarning('The method name have changed. Use flow() instead of flow_data()')

    @staticmethod
    def prec(list_station, only_consisted=False, threads=10):
        """
        Get the precipitation station data series from a list of stations code.

        Parameters
        ----------
        list_station : list of strings
            A list of with the stations code as strings.
        only_consisted : boolean, default False
            If True, returns only the data classified as consistent by the provider.
        threads: int
            Number of parallel requisitions

        Returns
        -------
        data_stations : pandas DataFrame
            The data of each station as a column in a pandas DataFrame
        """

        data_stations = ANA.__data_ana(list_station, '2', only_consisted=only_consisted, threads=threads)

        return data_stations

    @staticmethod
    def stage(list_station, only_consisted=False, threads=10):
        """
        Get the stage station data series from a list of stations code of the Brazilian National Water Agency
        (ANA) database.

        Parameters
        ----------
        list_station : list of strings
            A list of with the stations code as strings.
        only_consisted : boolean, default False
            If True, returns only the data classified as consistent by the provider.
        threads: int
            Number of parallel requisitions

        Returns
        -------
        data_stations : pandas DataFrame
            The data of each station as a column in a pandas DataFrame
        """

        data_stations = ANA.__data_ana(list_station, '1', only_consisted=only_consisted, threads=threads)
        return data_stations

    @staticmethod
    def flow(list_station, only_consisted=False, threads=10):
        """
        Get the flow station data series from a list of stations code of the Brazilian National Water Agency
        (ANA) database.

        Parameters
        ----------
        list_station : list of strings
            A list of with the stations code as strings.
        only_consisted : boolean, default False
            If True, returns only the data classified as consistent by the provider.
        threads: int
            Number of parallel requisitions

        Returns
        -------
        data_stations : pandas DataFrame
            The data os each station as a column in a pandas DataFrame
        """
        data_stations = ANA.__data_ana(list_station, '3', only_consisted=only_consisted, threads=threads)
        return data_stations

    @staticmethod
    def telemetric(station_code, threads=10):
        """
        Get the Precipitation, Stage and Flow data for the ANA's telemetric stations as a DataFrame.

        Parameters
        ----------
        station_code : str
            The station code a string.
        threads: int
            Number of parallel requisitions

        Returns
        -------
        data_station : pandas DataFrame
            The data os each station as a column in a pandas DataFrame
        """

        if type(station_code) is not str:
            raise Exception('This function only returns data for a single station at a time. The station_code must be '
                            'a string.')
        # Defining dates
        start = pd.to_datetime('01/01/1950').strftime("%Y-%m-%d")
        start_dates = pd.date_range(start=start, end=pd.to_datetime("today"), freq='180D').to_list()
        if start_dates[0].strftime("%Y-%m-%d") != start:
            start_dates.insert(0, pd.to_datetime(start))
        end_dates = []
        for i in range(len(start_dates) - 1):
            end_dates.append(start_dates[i + 1] + datetime.timedelta(days=-1))
        end_dates.append(pd.to_datetime("today"))

        def __call_request(date):
            params = {'codEstacao': str(station_code), 'dataInicio': date[0].strftime("%d-%m-%Y"),
                      'dataFim': date[1].strftime("%d-%m-%Y")}
            try:
                response = requests.get('http://telemetriaws1.ana.gov.br/ServiceANA.asmx/DadosHidrometeorologicos',
                                        params, timeout=120.0)
            except:
                raise Exception('It was not possible to get the data, please verify your connection and try again.')

            try:
                tree = ET.ElementTree(ET.fromstring(response.content))
                root = tree.getroot()
            except:
                return pd.DataFrame()
            date, prec, stage, flow = [], [], [], []
            for data in root.iter('DadosHidrometereologicos'):
                date.append(pd.to_datetime(data.find('DataHora').text, format="%Y-%m-%d %H:%M:%S"))
                prec.append(data.find('Chuva').text)
                stage.append(data.find('Nivel').text)
                flow.append(data.find('Vazao').text)
            df = pd.DataFrame({'Precipitation': prec, 'Stage': stage, 'Flow': flow}, index=date)
            df.Precipitation = df.Precipitation.astype(float)
            df.Stage = df.Stage.astype(float)
            df.Flow = df.Flow.astype(float)
            return df

        iteration = [(start_date, end_date) for start_date, end_date in zip(start_dates, end_dates)]
        with ThreadPool(threads) as pool:
            responses = list(tqdm(pool.imap(__call_request, iteration), total=len(iteration)))
        responses = [response for response in responses if not response.empty]
        if len(responses) == 0:
            warnings.warn('There is no data available for this stations')
            return pd.DataFrame()
        data_station = pd.concat(responses)
        data_station = data_station.sort_index()
        return data_station

class INMET:
    """
    It provides a connection with the  Brazilian National Institute of Meteorology (Instituto Nacional de Meteorologia
     - INMET) database.
    """

    @staticmethod
    def list_stations(station_type='both'):
        """
        Searches for precipitation stations registered at the Brazilian National Agency of Water (ANA) or the INMET
        inventory.

        Parameters
        ----------
        station_type : string, default 'both'
            The type of station. 'both' to get the list of automatic and manual gauge stations, 'automatic' to get only
            the automatic gauge stations, and 'conventional' to get only the conventional gauge stations.
        Returns
        -------
        list_stations : pandas DataFrame
            The selected list of stations as a pandas DataFrame
        """

        if station_type == 'both':
            responseM = requests.get('https://apitempo.inmet.gov.br/estacoes/M', timeout=120.0)
            responseT = requests.get('https://apitempo.inmet.gov.br/estacoes/T', timeout=120.0)
            list_stations = pd.concat([pd.DataFrame(json.loads(responseM.text)),
                                       pd.DataFrame(json.loads(responseT.text))])
        elif station_type == 'automatic':
            response = requests.get('https://apitempo.inmet.gov.br/estacoes/T', timeout=120.0)
            list_stations = pd.DataFrame(json.loads(response.text))
        elif station_type == 'conventional':
            response = requests.get('https://apitempo.inmet.gov.br/estacoes/M', timeout=120.0)
            list_stations = pd.DataFrame(json.loads(response.text))
        else:
            raise Exception('Please, select a valid station type.')

        list_stations['TP_ESTACAO'].replace({'Automatica': 'Automatic', 'Convencional': 'Conventional'}, inplace=True)
        list_stations.rename(columns={'CD_ESTACAO': 'Code', 'TP_ESTACAO': 'Type', 'DC_NOME': 'Name',
                                      'SG_ESTADO': 'State', 'VL_LATITUDE': 'Latitude', 'VL_LONGITUDE': 'Longitude',
                                      'VL_ALTITUDE': 'Height', 'DT_INICIO_OPERACAO': 'Start Operation',
                                      'DT_FIM_OPERACAO': 'End Operation'},
                             inplace=True)
        list_stations = list_stations[
            ['Code', 'Type', 'Name', 'State', 'Latitude', 'Longitude', 'Height', 'Start Operation', 'End Operation']]
        list_stations['Start Operation'] = pd.to_datetime(list_stations['Start Operation'])
        list_stations['End Operation'] = pd.to_datetime(list_stations['End Operation']).replace(
            {pd.NaT: 'In operation'})
        return list_stations

    @staticmethod
    def daily_data(station_code, filter=True, threads=10):
        """
        Searches for all the data of a station registered at the Brazilian National Institute of Meteorology
        (Instituto Nacional de Meteorologia - INMET) database.

        Returns a pandas daily DataFrame with six variables for each day:
            - Prec - Precipitation (mm)
            - Tmean - Daily mean Temperature (ºC)
            - Tmax - Maximum Temperature (ºC)
            - Tmin - Minimum Temperature (ºC)
            - RH - Relative Humidity (%)
            - SD - Sunshine Duration (hours)

        Parameters
        ----------
        station_code : string
            Code of the station as a string
        filter: boolean, default True
            There is stations with repeated registered data. If 'True' the function returns a panda DataFrame
            with the first occurrence of the date. If 'False' return a pandas DataFrame with, in some cases, repeated
            datetime index.
        threads: int
            Number of parallel requisitions

        Returns
        -------
        data : pandas DataFrame
            The data of the selected station as a pandas DataFrame
        """
        list_stations = INMET.list_stations()
        station = list_stations[list_stations.Code == station_code]
        if len(station) == 0:
            raise Exception('Please input a valid station code')

        # Defining dates
        start = station['Start Operation'].to_list()[0].strftime("%Y-%m-%d")
        start_dates = pd.date_range(start=start, end=pd.to_datetime("today"), freq='60D').to_list()
        if start_dates[0].strftime("%Y-%m-%d") != start:
            start_dates.insert(0, pd.to_datetime(start))
        end_dates = []
        for i in range(len(start_dates) - 1):
            end_dates.append(start_dates[i + 1] + datetime.timedelta(days=-1))
        end_dates.append(pd.to_datetime("today"))

        def __call_request(date):
            start_date = date[0]
            end_date = date[1]
            try:
                response = requests.get('https://apitempo.inmet.gov.br/estacao/diaria/{}/{}/{}'.format(
                    start_date.strftime("%Y-%m-%d"),
                    end_date.strftime("%Y-%m-%d"),
                    station_code),
                    timeout=120.0)
                response = pd.DataFrame(json.loads(response.text))
            except:
                raise Exception('It was not possible to get the data, please verify your connection and try again.')
            return response

        # Getting the data
        iteration = [(start_date, end_date) for start_date, end_date in zip(start_dates, end_dates)]
        with ThreadPool(threads) as pool:
            responses = list(tqdm(pool.imap(__call_request, iteration), total=len(iteration)))
        data_station = pd.concat(responses)
        data_station.rename(
            columns={'CHUVA': 'Prec', 'TEMP_MAX': 'Tmax', 'TEMP_MED': 'Tmean', 'TEMP_MIN': 'Tmin', 'UMID_MED': 'RHmean',
                     'UMID_MIN': 'RHmin', 'UMID_MAX': 'RHmax', 'INSOLACAO': 'SD', 'DT_MEDICAO': 'Date'}, inplace=True)
        data_station.index = pd.to_datetime(data_station.Date)
        data_station.drop(['UF', 'Date', 'DC_NOME', 'CD_ESTACAO', 'VL_LATITUDE', 'VL_LONGITUDE'], axis=1, inplace=True)
        data_station = data_station[sorted(data_station.columns)]
        data_station[data_station.columns] = data_station[data_station.columns].apply(pd.to_numeric, errors='coerce')
        data_station = data_station.dropna(how='all', axis=0)
        if filter:
            data_station = data_station.reset_index().drop_duplicates(subset='Date', keep='first').set_index('Date')
            date_index = pd.date_range(data_station.index[0], data_station.index[-1], freq='D')
            data_station = data_station.reindex(date_index)
        data_station = data_station.convert_dtypes()
        data_station = data_station.astype(float)
        return data_station

    @staticmethod
    def hourly_data(station_code, threads=10):
        """
        Searches for all the data of a station registered at the Brazilian National Institute of Meteorology
        (Instituto Nacional de Meteorologia - INMET) database.

        Only works for Automatic Stations.

        Returns a pandas hourly DataFrame with 17 variables for each day:
            - Tins - Instant Temperature (ºC)
            - Tmax - Maximum Temperature (ºC)
            - Tmin - Minimum Temperature (ºC)
            - RHins - Instant Relative Humidity (%)
            - RHmax - Maximum Relative Humidity (%)
            - RHmin - Minimum Relative Humidity (%)
            - DPins - Instant Dew Point Temperature (ºC)
            - DPmax - Maximum Dew Point Temperature (ºC)
            - DPmin - Minimum Dew Point Temperature (ºC)
            - Pins - Instant Pressure (hPa)
            - Pmax - Maximum Pressure (hPa)
            - Pmin - Minimum Pressure (hPa)
            - Wspeed - Wind Speed (m/s)
            - Wdir - Wind direction (º)
            - Wgust - Wind gust (m/s)
            - Rad - Global Radiation (kJ/m²)
            - Prec - Precipitation (mm)

        Parameters
        ----------
        station_code : string
            Code of the station as a string.
        threads: int
            Number of parallel requisitions
        Returns
        -------
        data : pandas DataFrame
            The data of the selected station as a pandas DataFrame.
        """
        list_stations = INMET.list_stations(station_type='automatic')
        station = list_stations[list_stations.Code == station_code]
        if len(station) == 0:
            raise Exception('Please input a valid station code')

        # Defining dates
        start = station['Start Operation'].to_list()[0].strftime("%Y-%m-%d")
        start_dates = pd.date_range(start=start, end=pd.to_datetime("today"), freq='60D').to_list()
        if start_dates[0].strftime("%Y-%m-%d") != start:
            start_dates.insert(0, pd.to_datetime(start))
        end_dates = []
        for i in range(len(start_dates) - 1):
            end_dates.append(start_dates[i + 1] + datetime.timedelta(days=-1))
        end_dates.append(pd.to_datetime("today"))

        def __call_request(date):
            start_date = date[0]
            end_date = date[1]
            try:
                response = requests.get(
                    'https://apitempo.inmet.gov.br/estacao/{}/{}/{}'.format(start_date.strftime("%Y-%m-%d"),
                                                                            end_date.strftime("%Y-%m-%d"),
                                                                            station_code), timeout=120.0)
                response = pd.DataFrame(json.loads(response.text))
            except:
                raise Exception('It was not possible to get the data, please verify your connection and try again.')
            return response

        # Getting the data
        iteration = [(start_date, end_date) for start_date, end_date in zip(start_dates, end_dates)]
        with ThreadPool(threads) as pool:
            responses = list(tqdm(pool.imap(__call_request, iteration), total=len(iteration)))

        data_station = pd.concat(responses)
        data_station['Date'] = pd.to_datetime(
            data_station['DT_MEDICAO'] + data_station['HR_MEDICAO'].apply(lambda x: ' ' + x[:2]))
        data_station.index = data_station['Date']
        data_station.rename(columns={'CHUVA': 'Prec', 'TEM_MAX': 'Tmax', 'TEM_INS': 'Tins', 'TEM_MIN': 'Tmin',
                                     'PRE_INS': 'Pins', 'PRE_MAX': 'Pmax', 'PRE_MIN': 'Pmin', 'PTO_INS': 'DPins',
                                     'PTO_MAX': 'DPmax',
                                     'PTO_MIN': 'DPmin', 'UMD_INS': 'RHins', 'UMD_MAX': 'RHmax', 'UMD_MIN': 'RHmin',
                                     'VEN_DIR': 'Wdir',
                                     'VEN_RAJ': 'Wgust', 'VEN_VEL': 'Wspeed', 'RAD_GLO': 'Rad'}, inplace=True)
        data_station = data_station[
            ['Tins', 'Tmax', 'Tmin', 'RHins', 'RHmax', 'RHmin', 'DPins', 'DPmax', 'DPmin', 'Pins', 'Pmax', 'Pmin',
             'Wspeed', 'Wdir', 'Wgust', 'Rad', 'Prec']]

        # Cleaning the data
        data_station = data_station.dropna(how='all', axis=0)
        data_station = data_station.reset_index().drop_duplicates(subset='Date', keep='first').set_index('Date')
        date_index = pd.date_range(data_station.index[0], data_station.index[-1], freq='H')
        data_station = data_station.reindex(date_index)
        data_station = data_station.sort_index()
        data_station = data_station.convert_dtypes()
        data_station = data_station.astype(float)
        return data_station


class ONS:
    """
    Provide data from the National Electric System Operator (Operador Nacional do Sistema Elétrico - ONS) database.
    """

    @staticmethod
    def daily_data():
        """
         Returns all the naturalized daily flow data of different reservoirs from the National Electric System Operator
         (Operador Nacional do Sistema Elétrico - ONS) database.

        Parameters
        ----------

        Returns
        -------
        data : pandas DataFrame
            All the naturalized daily flow data as a pandas DataFrame, where each column refers to a specific reservoir.
        """
        data = pd.read_csv('http://raw.githubusercontent.com/wallissoncarvalho/hydrobr/master/hydrobr/'
                           'resources/ONS_daily_flow.csv')
        data.index = pd.to_datetime(data.Date)
        data.drop('Date', axis=1, inplace=True)
        return data
