import pandas as pd
import requests
import xml.etree.ElementTree as ET
from tqdm import tqdm
import numpy as np


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
    def __data_ana(list_station, data_type, only_consisted, threads=10, **kwargs):
        from .ana import ANA as ANAService
        start, end = kwargs.pop("start", None), kwargs.pop("end", None)
        client = ANAService(**kwargs)
        method = {"1": client.stage, "2": client.prec, "3": client.flow}[data_type]
        return method(list_station, only_consisted=only_consisted, start=start, end=end)

    @staticmethod
    def prec_data(list_station, only_consisted=False, **kwargs):
        """Alias histórico de prec()."""
        return ANA.prec(list_station, only_consisted=only_consisted, **kwargs)

    @staticmethod
    def stage_data(list_station, only_consisted=False, **kwargs):
        """Alias histórico de stage()."""
        return ANA.stage(list_station, only_consisted=only_consisted, **kwargs)

    @staticmethod
    def flow_data(list_station, only_consisted=False, **kwargs):
        """Alias histórico de flow()."""
        return ANA.flow(list_station, only_consisted=only_consisted, **kwargs)

    @staticmethod
    def prec(list_station, only_consisted=False, threads=10, **kwargs):
        """
        Get the precipitation station data series from a list of stations code.
        Parameters
        ----------
        list_station : list of strings
            A list of with the stations code as strings.
        only_consisted : boolean, default False
            If True, returns only the data classified as consistent by the provider.
        threads: int
            Mantido por compatibilidade; consultas convencionais são sequenciais.
        **kwargs:
            source ('auto', 'rest', 'legacy'), identifier, password, timeout, start e end.
            Sem datas explícitas, consulta toda a abrangência do inventário.
        Returns
        -------
        data_stations : pandas DataFrame
            The data of each station as a column in a pandas DataFrame
        """

        data_stations = ANA.__data_ana(list_station, '2', only_consisted=only_consisted, threads=threads, **kwargs)

        return data_stations

    @staticmethod
    def stage(list_station, only_consisted=False, threads=10, **kwargs):
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
            Mantido por compatibilidade; consultas convencionais são sequenciais.
        **kwargs:
            source ('auto', 'rest', 'legacy'), identifier, password, timeout, start e end.
            Sem datas explícitas, consulta toda a abrangência do inventário.
        Returns
        -------
        data_stations : pandas DataFrame
            The data of each station as a column in a pandas DataFrame
        """

        data_stations = ANA.__data_ana(list_station, '1', only_consisted=only_consisted, threads=threads, **kwargs)
        return data_stations

    @staticmethod
    def flow(list_station, only_consisted=False, threads=10, **kwargs):
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
            Mantido por compatibilidade; consultas convencionais são sequenciais.
        **kwargs:
            source ('auto', 'rest', 'legacy'), identifier, password, timeout, start e end.
            Sem datas explícitas, consulta toda a abrangência do inventário.
        Returns
        -------
        data_stations : pandas DataFrame
            The data os each station as a column in a pandas DataFrame
        """
        data_stations = ANA.__data_ana(list_station, '3', only_consisted=only_consisted, threads=threads, **kwargs)
        return data_stations

    @staticmethod
    def telemetric(station_code, threads=10, start=None, end=None, detailed=False, **kwargs):
        """Retorna telemetria de uma estação; ``threads`` é mantido por compatibilidade."""
        from .ana import ANA as ANAService
        return ANAService(**kwargs).telemetry(station_code, start=start, end=end, detailed=detailed)

    @staticmethod
    def stations(uf=None, basin=None, station=None, name=None, river=None, city=None, all_states=False, **kwargs):
        """Delega a busca de estações ao inventário atualizado da ANA."""
        from .ana import ANA as ANAService
        return ANAService(**kwargs).stations(uf, basin, station, name, river, city, all_states)

    @staticmethod
    def _extra(method, station, start=None, end=None, **kwargs):
        from .ana import ANA as ANAService
        return getattr(ANAService(**kwargs), method)(station, start, end)

    @staticmethod
    def quality(station, start=None, end=None, **kwargs):
        return ANA._extra("quality", station, start, end, **kwargs)

    @staticmethod
    def sediment(station, start=None, end=None, **kwargs):
        return ANA._extra("sediment", station, start, end, **kwargs)

    @staticmethod
    def discharge_measurements(station, start=None, end=None, **kwargs):
        return ANA._extra("discharge_measurements", station, start, end, **kwargs)

    @staticmethod
    def rating_curves(station, start=None, end=None, **kwargs):
        return ANA._extra("rating_curves", station, start, end, **kwargs)

    @staticmethod
    def cross_sections(station, start=None, end=None, **kwargs):
        return ANA._extra("cross_sections", station, start, end, **kwargs)

    @staticmethod
    def grain_size(station, start=None, end=None, **kwargs):
        return ANA._extra("grain_size", station, start, end, **kwargs)

class INMET:
    """Interface compatível para a implementação WIS2 atual do INMET."""

    @staticmethod
    def list_stations(station_type="both", **kwargs):
        """Lista estações WIGOS; ``station_type`` aceita both, automatic ou conventional."""
        from .inmet import INMET as INMETService
        choices = {"both": None, "automatic": "hourly", "conventional": "manual"}
        if station_type not in choices:
            raise ValueError("station_type deve ser both, automatic ou conventional.")
        client = INMETService(timeout=kwargs.pop("timeout", 60), session=kwargs.pop("session", None),
                              page_size=kwargs.pop("page_size", 10000))
        return client.official_stations(station_type)

    @staticmethod
    def hourly_data(station_code, threads=10, start=None, end=None, variables=None, long=False, **kwargs):
        """Obtém SYNOP horário no WIS2; ``threads`` é mantido por compatibilidade."""
        from .inmet import INMET as INMETService
        client = INMETService(timeout=kwargs.pop("timeout", 60), session=kwargs.pop("session", None),
                              page_size=kwargs.pop("page_size", 10000))
        return client.hourly(station_code, start, end, variables, long)

    @staticmethod
    def daily_data(station_code, filter=True, threads=10, start=None, end=None, variables=None, long=False, **kwargs):
        """Obtém valores climáticos diários DAYCLI no WIS2; argumentos antigos são aceitos por compatibilidade."""
        from .inmet import INMET as INMETService
        client = INMETService(timeout=kwargs.pop("timeout", 60), session=kwargs.pop("session", None),
                              page_size=kwargs.pop("page_size", 10000))
        return client.daily(station_code, start, end, variables, long)


class ONS:
    """
    Provide data from the National Electric System Operator (Operador Nacional do Sistema Elétrico - ONS) database.
    """

    @staticmethod
    def daily_data(start="2000-01-01", end=None, reservoirs=None, refresh=False, **kwargs):
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
        from .ons import ONS as ONSService
        return ONSService(**kwargs).natural_flow(start, end, reservoirs, refresh)

    @staticmethod
    def hydraulic_data(start="2000-01-01", end=None, reservoirs=None, variables=None, refresh=False, **kwargs):
        """Retorna todas as grandezas hidráulicas diárias publicadas pelo ONS."""
        from .ons import ONS as ONSService
        return ONSService(**kwargs).daily_hydraulic_data(start, end, reservoirs, variables, refresh)

    @staticmethod
    def hourly_data(start=None, end=None, reservoirs=None, variables=None, refresh=False, **kwargs):
        """Retorna todas as grandezas hidráulicas horárias publicadas pelo ONS."""
        from .ons import ONS as ONSService
        return ONSService(**kwargs).hourly_hydraulic_data(start, end, reservoirs, variables, refresh)

    @staticmethod
    def reservoirs(refresh=False, **kwargs):
        """Retorna o cadastro atual de reservatórios do ONS."""
        from .ons import ONS as ONSService
        return ONSService(**kwargs).reservoirs(refresh)


class SAR:
    """Compatibilidade com a interface atual do Sistema de Acompanhamento de Reservatórios."""

    @staticmethod
    def reservoirs(system="sin", **kwargs):
        from .sar import SAR as SARService
        return SARService(**kwargs).reservoirs(system)

    @staticmethod
    def history(reservoir, start, end, system="sin", **kwargs):
        from .sar import SAR as SARService
        return SARService(**kwargs).history(reservoir, start, end, system)


class CEMADEN:
    """Compatibilidade com a interface atual da Plataforma de Entrega de Dados."""

    @staticmethod
    def stations(**kwargs):
        from .cemaden import CEMADEN as CEMADENService
        client_keys = {key: kwargs.pop(key) for key in list(kwargs)
                       if key in {"email", "password", "token", "partner", "timeout", "session"}}
        return CEMADENService(**client_keys).stations(**kwargs)

    @staticmethod
    def data(station, start, end, sensor=None, network=11, **kwargs):
        from .cemaden import CEMADEN as CEMADENService
        return CEMADENService(**kwargs).data(station, start, end, sensor=sensor, network=network)

    @staticmethod
    def recent(uf, **kwargs):
        from .cemaden import CEMADEN as CEMADENService
        client_keys = {key: kwargs.pop(key) for key in list(kwargs)
                       if key in {"email", "password", "token", "partner", "timeout", "session"}}
        return CEMADENService(**client_keys).recent(uf, **kwargs)
