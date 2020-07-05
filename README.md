# HydroBr [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.3930349.svg)](https://doi.org/10.5281/zenodo.3930349) [![PythonVersion](https://img.shields.io/badge/python-3.6%20%7C%203.7%20%7C%203.8-blue)](https://img.shields.io/badge/python-3.6%20%7C%203.7%20%7C%203.8-blue)

HydroBr is an open-source package to work with Brazilian hydrometeorological time series.

Introduction
------------
HydroBr is an open-source package for work with Brazilian hydrometeorological time series in Python. This package
provides a connection with the Brazilian  National Water Agency (ANA), the Brazilian National Institute of Meteorology
(Instituto Nacional de Meteorologia - INMET), and the National Electric System Operator (Operador Nacional do Sistema
Elétrico - ONS) databases in order to help users to select, download, preprocess, and plot hydrometeorological  data. 

Installation
------------
The released version of HydroBr is 0.1.  To install the released
version, use ``pip install hydrobr``.

You may install the latest development version by cloning the
`GitHub` repository and using the setup script::

    git clone https://github.com/wallissoncarvalho/hydrobr.git
    cd hydrobr
    python setup.py install

## Dependencies
- [NumPy](https://numpy.org/)
- [Pandas](https://pandas.pydata.org/)
- [Plotly](https://plotly.com/python/)
- [Requests](https://requests.readthedocs.io/en/master/)
- [tqdm](https://github.com/tqdm/tqdm)

## License
[BSD 3-Clause License](https://github.com/wallissoncarvalho/hydrobr/blob/master/LICENSE)

## How to cite
Wallisson Moreira de Carvalho. (2020, July 4). HydroBr: A Python package to work with Brazilian hydrometeorological
time series. (Version 0.0.2). Zenodo. http://doi.org/10.5281/zenodo.3930349