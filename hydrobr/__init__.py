"""HydroBr - Open-source toolkit for acquiring, processing, and visualising Brazilian hydrometeorological datasets."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from . import  data_access, processing, spatial, view, save

try:
    __version__ = version("hydrobr")
except PackageNotFoundError:  # pragma: no cover - fallback during local dev
    __version__ = "0.0.0"

# noinspection PyInterpreter
__all__ = [
    "__version__",
    "data_access",
    "processing",
    "spatial",
    "view",
    "save",
]