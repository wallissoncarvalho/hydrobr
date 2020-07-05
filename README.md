# HydroBr [![DOI](https://zenodo.org/badge/276715050.svg)](https://zenodo.org/badge/latestdoi/276715050) [![PythonVersion](https://img.shields.io/badge/python-3.6%20%7C%203.7%20%7C%203.8-blue)](https://img.shields.io/badge/python-3.6%20%7C%203.7%20%7C%203.8-blue)

HydroBr is an open-source package to work with Brazilian hydrometeorological time series.

Introduction
------------
HydroBr is an open-source package for work with Brazilian hydrometeorological time series in Python. This package
provides a connection with the Brazilian  National Water Agency (Agência Nacional de Águas - ANA), the Brazilian
National Institute of Meteorology (Instituto Nacional de Meteorologia - INMET), and the National Electric System
Operator (Operador Nacional do Sistema Elétrico - ONS) databases in order to help users to select, download,
preprocess, and plot hydrometeorological data. 

Installation
------------
The released version of HydroBr is 0.1.0.

To install the released version, use ``pip install hydrobr``.

You may install the latest development version by cloning the
`GitHub` repository and using the setup script::

    git clone https://github.com/wallissoncarvalho/hydrobr.git
    cd hydrobr
    python setup.py install

Modules - Documentation
------------
Currently, the *HydroBr* package has four modules:

* get_data - Functions that provide a connection with the Brazilian National Water Agency
(Agência Nacional de Águas - ANA), the Brazilian National Institute of Meteorology
(Instituto Nacional de Meteorologia - INMET), and the National Electric System Operator
(Operador Nacional do Sistema Elétrico - ONS) databases.

* Plot - You will have some data plot options, such as the Gantt (temporal data availability) graphic, Flow Duration
Cuve, and plot for spatial station availability.

* PreProcessing - Presents a function to filter your data by dates, number of years with data, and missing percentage.
Further, there is a function to convert your data.

* SaveAs - Provides functions to save your data into a ".txt" file in the ASCII standard.

The modules will be updated with new functions/methods as soon as possible. Contributions are welcome!

### Import HydroBr
```python
import hydrobr
```
### Data from ANA
```python
help(hydrobr.get_data.ANA)
```

    Help on class ANA in module hydrobr.get_data:
    
    class ANA(builtins.object)
     |  It provides a connection with the Brazilian National Water Agency (Agência Nacional de Águas - ANA) database
     |  
     |  Static methods defined here:
     |  
     |  flow_data(list_station, only_consisted=False)
     |      Get the flow station data series from a list of stations code of the Brazilian National Water Agency
     |      (ANA) database.
     |      
     |      Parameters
     |      ----------
     |      list_station : list of strings
     |          A list of with the stations code as strings.
     |      only_consisted : boolean, default False
     |          If True, returns only the data classified as consistent by the provider.
     |      
     |      Returns
     |      -------
     |      data_stations : pandas DataFrame
     |          The data os each station as a column in a pandas DataFrame
     |  
     |  list_flow_stations(state='', city='', source='ANAF')
     |      Searches for flow/stage stations registered at the Brazilian National Agency of Water inventory.
     |      
     |      Parameters
     |      ----------
     |      state : string
     |          Brazilian state name where the stations are located (e.g., Rio de Janeiro)
     |      city : string
     |          Brazilian city name where the stations are located (e.g., Rio de Itaperuna)
     |      source: string, default 'ANAF'
     |          The source to look for the data. 'ANA' to get the list of stations from the Brazilian National Water
     |          Agency (ANA) database, or 'ANAF' to get the filtered list of stations that contain only the stations
     |          from ANA with registered data.
     |          More information about ANAF: https://doi.org/10.5281/zenodo.3755065
     |      
     |      Returns
     |      -------
     |      list_stations : pandas DataFrame
     |          The selected list of stations as a pandas DataFrame
     |  
     |  list_prec_stations(state='', city='', source='ANAF')
     |      Searches for precipitation stations registered at the Brazilian National Agency of Water (ANA)
     |      
     |      Parameters
     |      ----------
     |      state : string
     |          Brazilian state name where the stations are located (e.g., Rio de Janeiro)
     |      city : string
     |          Brazilian city name where the stations are located (e.g., Rio de Itaperuna)
     |      source: string, default 'ANA'
     |          The source to look for the data. 'ANA' to get the list of stations from the Brazilian National Water
     |          Agency (ANA) database, or 'ANAF' to get the filtered list of stations that contain only the stations
     |          from ANA with registered data.
     |          More information about ANAF: https://doi.org/10.5281/zenodo.3755065
     |      
     |      Returns
     |      -------
     |      list_stations : pandas DataFrame
     |          The selected list of stations as a pandas DataFrame
     |  
     |  prec_data(list_station, only_consisted=False)
     |      Get the precipitation station data series from a list of stations code.
     |      
     |      Parameters
     |      ----------
     |      list_station : list of strings
     |          A list of with the stations code as strings.
     |      only_consisted : boolean, default False
     |          If True, returns only the data classified as consistent by the provider.
     |      
     |      Returns
     |      -------
     |      data_stations : pandas DataFrame
     |          The data os each station as a column in a pandas DataFrame
     |  
     |  stage_data(list_station, only_consisted=False)
     |      Get the stage station data series from a list of stations code of the Brazilian National Water Agency
     |      (ANA) database.
     |      
     |      Parameters
     |      ----------
     |      list_station : list of strings
     |          A list of with the stations code as strings.
     |      only_consisted : boolean, default False
     |          If True, returns only the data classified as consistent by the provider.
     |      
     |      Returns
     |      -------
     |      data_stations : pandas DataFrame
     |          The data os each station as a column in a pandas DataFrame
     |  
     |  ----------------------------------------------------------------------    
### Data from INMET
```python
help(hydrobr.get_data.INMET)
```

    Help on class INMET in module hydrobr.get_data:
    
    class INMET(builtins.object)
     |  It provides a connection with the  Brazilian National Institute of Meteorology (Instituto Nacional de
     |  Meteorologia - INMET) database.
     |  
     |  Static methods defined here:
     |  
     |  daily_data(station_code, filter=True)
     |      Searches for all the data of a station registered at the Brazilian National Institute of Meteorology
     |      (Instituto Nacional de Meteorologia - INMET) database.
     |      
     |      Returns a pandas daily DataFrame with six variables for each day:
     |          - Prec - Precipitation (mm)
     |          - Tmean - Daily mean Temperature (ºC)
     |          - Tmax - Maximum Temperature (ºC)
     |          - Tmin - Minimum Temperature (ºC)
     |          - RH - Relative Humidity (%)
     |          - SD - Sunshine Duration (hours)
     |      
     |      Parameters
     |      ----------
     |      station_code : string
     |          Code of the station as a string
     |      filter: boolean, default True
     |          There is stations with repeated registered data. If 'True' the function returns a panda DataFrame
     |          with the first occurrence of the date. If 'False' return a pandas DataFrame with, in some cases,
     |          repeated datetime index.
     |      
     |      Returns
     |      -------
     |      data : pandas DataFrame
     |          The data of the selected station as a pandas DataFrame
     |  
     |  hourly_data(station_code)
     |      Searches for all the data of a station registered at the Brazilian National Institute of Meteorology
     |      (Instituto Nacional de Meteorologia - INMET) database.
     |      
     |      Only works for Automatic Stations.
     |      
     |      Returns a pandas hourly DataFrame with 17 variables for each day:
     |          - Tins - Instant Temperature (ºC)
     |          - Tmax - Maximum Temperature (ºC)
     |          - Tmin - Minimum Temperature (ºC)
     |          - RHins - Instant Relative Humidity (%)
     |          - RHmax - Maximum Relative Humidity (%)
     |          - RHmin - Minimum Relative Humidity (%)
     |          - DPins - Instant Dew Point Temperature (ºC)
     |          - DPmax - Maximum Dew Point Temperature (ºC)
     |          - DPmin - Minimum Dew Point Temperature (ºC)
     |          - Pins - Instant Pressure (hPa)
     |          - Pmax - Maximum Pressure (hPa)
     |          - Pmin - Minimum Pressure (hPa)
     |          - Wspeed - Wind Speed (m/s)
     |          - Wdir - Wind direction (º)
     |          - Wgust - Wind gust (m/s)
     |          - Rad - Global Radiation (kJ/m²)
     |          - Prec - Precipitation (mm)
     |      
     |      Parameters
     |      ----------
     |      station_code : string
     |          Code of the station as a string.
     |      
     |      Returns
     |      -------
     |      data : pandas DataFrame
     |          The data of the selected station as a pandas DataFrame.
     |  
     |  list_stations(station_type='both')
     |      Searches for precipitation stations registered at the Brazilian National Agency of Water (ANA) or the INMET
     |      inventory.
     |      
     |      Parameters
     |      ----------
     |      station_type : string, default 'both'
     |          The type of station. 'both' to get the list of automatic and manual gauge stations, 'automatic' to get only
     |          the automatic gauge stations, and 'conventional' to get only the conventional gauge stations.
     |      Returns
     |      -------
     |      list_stations : pandas DataFrame
     |          The selected list of stations as a pandas DataFrame
     |  
     |  ----------------------------------------------------------------------    
### Data from ONS
```python
help(hydrobr.get_data.ONS)
```

    Help on class ONS in module hydrobr.get_data:
    
    class ONS(builtins.object)
     |  Provide data from the National Electric System Operator (Operador Nacional do Sistema Elétrico - ONS) database.
     |  
     |  Static methods defined here:
     |  
     |  daily_data()
     |       Returns all the naturalized daily flow data of different reservoirs from the National Electric System
     |       Operator (Operador Nacional do Sistema Elétrico - ONS) database.
     |      
     |      Parameters
     |      ----------
     |      
     |      Returns
     |      -------
     |      data : pandas DataFrame
     |          All the naturalized daily flow data as a pandas DataFrame, where each column refers to a specific
     |          reservoir.  
     |  ----------------------------------------------------------------------    
### PreProcessing methods
```python
help(hydrobr.PreProcessing)
```

    Help on class PreProcessing in module hydrobr.preprocessing:
    
    class PreProcessing(builtins.object)
     |  Static methods defined here:
     |  
     |  daily_to_monthly(data, method='sum')
     |      Transform a time series of daily data into a time series monthly data.
     |      
     |      In the conversion process a month with a day missing data is considered as a missing month.
     |      
     |      Parameters
     |      ----------
     |      data : pandas DataFrame
     |          A Pandas daily DataFrame with DatetimeIndex where each column corresponds to a station.
     |      method: str, default sum
     |          The method used to convert. If 'sum', the monthly data will be the sum of the daily data. If 'mean', the
     |          monthly data will be the mean of the daily data.
     |      
     |      Returns
     |      -------
     |      monthly_data : pandas DataFrame
     |          The  monthly pandas DataFrame
     |  
     |  stations_filter(data, n_years=10, missing_percentage=5, start_date=False, end_date=False)
     |      A composed method to filter stations. 
     |      
     |      First, the method filters the stations data by the Start Date and the End Date, it its passed. After that,
     |      the is selected only the stations with at least a defined number of years between the first date and the
     |      last date of the station. At the end is selected the stations that contains at least one window of data with
     |      the number of years and a maximum missing data percentage. 
     |      
     |      Parameters
     |      ----------
     |      data : pandas DataFrame
     |          A Pandas daily DataFrame with DatetimeIndex where each column corresponds to a station.
     |      n_years: int, default 10
     |          The minimum number of years of registered data for the station between the first date and the end date.
     |      missing_percentage: int, default 5
     |           The maximum missing data percentage in a window with n_years.
     |           A number between 0 and 100
     |      start_date : int, float, str, default False
     |          The desired start date for the output DataFrame.
     |          See: pandas.to_datetime documentation if have doubts about the date format
     |      end_date: int, float, str, default False
     |          The desired end date for the output DataFrame.
     |          See: pandas.to_datetime documentation if have doubts about the date format
     |      
     |      Returns
     |      -------
     |      data : pandas DataFrame
     |          A pandas DataFrame with only the filtered stations
     |  
     |  ---------------------------------------------------------------------- 
### Plot methods
```python
help(hydrobr.Plot)
```

    Help on class Plot in module hydrobr.graphics:
    
    class Plot(builtins.object)
     |  Static methods defined here:
     |  
     |  fdc(data, y_log_scale=True)
     |      Make a flow duration curve plot.
     |      
     |      Parameters
     |      ----------
     |      data : pandas DataFrame
     |          A Pandas daily DataFrame with DatetimeIndex where each column corresponds to a station..
     |      y_log_scale : boolean, default True
     |          Defines if the the plotting y-axis will be in the logarithmic scale.
     |      
     |      Returns
     |      -------
     |      fig : plotly Figure
     |  
     |  gantt(data, monthly=True)
     |      Make a Gantt plot, which shows the temporal data availability for each station.
     |      
     |      Parameters
     |      ----------
     |      data : pandas DataFrame
     |          A Pandas daily DataFrame with DatetimeIndex where each column corresponds to a station..
     |      monthly : boolean, default True
     |          Defines if the availability count of the data will be monthly to obtain a more fluid graph.
     |      
     |      Returns
     |      -------
     |      fig : plotly Figure
     |  
     |  spatial_stations(list_stations, mapbox_access_token)
     |      Make a spatial plot of the stations.
     |      
     |      Parameters
     |      ----------
     |      list_stations : pandas DataFrame
     |          A Pandas DataFrame that must contain Latitude, Longitude, Name, and Code columns.
     |      mapbox_access_token : str
     |          Mapbox access toke, which can be obtained at https://account.mapbox.com/access-tokens/
     |      
     |      Returns
     |      -------
     |      fig : plotly Figure
     |  
     |  ----------------------------------------------------------------------
     |  Data descriptors defined here:
     |  
     |  __dict__
     |      dictionary for instance variables (if defined)
     |  
     |  __weakref__
     |      list of weak references to the object (if defined)
### SaveAs methods
```python
help(hydrobr.SaveAs)
```
    Help on class SaveAs in module hydrobr.save:
    
    class SaveAs(builtins.object)
     |  Static methods defined here:
     |  
     |  asc_daily_flow(data, path_save)
     |      Save each column of the flow stations DataFrame into a ".txt" file in the ASCII standard.
     |      
     |      Parameters
     |      ----------
     |      data : pandas DataFrame
     |          A Pandas daily DataFrame with DatetimeIndex where each column corresponds to a station.
     |      path_save: string
     |          The computer location where the ".txt" files will be saved.
     |      
     |      Returns
     |      -------
     |  
     |  asc_daily_prec(data, path_save)
     |      Save each column of the precipitation stations DataFrame into a ".txt" file in the ASCII standard.
     |      
     |      Parameters
     |      ----------
     |      data : pandas DataFrame
     |          A Pandas daily DataFrame with DatetimeIndex where each column corresponds to a station.
     |      path_save: string
     |          The computer location where the ".txt" files will be saved.
     |      
     |      Returns
     |      -------
     |  
     |  ----------------------------------------------------------------------


Modules
------------
Examples of usage are available at [HydroBr](https://wallissoncarvalho.github.io/hydrobr) 's page on my blog.


Dependencies
------------
- [NumPy](https://numpy.org/)
- [Pandas](https://pandas.pydata.org/)
- [Plotly](https://plotly.com/python/)
- [Requests](https://requests.readthedocs.io/en/master/)
- [tqdm](https://github.com/tqdm/tqdm)

License
------------
[BSD 3-Clause License](https://github.com/wallissoncarvalho/hydrobr/blob/master/LICENSE)

How to cite
------------
Wallisson Moreira de Carvalho. (2020, July 5). HydroBr: A Python package to work with Brazilian hydrometeorological
time series. (Version 0.1.0). Zenodo. http://doi.org/10.5281/zenodo.3930840
