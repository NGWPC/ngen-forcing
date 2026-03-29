"""High-level module file that will handle supplemental analysis/observed precipitation grids that will replace precipitation in the final output files."""

from __future__ import annotations

import logging
from functools import cached_property
from typing import TYPE_CHECKING, Any

import numpy as np
from nextgen_forcings_ewts import MODULE_NAME

from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.core.consts import (
    SUPPPRECIPMOD,
)

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

LOG = logging.getLogger(MODULE_NAME)


class SupplementalPrecip:
    """Supplemental precipitation abstract class.

    This is an abstract class that will define all the parameters
    of a single supplemental precipitation product.
    """

    def __init__(self, idx: int, config_options: ConfigOptions, geo_meta: GeoMeta):
        """Initializie all attributes and objects to None."""
        self.regridComplete = False
        self.has_cache = False
        self._keyValue = config_options.supp_precip_forcings[idx]
        self.idx = idx
        self.config_options = config_options
        self.geo_mdeta = geo_meta
        for attr in SUPPPRECIPMOD[self.__class__.__base__.__name__]:
            setattr(self, attr, None)

        self.initialize_config_options()

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

    def initialize_config_options(self) -> None:
        """Initialize configuration options from the config_options attribute."""
        for key, val in list(vars(self.config_options).items()):
            if (
                isinstance(val, list)
                and len(val) > 0
                and key not in ["rqiMethod", "rqiThresh"]
            ):
                setattr(self, key, val[self.idx])
                LOG.info(key)

    @property
    def rqiMethod(self) -> int | float:
        if self.config_options.rqiMethod is not None:
            return self.config_options.rqiMethod[self.idx]
        else:
            return 0

    @property
    def rqiThresh(self) -> int | float:
        if self.config_options.rqiMethod is not None:
            return self.config_options.rqiThresh[self.idx]
        else:
            return 1.0

    @property
    def product_name(self) -> str:
        return SUPPPRECIPMOD["PRODUCT_NAMES"][self.keyValue]

        ## DEFINED IN CONFIG
        # product_types = {
        #     1: "GRIB2",
        #     2: "GRIB2",
        #     3: "GRIB2",
        #     4: "GRIB2",
        #     5: "GRIB2"
        # }
        # self.file_type = product_types[self.keyValue]

    @property
    def file_ext(self) -> str:
        return SUPPPRECIPMOD["FILE_EXT"][self.file_type]

    @property
    def grib_vars(self) -> None:
        return SUPPPRECIPMOD["GRIB_VARS"][self.keyValue]

    @property
    def grib_levels(self) -> list[str]:
        return SUPPPRECIPMOD["GRIB_LEVELS"][self.keyValue]

    @property
    def netcdf_var_names(self) -> list[str]:
        return SUPPPRECIPMOD["NET_CDF_VARS_NAMES"][self.keyValue]

    @property
    def rqi_netcdf_var_names(self) -> list[str] | None:
        return SUPPPRECIPMOD["RQI_NETCDF_VAR_NAMES"][self.keyValue]

    @property
    def output_var_idx(self) -> int:
        return SUPPPRECIPMOD["OUTPUT_VAR_IDX"][self.keyValue]

    @property
    def find_neighbor_files(self) -> dict:
        return SUPPPRECIPMOD["FIND_NEIGHBOR_FILES_MAP"]

    def calc_neighbor_files(
        self, config_options: ConfigOptions, dcurrent, mpi_config: MpiConfig
    ) -> None:
        """Calculate neighbor supplemental precipitation files.

        Function that will calculate the last/next expected
        supplemental precipitation file based on the current time step that
        is being processed.
        :param ConfigOptions:
        :param dCurrent:
        :return:
        """
        self.find_neighbor_files_map[self.keyValue](
            self, config_options, dcurrent, mpi_config
        )

    @property
    def regrid_map(self) -> dict:
        return SUPPPRECIPMOD["REGRID_MAP"]

    def regrid_inputs(
        self, config_options: ConfigOptions, geo_meta: GeoMeta, mpi_config: MpiConfig
    ) -> None:
        """Polymorphic function that will regrid input forcings to the supplemental precipitation grids for this particular timestep.

        Polymorphic function that will regrid input forcings to the
        supplemental precipitation grids for this particular timestep. For
        timesteps that require interpolation, two sets of input
        forcing grids will be regridded IF we have come across new
        files and the process flag has been reset.
        :param ConfigOptions:
        :return:
        """
        # Establish a mapping dictionary that will point the
        # code to the functions to that will regrid the data.
        self.regrid_map[self.keyValue](self, config_options, geo_meta, mpi_config)

    @property
    def temporal_interpolate_inputs_map(self) -> dict:
        return SUPPPRECIPMOD["TEMPORAL_INTERPOLATE_INPUTS_MAP"]

    def temporal_interpolate_inputs(
        self, config_options: ConfigOptions, mpi_config: MpiConfig
    ):
        """Polymorphic function that will run temporal interpolation of the supplemental precipitation grids that have been regridded.

        Polymorphic function that will run temporal interpolation of
        the supplemental precipitation grids that have been regridded. This is
        especially important for supplemental precips that have large output
        frequencies. This is also important for frequent WRF-Hydro
        input timesteps.
        :param ConfigOptions:
        :param MpiConfig:
        :return:
        """
        self.temporal_interpolate_inputs_map[self.keyValue][self.timeInterpOpt](
            self, config_options, mpi_config
        )


class SupplementalPrecipGridded(SupplementalPrecip):
    def __init__(
        self,
        idx: int = None,
        config_options: ConfigOptions = None,
        geo_meta: GeoMeta = None,
    ) -> None:
        """Initialize InputForcingsUnstructured with configuration options, geospatial metadata, and MPI configuration."""
        super().__init__(idx, config_options, geo_meta)
        for attr in SUPPPRECIPMOD[self.__class__.__name__]:
            setattr(self, attr, None)

    @cached_property
    def final_supp_precip(self) -> np.ndarray | Any:
        if self._final_supp_precip is not None:
            return self._final_supp_precip
        else:
            return np.full(
                [self.geo_meta.ny_local, self.geo_meta.nx_local],
                np.nan,
                dtype=np.float64,
            )

    @final_supp_precip.setter
    def final_supp_precip(self, value: Any) -> Any:
        """Setter for final_supp_precip."""
        self._final_supp_precip = value

    @cached_property
    def regridded_mask(self) -> np.ndarray | Any:
        if self._regridded_mask is not None:
            return self._regridded_mask
        else:
            return np.full(
                [self.geo_meta.ny_local, self.geo_meta.nx_local], np.nan, np.float32
            )

    @regridded_mask.setter
    def regridded_mask(self, value: Any) -> Any:
        """Setter for regridded_mask."""
        self._regridded_mask = value


class SupplementalPrecipHydrofabric(SupplementalPrecip):
    def __init__(
        self,
        idx: int = None,
        config_options: ConfigOptions = None,
        geo_meta: GeoMeta = None,
    ) -> None:
        """Initialize InputForcingsUnstructured with configuration options, geospatial metadata, and MPI configuration."""
        super().__init__(idx, config_options, geo_meta)
        for attr in SUPPPRECIPMOD[self.__class__.__name__]:
            setattr(self, attr, None)

    @cached_property
    def final_supp_precip(self) -> np.ndarray | Any:
        if self._final_supp_precip is not None:
            return self._final_supp_precip
        else:
            return np.full([self.geo_meta.ny_local], np.nan, dtype=np.float64)

    @final_supp_precip.setter
    def final_supp_precip(self, value: Any) -> Any:
        """Setter for final_supp_precip."""
        self._final_supp_precip = value

    @cached_property
    def regridded_mask(self) -> np.ndarray | Any:
        if self._regridded_mask is not None:
            return self._regridded_mask
        else:
            return np.full([self.geo_meta.ny_local], np.nan, dtype=np.float32)

    @regridded_mask.setter
    def regridded_mask(self, value: Any) -> Any:
        """Setter for regridded_mask."""
        self._regridded_mask = value


class SupplementalPrecipUnstructured(SupplementalPrecip):
    def __init__(
        self,
        idx: int = None,
        config_options: ConfigOptions = None,
        geo_meta: GeoMeta = None,
    ) -> None:
        """Initialize InputForcingsUnstructured with configuration options, geospatial metadata, and MPI configuration."""
        super().__init__(idx, config_options, geo_meta)
        for attr in SUPPPRECIPMOD[self.__class__.__name__]:
            setattr(self, attr, None)

    @cached_property
    def final_supp_precip(self) -> np.ndarray | Any:
        if self._final_supp_precip is not None:
            return self._final_supp_precip
        else:
            return np.full([self.geo_meta.ny_local], np.nan, dtype=np.float64)

    @final_supp_precip.setter
    def final_supp_precip(self, value: Any) -> Any:
        """Setter for final_supp_precip."""
        self._final_supp_precip = value

    @cached_property
    def regridded_mask(self) -> np.ndarray | Any:
        if self._regridded_mask is not None:
            return self._regridded_mask
        else:
            return np.full([self.geo_meta.ny_local], np.nan, dtype=np.float32)

    @regridded_mask.setter
    def regridded_mask(self, value: Any) -> Any:
        """Setter for regridded_mask."""
        self._regridded_mask = value

    @cached_property
    def final_supp_precip_elem(self) -> np.ndarray | Any:
        if self._final_supp_precip_elem is not None:
            return self._final_supp_precip_elem
        else:
            return np.full([self.geo_meta.ny_local_elem], np.nan, dtype=np.float64)

    @final_supp_precip_elem.setter
    def final_supp_precip_elem(self, value: Any) -> Any:
        """Setter for final_supp_precip_elem."""
        self._final_supp_precip_elem = value

    @cached_property
    def regridded_mask_elem(self) -> np.ndarray | Any:
        if self._regridded_mask_elem is not None:
            return self._regridded_mask_elem
        else:
            return np.full([self.geo_meta.ny_local_elem], np.nan, dtype=np.float32)

    @regridded_mask_elem.setter
    def regridded_mask_elem(self, value: Any) -> Any:
        """Setter for regridded_mask_elem."""
        self._regridded_mask_elem = value


SUPPPRECIP = {
    "gridded": SupplementalPrecipGridded,
    "unstructured": SupplementalPrecipUnstructured,
    "hydrofabric": SupplementalPrecipHydrofabric,
}


def init_dict(config_options: ConfigOptions, geo_meta: GeoMeta) -> dict:
    """Initialize the supplemental precipitation input dictionary.

    Initial function to create an supplemental dictionary, which
    will contain an abstract class for each supplemental precip product.
    This gets called one time by the parent calling program.
    :param ConfigOptions:
    :return: input_dict - A dictionary defining our inputs.
    """
    input_dict = {}
    for idx in range(0, config_options.number_supp_pcp):
        supp_pcp_key = config_options.supp_precip_forcings[idx]
        input_dict[supp_pcp_key] = SUPPPRECIP[config_options.grid_type](
            idx, config_options, geo_meta
        )
    return input_dict
