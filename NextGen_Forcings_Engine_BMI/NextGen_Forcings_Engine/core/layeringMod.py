"""Layering module for implementing various layering schemes.

Key Concepts
------------
force_idx : int
    Index into the forcing product array.  See function ``layer_final_forcings`` for additional information.

attr_suffix : str
    Suffix appended to attribute names to access different array variants.
    Empty string for standard arrays; '_elem' for element-based arrays in unstructured grids.

Future functionality may include blending, etc.
"""

from abc import ABC, abstractmethod
from typing import Any

import numpy as np

from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.core.config import (
    ConfigOptions,
)
from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.core.forcingInputMod import (
    InputForcings,
)
from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.core.ioMod import (
    OutputObj,
)
from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.core.suppPrecipMod import (
    SupplementalPrecip,
)


class _LayeringMod(ABC):
    """Abstract Class for layering of forcing grids"""

    def __init__(
        self,
        output_obj,
        input_forcings: InputForcings,
        config_options: ConfigOptions,
    ):
        self.output_obj = output_obj
        self.input_forcings = input_forcings
        self.config_options = config_options

    @abstractmethod
    def get_slice(self, obj: Any, force_idx: int) -> Any:
        """Abstract method: Using bracket syntax, return a slice of an object based on its forcing index."""
        raise NotImplementedError

    @abstractmethod
    def set_slice(self, obj: Any, force_idx: int, value: Any) -> None:
        """Abstract method: Using bracket syntax, set the value of a slice of an object based on its forcing index."""
        raise NotImplementedError

    @abstractmethod
    def apply_layering(self, force_idx: int) -> None:
        """Abstract method: Apply the layering logic (this is the primary function of this class)."""
        raise NotImplementedError

    def layerIn(self, force_idx: int, attr_suffix: str = "") -> Any:
        """Return an input dataset used for layering."""
        return self.get_slice(
            getattr(self.input_forcings, f"final_forcings{attr_suffix}"), force_idx
        )

    def indSet(self, force_idx: int, attr_suffix: str = "") -> Any:
        """Return the indices of the input dataset that are not equal to the global no-data value (a non-no-data mask)."""
        return np.where(
            self.layerIn(force_idx, attr_suffix) != self.config_options.globalNdv
        )

    def update_output_local(self, force_idx: int, attr_suffix: str = "") -> None:
        """Apply layering logic to update the output grid with input forcing data.

        This is the primary business logic of the layering module. It retrieves input forcing data,
        applies validity checks (using globalNdv as the no-data value), and updates the output grid
        with valid data. Special handling is provided for ERA5 data.

        Parameters
        ----------
        force_idx : int
            Index of the forcing product to layer.
        attr_suffix : str, optional
            Suffix to append to attribute names (e.g., '_elem' for element arrays).
            Default is empty string, which accesses standard arrays.
            This is leveraged by the Unstructured discretization type.

        Notes
        -----
        - Uses `get_slice()` and `set_slice()` to support different grid discretizations (gridded, unstructured, hydrofabric).
        - For ERA5 with forcing keys [12, 21], uses `regridded_mask_AORC` (or `regridded_mask_elem_AORC` for elem variants) to determine valid cells.
        - For other cases, uses global no-data value (`globalNdv`) to identify valid data.
        """
        output_tmp = self.get_slice(
            getattr(self.output_obj, f"output_local{attr_suffix}"), force_idx
        )
        layerIn = self.layerIn(force_idx, attr_suffix)

        if (
            self.input_forcings.product_name == "ERA5"
            and [12, 21] in self.config_options.input_forcings
        ):
            mask = getattr(self.input_forcings, f"regridded_mask{attr_suffix}_AORC")
            output_tmp[np.where(mask == 0)] = layerIn[np.where(mask == 0)]
        else:
            indSet = self.indSet(force_idx, attr_suffix)
            output_tmp[indSet] = layerIn[indSet]

        self.set_slice(
            getattr(self.output_obj, f"output_local{attr_suffix}"),
            force_idx,
            output_tmp,
        )


class _LayeringMod_Gridded(_LayeringMod):
    """Implementation of abstract class _LayeringMod for Gridded discretization"""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def get_slice(self, obj: Any, force_idx: int) -> Any:
        return obj[force_idx, :, :]

    def set_slice(self, obj: Any, force_idx: int, value: Any) -> None:
        obj[force_idx, :, :] = value

    def apply_layering(self, force_idx: int) -> None:
        self.update_output_local(force_idx)


class _LayeringMod_Unstructured(_LayeringMod):
    """Implementation of abstract class _LayeringMod for Unstructured discretization"""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def get_slice(self, obj: Any, force_idx: int) -> Any:
        return obj[force_idx, :]

    def set_slice(self, obj: Any, force_idx: int, value: Any) -> None:
        obj[force_idx, :] = value

    def apply_layering(self, force_idx: int) -> None:
        self.update_output_local(force_idx)
        self.update_output_local(force_idx, "_elem")


class _LayeringMod_Hydrofabric(_LayeringMod):
    """Implementation of abstract class _LayeringMod for Hydrofabric discretization"""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def get_slice(self, obj: Any, force_idx: int) -> Any:
        return obj[force_idx, :]

    def set_slice(self, obj: Any, force_idx: int, value: Any) -> None:
        obj[force_idx, :] = value

    def apply_layering(self, force_idx: int) -> None:
        self.update_output_local(force_idx)


def layer_final_forcings(
    output_obj: OutputObj, input_forcings: InputForcings, config_options: ConfigOptions
):
    """Layer input forcings onto the output grid.

    Function to perform basic layering of input forcings as they are processed. The logic
    works as following:
    1.) As the parent calling program loops through the forcings for each layer
        for this timestep, forcings are placed onto the output grid by shear brute
        replacement. However, this only occurs where valid data exists.
        Supplemental precipitation will be layered in separately.
    :param output_obj:
    :param input_forcings:
    :param config_options:
    :return:
    """
    # Loop through the 8(or 9) forcing products to layer in:
    # 0.) U-Wind (m/s)
    # 1.) V-Wind (m/s)
    # 2.) Surface incoming longwave radiation flux (W/m^2)
    # 3.) Precipitation rate (mm/s)
    # 4.) 2-meter temperature (K)
    # 5.) 2-meter specific humidity (kg/kg)
    # 6.) Surface pressure (Pa)
    # 7.) Surface incoming shortwave radiation flux (W/m^2)
    # 8.) Liquid fraction of precipitation ([0..1])

    if config_options.grid_type == "gridded":
        factory = _LayeringMod_Gridded
    elif config_options.grid_type == "unstructured":
        factory = _LayeringMod_Unstructured
    elif config_options.grid_type == "hydrofabric":
        factory = _LayeringMod_Hydrofabric
    else:
        raise ValueError(
            f"Unexpected discretization type / grid type: {config_options.grid_type}"
        )
    layering_mod = factory(output_obj, input_forcings, config_options)
    force_count = 9 if config_options.include_lqfrac else 8
    for force_idx in range(0, force_count):
        if force_idx in input_forcings.input_map_output:
            layering_mod.apply_layering(force_idx)


class _LayeringModSupplemental(ABC):
    def __init__(
        self,
        output_obj: OutputObj,
        supplemental_precip: SupplementalPrecip,
        config_options: ConfigOptions,
    ):
        self.output_obj = output_obj
        self.supplemental_precip = supplemental_precip
        self.config_options = config_options

    @abstractmethod
    def get_slice(self, obj: Any) -> Any:
        """Abstract method: Using bracket syntax, return a slice of an object based on its forcing index."""
        raise NotImplementedError

    @abstractmethod
    def set_slice(self, obj: Any, value: Any) -> None:
        """Abstract method: Using bracket syntax, set the value of a slice of an object based on its forcing index."""
        raise NotImplementedError

    @abstractmethod
    def apply_layering(self) -> None:
        """Abstract method: Apply the layering logic (this is the primary function of this class)."""
        raise NotImplementedError

    def indSet(self, attr_suffix: str = ""):
        return np.where(
            getattr(self.supplemental_precip, f"final_supp_precip{attr_suffix}")
            != self.config_options.globalNdv
        )

    def layerIn(self, attr_suffix: str = ""):
        return getattr(self.supplemental_precip, f"final_supp_precip{attr_suffix}")

    def layerOut(self, attr_suffix: str = ""):
        return self.get_slice(
            getattr(self.output_obj, f"output_local{attr_suffix}"),
            self.supplemental_precip.output_var_idx,
        )

    def update_output_local(self, attr_suffix: str = "") -> None:
        indSet = self.indSet(attr_suffix)
        layerIn = self.layerIn(attr_suffix)
        layerOut = self.layerOut(attr_suffix)
        # NOTE original TODO comment below was for "gridded" discretization. Unknown intent:
        # TODO: review test layering for ExtAnA calculation to replace FE QPE with MPE RAINRATE
        # If this isn't sufficient, replace QPE with MPE here:
        # if supplemental_precip.keyValue == 11:
        #    config_options.statusMsg = "Performing ExtAnA calculation"
        #    err_handler.log_msg(config_options, MpiConfig)
        if len(indSet[0]) != 0:
            layerOut[indSet] = layerIn[indSet]
        # NOTE original TODO comment below was for all discretizations ("gridded", "unstructured", and "hydrofabric"). Unknown intent.
        # TODO: test that even does anything...?s
        self.set_slice(
            getattr(self.output_obj, f"output_local{attr_suffix}"),
            self.supplemental_precip.output_var_idx,
            layerOut,
        )


class _LayeringModSupplemental_Gridded(_LayeringModSupplemental):
    """Implementation of abstract class _LayeringModSupplemental for Gridded discretization.
    Slicing is 3-dimensional.
    Primary business logic executes once (no extra "_elem" call).
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def get_slice(self, obj: Any, first_dim_idx: int) -> Any:
        return obj[first_dim_idx, :, :]

    def set_slice(self, obj: Any, first_dim_idx: int, value: Any) -> None:
        obj[first_dim_idx, :, :] = value

    def apply_layering(self) -> None:
        self.update_output_local()


class _LayeringModSupplemental_Unstructured(_LayeringModSupplemental):
    """Implementation of abstract class _LayeringModSupplemental for Unstructured discretization.
    Slicing is 2-dimensional.
    Primary business logic executes twice (with extra "_elem" call).
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def get_slice(self, obj: Any, first_dim_idx: int) -> Any:
        return obj[first_dim_idx, :]

    def set_slice(self, obj: Any, first_dim_idx: int, value: Any) -> None:
        obj[first_dim_idx, :] = value

    def apply_layering(self) -> None:
        self.update_output_local()
        self.update_output_local("_elem")


class _LayeringModSupplemental_Hydrofabric(_LayeringModSupplemental):
    """Implementation of abstract class _LayeringModSupplemental for Unstructured discretization.
    Slicing is 2-dimensional.
    Primary business logic executes once (no extra "_elem" call).
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def get_slice(self, obj: Any, first_dim_idx: int) -> Any:
        return obj[first_dim_idx, :]

    def set_slice(self, obj: Any, first_dim_idx: int, value: Any) -> None:
        obj[first_dim_idx, :] = value

    def apply_layering(self) -> None:
        self.update_output_local()


def layer_supplemental_forcing(
    output_obj: OutputObj,
    supplemental_precip: SupplementalPrecip,
    config_options: ConfigOptions,
):
    """Layer in supplemental precipitation where valid values exist.

    Function to layer in supplemental precipitation where we have valid values. Any pixel
    cells that contain missing values will not be layered in, and background input forcings
    will be used instead.
    :param output_obj:
    :param supplemental_precip:
    :param config_options:
    :return:
    """
    if config_options.grid_type == "gridded":
        factory = _LayeringModSupplemental_Gridded
    elif config_options.grid_type == "unstructured":
        factory = _LayeringModSupplemental_Unstructured
    elif config_options.grid_type == "hydrofabric":
        factory = _LayeringModSupplemental_Hydrofabric
    else:
        raise ValueError(
            f"Unexpected discretization type / grid type: {config_options.grid_type}"
        )
    layering_mod_supp = factory(output_obj, supplemental_precip, config_options)
    layering_mod_supp.apply_layering()
