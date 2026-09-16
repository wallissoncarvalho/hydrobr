"""HydroBr is an open-source package to work with Brazilian hydrometeorological time series."""

__version__ = '0.1.1'

from hydrobr import get_data
from hydrobr.analysis import HydroAnalysis
from hydrobr.ana import ANA, ANAClient
from hydrobr.cemaden import CEMADEN, CEMADENError
from hydrobr.climate import ClimateIndices, ClimateIndexError
from hydrobr.inmet import INMET, INMETError
from hydrobr.nasa_power import NASAPOWER, NASAPOWERError
from hydrobr.ons import ONS, ONSError
from hydrobr.sar import SAR, SARError
from hydrobr.graphics import Plot
from hydrobr.preprocessing import PreProcessing
from hydrobr.save import SaveAs
