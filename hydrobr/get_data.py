import calendar
import json
import pandas as pd
import requests
import xml.etree.ElementTree as ET
from tqdm import tqdm


class ANA:
    """
    It provides a connection with the Brazilian National Water Agency (Agência Nacional de Águas - ANA) database
    """

    def __init__(self):
        pass

    @staticmethod
    def __list_ana(params):
        check_params = ['codEstDE', 'codEstATE', 'tpEst', 'nmEst', 'nmRio', 'codSubBacia',
                        'codBacia', 'nmMunicipio', 'nmEstado', 'sgResp', 'sgOper', 'telemetrica']
        if list(params.keys()) != check_params:
            raise Exception('You must pass the dictionary with the standard keys.')

        response = requests.get('http://telemetriaws1.ana.gov.br/ServiceANA.asmx/HidroInventario', params, timeout=20.0)
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
    def list_flow_stations(state='', city='', source='ANA'):
        """
        Searches for flow/stage stations registered at the Brazilian National Agency of Water inventory.
        
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

        Returns
        -------
        list_stations : pandas DataFrame
            The selected list of stations as a pandas DataFrame
        """

        if source == 'ANA':
            params = {'codEstDE': '', 'codEstATE': '', 'tpEst': '1', 'nmEst': '', 'nmRio': '', 'codSubBacia': '',
                      'codBacia': '', 'nmMunicipio': city, 'nmEstado': state, 'sgResp': '', 'sgOper': '',
                      'telemetrica': ''}
            list_stations = Stations.__list_ana(params)
        elif souce == 'ANAF':
            path = os.path.dirname(os.path.abspath(__file__))
            file_path = os.path.join(path, 'resources', 'ANAF_flow_stations.pkl')
            list_stations = pd.read_csv(file_path)
            if city != '':
                list_stations = list_stations[list_stations['City'] == city]
            if state != '':
                list_stations = list_stations[list_stations['State'] == state]

        else:
            raise Exception('Please, select a valid source.')

        return list_stations

    @staticmethod
    def list_prec_stations(state='', city='', source='ANA'):
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

        Returns
        -------
        list_stations : pandas DataFrame
            The selected list of stations as a pandas DataFrame
        """

        if source == 'ANA':
            params = {'codEstDE': '', 'codEstATE': '', 'tpEst': '2', 'nmEst': '', 'nmRio': '', 'codSubBacia': '',
                      'codBacia': '', 'nmMunicipio': city, 'nmEstado': state, 'sgResp': '', 'sgOper': '',
                      'telemetrica': ''}
            list_stations = Stations.__list_ana(params)
        elif source == 'ANAF':
            path = os.path.dirname(os.path.abspath(__file__))
            file_path = os.path.join(path, 'resources', 'ANAF_prec_stations.pkl')
            list_stations = pd.read_csv(file_path)
            if city != '':
                list_stations = list_stations[list_stations['City'] == city]
            if state != '':
                list_stations = list_stations[list_stations['State'] == state]
        else:
            raise Exception('Please, select a valid source.')

        return list_stations

    @staticmethod
    def __data_ana(list_station, data_type, only_consisted):
        params = {'codEstacao': '', 'dataInicio': '', 'dataFim': '', 'tipoDados': data_type, 'nivelConsistencia': ''}
        data_types = {'3': ['Vazao{:02}'], '2': ['Chuva{:02}'], '1': ['Cota{:02}']}
        data_stations = []
        for station in tqdm(list_station):
            params['codEstacao'] = str(station)
            try:
                response = requests.get('http://telemetriaws1.ana.gov.br/ServiceANA.asmx/HidroSerieHistorica', params,
                                        timeout=60.0)
            except (
                    requests.ConnectTimeout, requests.HTTPError, requests.ReadTimeout, requests.Timeout,
                    requests.ConnectionError):
                continue

            tree = ET.ElementTree(ET.fromstring(response.content))
            root = tree.getroot()
            df = []
            for month in root.iter('SerieHistorica'):
                code = month.find('EstacaoCodigo').text
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
                df.append(pd.DataFrame({f'{int(code):08}': data}, index=index_multi))
            if (len(df)) == 0:
                continue
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
                    continue
            series = df[f'{int(code):08}']
            date_index = pd.date_range(series.index[0], series.index[-1], freq='D')
            series = series.reindex(date_index)
            data_stations.append(series)
        data_stations = pd.concat(data_stations, axis=1)
        date_index = pd.date_range(data_stations.index[0], data_stations.index[-1], freq='D')
        data_stations = data_stations.reindex(date_index)
        return data_stations

    @staticmethod
    def prec_data(list_station, only_consisted=False):
        """
        Get the precipitation station data series from a list of stations code.

        Parameters
        ----------
        list_station : list of strings
            A list of with the stations code as strings.
        only_consisted : boolean, default False
            If True, returns only the data classified as consistent by the provider.

        Returns
        -------
        data_stations : pandas DataFrame
            The data os each station as a column in a pandas DataFrame
        """

        data_stations = Stations.__data_ana(list_station, '2', only_consisted=only_consisted)

        return data_stations

    @staticmethod
    def stage_data(list_station, only_consisted=False):
        """
        Get the stage station data series from a list of stations code of the Brazilian National Water Agency
        (ANA) database.

        Parameters
        ----------
        list_station : list of strings
            A list of with the stations code as strings.
        only_consisted : boolean, default False
            If True, returns only the data classified as consistent by the provider.

        Returns
        -------
        data_stations : pandas DataFrame
            The data os each station as a column in a pandas DataFrame
        """

        data_stations = Stations.__data_ana(list_station, '1', only_consisted=only_consisted)
        return data_stations

    @staticmethod
    def flow_data(list_station, only_consisted=False):
        """
        Get the flow station data series from a list of stations code of the Brazilian National Water Agency
        (ANA) database.

        Parameters
        ----------
        list_station : list of strings
            A list of with the stations code as strings.
        only_consisted : boolean, default False
            If True, returns only the data classified as consistent by the provider.

        Returns
        -------
        data_stations : pandas DataFrame
            The data os each station as a column in a pandas DataFrame
        """
        data_stations = Stations.__data_ana(list_station, '3', only_consisted=only_consisted)

        return data_stations


class INMET:
    """
    It provides a connection with the  Brazilian National Institute of Meteorology (Instituto Nacional de Meteorologia
     - INMET) database.
    """

    def __init__(self):
        pass

    @staticmethod
    def list_stations(station_type='both'):
        """
        Searches for precipitation stations registered at the Brazilian National Agency of Water (ANA) or the INEMET
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
            responseM = requests.get('https://apitempo.inmet.gov.br/estacoes/M', timeout=20.0)
            responseT = requests.get('https://apitempo.inmet.gov.br/estacoes/T', timeout=20.0)
            list_stations = pd.concat([pd.DataFrame(json.loads(responseM.text)),
                                       pd.DataFrame(json.loads(responseT.text))])
        elif station_type == 'automatic':
            response = requests.get('https://apitempo.inmet.gov.br/estacoes/T', timeout=20.0)
            list_stations = pd.DataFrame(json.loads(response.text))
        elif station_type == 'conventional':
            response = requests.get('https://apitempo.inmet.gov.br/estacoes/M', timeout=20.0)
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
        return list_station
