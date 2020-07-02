from setuptools import setup, find_packages
from versioneer import find_version

with open("README.md", "r") as fh:
    long_description = fh.read()

with open('requirements.txt') as req:
    require = req.readlines()
install_requires = [r.strip() for r in require]

setup(
    name='hydrobr',
    description='HydroBr is an open-source package to work with Brazilian hydrometeorological time series.',
    version=find_version('hydrobr','__init__.py'),
    keywords='timeseries flow precipitation stages',
    author='Wallisson Moreira de Carvalho',
    url='https://github.com/wallissoncarvalho/hydrobr',
    author_email='cmwallisson@gmail.com',
    license='BSD 3-Clause License',
    packages=find_packages(),
    classifiers=['Development Status :: 1 - Planning',
                 'Environment :: Console',
                 'Operating System :: OS Independent',
                 'Intended Audience :: Science/Research',
                 "Programming Language :: Python :: 3"
                 "Programming Language :: Python :: 3.6",
                 "Programming Language :: Python :: 3.7",
                 "Programming Language :: Python :: 3.8",
                 "Topic :: Scientific/Engineering",
                 ],
    install_requires=install_requires
)
