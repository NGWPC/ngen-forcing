from __future__ import annotations

from dataclasses import dataclass
import typing

if typing.TYPE_CHECKING:
    from test_utils import ClassAttrFetcher


@dataclass
class TestConfig_Base:
    """Configuration base class for tests"""

    config_file: str
    keys_to_check: tuple[str]
    keys_to_exclude: tuple[str]
    grid_type: str


@dataclass
class TestConfig_GeoMod(TestConfig_Base):
    """Configuration class for GeoMod Tests"""


@dataclass
class TestConfig_InputForcing(TestConfig_Base):
    """Configuration class for InputForcing Tests"""

    force_key: int


@dataclass
class TestConfig_Regrid(TestConfig_Base):
    """Configuration class for Regrid Tests"""

    force_key: int
    regrid_func: typing.Callable
    extra_attrs: list[ClassAttrFetcher]
    regrid_arrays_to_trim_extra_elements: tuple[str]
