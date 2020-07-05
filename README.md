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

Modules
------------
Currently, the *HydroBr* package has four modules:

* get_data - Functions that provide a connection with the Brazilian National Water Agency
(Agência Nacional de Águas - ANA), the Brazilian National Institute of Meteorology
(Instituto Nacional de Meteorologia - INMET), and the National Electric System Operator
(Operador Nacional do Sistema Elétrico - ONS) databases.

* Plot - You will have some data plot options, such as the Gantt (temporal data availability) graphic, Flow Duration
Cuve, and plot for spatial station availability.

* Preprocessing - Presents a function to filter your data by dates, number of years with data, and missing percentage.
Further, there is a function to convert your data.

* SaveAs - Provides functions to save your data into a ".txt" file in the ASCII standard.

The modules will be updated with new functions/methods as soon as possible. Contributions are welcome!

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
