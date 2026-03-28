"""Module will guide the forcing engine in defining parameters in all input forcing products.

These parameters include things such as file types, grid definitions (including
initializing ESMF grids and regrid objects), etc
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.core.consts import FORCINGINPUTMOD

if TYPE_CHECKING:
    from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.core.config import (
        ConfigOptions,
    )
    from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.core.geoMod import (
        GeoMeta,
    )
    from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.core.parallel import (
        MpiConfig,
    )
from nextgen_forcings_ewts import MODULE_NAME

LOG = logging.getLogger(MODULE_NAME)


class InputForcings:
    """Class defining parameters of a single input forcing product.

    This is a class that will define all the parameters
    of a single input forcing product.
    """

    def __init__(
        self,
        force_key: int,
        idx: int = None,
        config_options: ConfigOptions = None,
        geo_meta: GeoMeta = None,
        mpi_config: MpiConfig = None,
    ) -> None:
        """Initialize InputForcings with configuration options, geospatial metadata, and MPI configuration."""
        self.config_options = config_options
        self.geo_meta = geo_meta
        self.mpi_config = mpi_config
        self.regridComplete = False
        self.regridComplete = False
        self.rstFlag = 0
        self.skip = False
        self._keyValue = force_key
        self.idx = idx

        for attr in FORCINGINPUTMOD[self.__class__.__base__.__name__]:
            setattr(self, attr, None)

        self.find_neighbor_files_map = FORCINGINPUTMOD["FIND_NEIGHBOR_FILES_MAP"]
        self.regrid_map = FORCINGINPUTMOD["REGRID_MAP"]
        self.temporal_interpolate_inputs_map = FORCINGINPUTMOD["TEMPORAL_INTERPOLATE_INPUTS_MAP"]

        self.initialize_config_options()

        if self.force_count == 8 and 8 in self.input_map_output:
            # TODO: this assumes that LQFRAC (8) is always the last grib var
            self.grib_vars = self.grib_vars[:-1]

        # Obtain custom input cycle frequencies
        if self.keyValue == 10 or self.keyValue == 11:
            self.cycle_freq = self.config_options.customFcstFreq[self.custom_count]

    def initialize_config_options(self) -> None:
        """Initialize configuration options from the config_options attribute."""
        for key, val in list(vars(self.config_options).items()):
            if isinstance(val, list) and len(val) > 0:
                setattr(self, key, val[self.idx])
                LOG.info(key)

    @property
    def force_count(self) -> int:
        """Force count."""
        return 9 if self.config_options.include_lqfrac else 8

    @property
    def product_name(self) -> str:
        """Map the forcing key value to the product name."""
        return FORCINGINPUTMOD["PRODUCT_NAME"][self.keyValue]

    @property
    def keyValue(self) -> int:
        """Get the forcing key value."""
        if self._keyValue is None:
            raise RuntimeError("keyValue has not yet been set")
        return self._keyValue

    @keyValue.setter
    def keyValue(self, val: int) -> int:
        """Set the forcing key value."""
        if self._keyValue is not None:
            raise RuntimeError(f"keyValue has already been set (to {self._keyValue}).")
        self._keyValue = val

    @property
    def file_ext(self) -> str:
        """Map the forcing file type to the file extension."""
        ext = FORCINGINPUTMOD["FILE_EXT"].get(self.input_force_types)
        if ext is None:
            raise ValueError(f"Unexpected file_type: {self.input_force_types}")
        self._file_ext = ext

        return self._file_ext

    @file_ext.setter
    def file_ext(self, val: str) -> str:
        if val is None:
            raise TypeError(
                "Cannot set file_ext to None since that value indicates an uninitialized state"
            )
        self._file_ext = val

    @property
    def cycle_freq(self) -> int:
        """Map the forcing key value to the cycle frequency in minutes."""
        if self._cycle_freq is None:
            # First call to getter, initialize
            self._cycle_freq = FORCINGINPUTMOD["CYCLE_FREQ"][self.keyValue]
        return self._cycle_freq

    @cycle_freq.setter
    def cycle_freq(self, val: int) -> int:
        if val is None:
            raise TypeError(
                "Cannot set cycle_freq to None since that value indicates an uninitialized state"
            )
        self._cycle_freq = val

    @property
    def grib_vars(self) -> list[str] | None:
        """Map the forcing key value to the required GRIB variable names."""
        if self._grib_vars is None:
            # First call to getter, initialize
            self._grib_vars = FORCINGINPUTMOD["GRIB_VARS"][self.keyValue]
        return self._grib_vars

    @grib_vars.setter
    def grib_vars(self, val: list[str]) -> list[str] | None:
        if val is None:
            raise TypeError(
                "Cannot set grib_vars to None since that value indicates an uninitialized state"
            )
        self._grib_vars = val

    @property
    def grib_levels(self) -> str:
        """Map the forcing key value to the required GRIB variable levels."""
        return FORCINGINPUTMOD["GRIB_LEVELS"][self.keyValue]

    @property
    def netcdf_var_names(self) -> str:
        """Map the forcing key value to the required NetCDF variable names."""
        return FORCINGINPUTMOD["NET_CDF_VARS_NAMES"][self.keyValue]

    @property
    def grib_mes_idx(self) -> list[int] | None:
        """Map the forcing key value to the required GRIB message ids.

        arrays that store the message ids of required forcing variables for each forcing type
        TODO fill these arrays for forcing types other than GFS
        """
        return FORCINGINPUTMOD["GRIB_MES_IDX"][self.keyValue]

    @property
    def input_map_output(self) -> list[int] | None:
        """Map the forcing key value to the input to output variable mapping."""
        return FORCINGINPUTMOD["INPUT_MAP_OUTPUT"][self.keyValue]

    @property
    def forecast_horizons(self) -> list[int] | None:
        """Map the forcing key value to the forecast horizons list."""
        return FORCINGINPUTMOD["FORECAST_HORIZONS"][self.keyValue]

    def calc_neighbor_files(
        self, config_options: ConfigOptions, dcurrent, mpi_config: MpiConfig
    ) -> None:
        """Calculate the last/next expected input forcing file based on the current time step.

        Function that will calculate the last/next expected
        input forcing file based on the current time step that
        is being processed.
        :param config_options:
        :param dCurrent:
        :return:
        """
        # First calculate the current input cycle date this
        # WRF-Hydro output timestep corresponds to.

        LOG.debug(
            f"keyValue: {self.keyValue}, {self.find_neighbor_files_map[self.keyValue].__name__}"
        )
        self.find_neighbor_files_map[self.keyValue](
            self, config_options, dcurrent, mpi_config
        )

    def regrid_inputs(
        self,
        config_options: ConfigOptions,
        geo_meta: GeoMeta,
        mpi_config: MpiConfig,
    ) -> None:
        """Regrid input forcings to the final output grids for this timestep.

        Polymorphic function that will regrid input forcings to the
        final output grids for this particular timestep. For
        timesteps that require interpolation, two sets of input
        forcing grids will be regridded IF we have come across new
        files and the process flag has been reset.
        :param config_options:
        :return:
        """
        # Establish a mapping dictionary that will point the
        # code to the functions to that will regrid the data.
        self.regrid_map[self.keyValue](self, config_options, geo_meta, mpi_config)

    def temporal_interpolate_inputs(
        self, config_options: ConfigOptions, mpi_config: MpiConfig
    ) -> None:
        """Run temporal interpolation of the input forcing grids that have been regridded.

        Polymorphic function that will run temporal interpolation of
        the input forcing grids that have been regridded. This is
        especially important for forcings that have large output
        frequencies. This is also important for frequent WRF-Hydro
        input timesteps.
        :param config_options:
        :param mpi_config:
        :return:
        """
        self.temporal_interpolate_inputs_map[self.forceTemoralInterp](
            self, config_options, mpi_config
        )


class InputForcingsGridded(InputForcings):
    """Abstract class defining parameters of a single input forcing product.

    This is an abstract class that will define all the parameters
    of a single gridded input forcing product.
    """

    def __init__(
        self,
        force_key: int,
        idx: int = None,
        config_options: ConfigOptions = None,
        geo_meta: GeoMeta = None,
        mpi_config: MpiConfig = None,
    ) -> None:
        """Initialize InputForcingsGridded with configuration options, geospatial metadata, and MPI configuration."""
        super().__init__(force_key, idx, config_options, geo_meta, mpi_config)
        for attr in FORCINGINPUTMOD[self.__class__.__name__]:
            setattr(self, attr, None)

    @property
    @lru_cache
    def final_forcings(self):
        """Initialize the local final grid of values."""
        if self._final_forcings is not None:
            return self._final_forcings
        else:
            return np.full(
                [
                    self.force_count,
                    self.geo_meta.ny_local,
                    self.geo_meta.nx_local,
                ],
                np.nan,
            )

    @final_forcings.setter
    def final_forcings(self, value):
        "Setter for final_forcings."
        self._final_forcings = value

    @property
    @lru_cache
    def height(self):
        """Initialize the local height grid."""
        if self._height is not None:
            return self._height
        else:
            return np.full(
                [self.geo_meta.ny_local, self.geo_meta.nx_local],
                np.nan,
            )

    @height.setter
    def height(self, value):
        """Setter for height"""
        self._height = value

    @property
    @lru_cache
    def regridded_mask(self):
        """Initialize the local regridded mask grid."""
        if self._regridded_mask is not None:
            return self._regridded_mask
        else:
            return np.full(
                [self.geo_meta.ny_local, self.geo_meta.nx_local],
                np.nan,
            )

    @regridded_mask.setter
    def regridded_mask(self, value):
        """Setter for regridded_mask"""
        self._regridded_mask = value

    @property
    @lru_cache
    def regridded_mask_AORC(self):
        """Initialize the local regridded AORC mask grid."""
        if self._regridded_mask_AORC is not None:
            return self._regridded_mask_AORC
        else:
            return np.full(
                [self.geo_meta.ny_local, self.geo_meta.nx_local],
                np.nan,
            )

    @regridded_mask_AORC.setter
    def regridded_mask_AORC(self, value):
        """Setter for regridded_mask_AORC"""
        self._regridded_mask_AORC = value

    @property
    @lru_cache
    def t2dTmp(self):
        """Initialize temporary array for specific humidity downscaling."""
        if self._t2dTmp is not None:
            return self._t2dTmp
        elif self.q2dDownscaleOpt > 0:
            return np.full(
                [self.geo_meta.ny_local, self.geo_meta.nx_local],
                np.nan,
            )

    @t2dTmp.setter
    def t2dTmp(self, value):
        """Setter for t2dTmp"""
        self._t2dTmp = value

    @property
    @lru_cache
    def psfcTmp(self):
        """Initialize temporary array for specific humidity downscaling."""
        if self._psfcTmp is not None:
            return self._psfcTmp
        elif self.q2dDownscaleOpt > 0:
            return np.full(
                [self.geo_meta.ny_local, self.geo_meta.nx_local],
                np.nan,
            )

    @psfcTmp.setter
    def psfcTmp(self, value):
        """Setter for psfcTmp"""
        self._psfcTmp = value


class InputForcingsHydrofabric(InputForcings):
    """Abstract class defining parameters of a single input forcing product.

    This is an abstract class that will define all the parameters
    of a single hydrofabric input forcing product.
    """

    def __init__(
        self,
        force_key: int,
        idx: int = None,
        config_options: ConfigOptions = None,
        geo_meta: GeoMeta = None,
        mpi_config: MpiConfig = None,
    ) -> None:
        """Initialize InputForcingsHydrofabric with configuration options, geospatial metadata, and MPI configuration."""
        super().__init__(force_key, idx, config_options, geo_meta, mpi_config)
        for attr in FORCINGINPUTMOD[self.__class__.__name__]:
            setattr(self, attr, None)

    @property
    @lru_cache
    def final_forcings(self):
        """Initialize the local final grid of values."""
        if self._final_forcings is not None:
            return self._final_forcings
        else:
            return np.full([self.force_count, self.geo_meta.ny_local], np.nan)

    @final_forcings.setter
    def final_forcings(self, value):
        "Setter for final_forcings."
        self._final_forcings = value

    @property
    @lru_cache
    def height(self):
        """Initialize the local height grid."""
        if self._height is not None:
            return self._height
        else:
            return np.full([self.geo_meta.ny_local], np.nan)

    @height.setter
    def regridded_mask(self, value):
        """Setter for height."""
        self._height = value

    @property
    @lru_cache
    def regridded_mask(self):
        """Initialize the local regridded mask grid."""
        if self._regridded_mask is not None:
            return self._regridded_mask
        else:
            return np.full([self.geo_meta.ny_local], np.nan)

    @regridded_mask.setter
    def regridded_mask(self, value):
        """Setter for regridded_mask."""
        self._regridded_mask = value

    @property
    @lru_cache
    def regridded_mask_AORC(self):
        """Initialize the local regridded AORC mask grid."""
        if self._regridded_mask_AORC is not None:
            return self._regridded_mask_AORC
        else:
            return np.full([self.geo_meta.ny_local], np.nan)

    @regridded_mask_AORC.setter
    def regridded_mask_AORC(self, value):
        """Setter for regridded_mask_AORC."""
        self._regridded_mask_AORC = value

    @property
    @lru_cache
    def t2dTmp(self):
        """Initialize temporary array for specific humidity downscaling."""
        if self._t2dTmp is not None:
            return self._t2dTmp
        elif self.q2dDownscaleOpt > 0:
            return np.full([self.geo_meta.ny_local], np.nan)

    @t2dTmp.setter
    def t2dTmp(self, value):
        """Setter for t2dTmp"""
        self._t2dTmp = value

    @property
    @lru_cache
    def psfcTmp(self):
        """Initialize temporary array for specific humidity downscaling."""
        if self._psfcTmp is not None:
            return self._psfcTmp
        if self.q2dDownscaleOpt > 0:
            return np.full([self.geo_meta.ny_local], np.nan)

    @psfcTmp.setter
    def psfcTmp(self, value):
        """Setter for psfcTmp"""
        self._psfcTmp = value


class InputForcingsUnstructured(InputForcings):
    """Abstract class defining parameters of a single input forcing product.

    This is an abstract class that will define all the parameters
    of a single unstructured input forcing product.
    """

    def __init__(
        self,
        force_key: int,
        idx: int = None,
        config_options: ConfigOptions = None,
        geo_meta: GeoMeta = None,
        mpi_config: MpiConfig = None,
    ) -> None:
        """Initialize InputForcingsUnstructured with configuration options, geospatial metadata, and MPI configuration."""
        super().__init__(force_key, idx, config_options, geo_meta, mpi_config)
        for attr in FORCINGINPUTMOD[self.__class__.__name__]:
            setattr(self, attr, None)

    @property
    @lru_cache
    def t2dTmp(self):
        """Initialize temporary array for specific humidity downscaling."""
        if self._t2dTmp is not None:
            return self._t2dTmp
        elif self.q2dDownscaleOpt > 0:
            return np.full([self.geo_meta.ny_local], np.nan)

    @t2dTmp.setter
    def t2dTmp(self, value):
        """Setter for t2dTmp"""
        self._t2dTmp = value

    @property
    @lru_cache
    def psfcTmp(self):
        """Initialize temporary array for specific humidity downscaling."""
        if self._psfcTmp is not None:
            return self._psfcTmp
        elif self.q2dDownscaleOpt > 0:
            return np.full([self.geo_meta.ny_local], np.nan)

    @psfcTmp.setter
    def psfcTmp(self, value):
        """Setter for psfcTmp"""
        self._psfcTmp = value

    @property
    @lru_cache
    def t2dTmp_elem(self):
        """Initialize temporary array for specific humidity downscaling."""
        if self._t2dTmp_elem is not None:
            return self._t2dTmp_elem
        elif self.q2dDownscaleOpt > 0:
            return np.full([self.geo_meta.ny_local_elem], np.nan)

    @t2dTmp_elem.setter
    def t2dTmp_elem(self, value):
        """Setter for t2dTmp_elem"""
        self._t2dTmp_elem = value

    @property
    @lru_cache
    def psfcTmp_elem(self):
        """Initialize temporary array for specific humidity downscaling."""
        if self._psfcTmp_elem is not None:
            return self._psfcTmp_elem
        elif self.q2dDownscaleOpt > 0:
            return np.full([self.geo_meta.ny_local_elem], np.nan)

    @psfcTmp_elem.setter
    def psfcTmp_elem(self, value):
        """Setter for psfcTmp_elem"""
        self._psfcTmp_elem = value

    @property
    @lru_cache
    def final_forcings(self):
        """Initialize the local final grid of values."""
        if self._final_forcings is not None:
            return self._final_forcings
        else:
            return np.full([self.force_count, self.geo_meta.ny_local], np.nan)

    @final_forcings.setter
    def final_forcings(self, value):
        """Setter for final_forcings."""
        self._final_forcings = value

    @property
    @lru_cache
    def height(self):
        """Initialize the local height grid."""
        if self._height is not None:
            return self._height
        else:
            return np.full([self.geo_meta.ny_local], np.nan)

    @height.setter
    def height(self, value):
        """Setter for height."""
        self._height = value

    @property
    @lru_cache
    def regridded_mask(self):
        """Initialize the local regridded mask grid."""
        if self._regridded_mask is not None:
            return self._regridded_mask
        else:
            return np.full([self.geo_meta.ny_local], np.nan)

    @regridded_mask.setter
    def regridded_mask(self, value):
        """Setter for regridded_mask."""
        self._regridded_mask = value

    @property
    @lru_cache
    def regridded_mask_AORC(self):
        """Initialize the local regridded AORC mask grid."""
        if self._regridded_mask_AORC is not None:
            return self._regridded_mask_AORC
        else:
            return np.full([self.geo_meta.ny_local], np.nan)

    @regridded_mask_AORC.setter
    def regridded_mask_AORC(self, value):
        """Setter for regridded_mask_AORC."""
        self._regridded_mask_AORC = value

    @property
    @lru_cache
    def final_forcings_elem(self):
        """Initialize the local final grid of values on elements."""
        if self._final_forcings_elem is not None:
            return self._final_forcings_elem
        else:
            return np.full(
                [self.force_count, self.geo_meta.ny_local_elem],
                np.nan,
            )

    @final_forcings_elem.setter
    def final_forcings_elem(self, value):
        """Setter for final_forcings_elem."""
        self._final_forcings_elem = value

    @property
    @lru_cache
    def height_elem(self):
        """Initialize the local height grid on elements."""
        if self._height_elem is not None:
            return self._height_elem
        else:
            return np.full([self.geo_meta.ny_local_elem], np.nan)

    @height_elem.setter
    def height_elem(self, value):
        """Setter for height_elem."""
        self._height_elem = value

    @property
    @lru_cache
    def regridded_mask_elem(self):
        """Initialize the local regridded mask grid on elements."""
        if self._regridded_mask_elem is not None:
            return self._regridded_mask_elem
        else:
            return np.full([self.geo_meta.ny_local_elem], np.nan)

    @regridded_mask_elem.setter
    def regridded_mask_elem(self, value):
        """Setter for regridded_mask_elem."""
        self._regridded_mask_elem = value

    @property
    @lru_cache
    def regridded_mask_elem_AORC(self):
        """Initialize the local regridded AORC mask grid on elements."""
        if self._regridded_mask_elem_AORC is not None:
            return self._regridded_mask_elem_AORC
        else:
            return np.full([self.geo_meta.ny_local_elem], np.nan)

    @regridded_mask_elem_AORC.setter
    def regridded_mask_elem_AORC(self, value):
        """Setter for regridded_mask_elem_AORC."""
        self._regridded_mask_elem_AORC = value

INPUTFORCINGS = {
    "gridded": InputForcingsGridded,
    "unstructured": InputForcingsUnstructured,
    "hydrofabric": InputForcingsHydrofabric,
}


def init_dict(
    config_options: ConfigOptions,
    geo_meta: GeoMeta,
    mpi_config: MpiConfig,
) -> dict:
    """Initialize the input forcing dictionary.

    Initial function to create an input forcing dictionary, which
    will contain an abstract class for each input forcing product.
    This gets called one time by the parent calling program.
    :param config_options:
    :return: input_dict - A dictionary defining our inputs.
    """
    input_dict = {}
    if config_options.precip_only_flag:
        return input_dict

    # Loop through and initialize the empty class for each product.
    custom_count = 0
    for idx in range(0, config_options.number_inputs):
        force_key = config_options.input_forcings[idx]

        if config_options.grid_type not in INPUTFORCINGS:
            raise TypeError(
                f"Invalid grid type specified: {config_options.grid_type}. Valid options are: {list(INPUTFORCINGS.keys())}"
            )

        input_dict[force_key] = INPUTFORCINGS[config_options.grid_type](
            force_key, idx, config_options, geo_meta, mpi_config
        )
        # input_dict[force_key].keyValue = force_key

        # Obtain custom input cycle frequencies
        if force_key == 10 or force_key == 11:
            custom_count = custom_count + 1

    return input_dict
