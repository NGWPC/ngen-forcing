"""Utilities for ngen-forcing tests."""

import json
import logging
import os
import typing

import pytest

from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.bmi_model import (
    NWMv3_Forcing_Engine_BMI_model,
)
from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.core.config import (
    ConfigOptions,
)
from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.core.forcingInputMod import (
    InputForcings,
)
from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.core.geoMod import (
    GeoMetaWrfHydro,
)
from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.core.parallel import MpiConfig
from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.general_utils import (
    ExpectVsActualError,
    serialize_to_json,
    assert_equal_with_tol,
)

OS_VAR__CREATE_TEST_EXPECT_DATA = "FORCING_PYTEST_WRITE_TEST_EXPECTED_DATA"


class BMIForcingFixture:
    """Minimal class of classes for running BMI forcing.
    For example usage, see: tests/esmf_regrid/test_esmf_regrid.test_regrid_aorc_aws.
    """

    def __init__(self, bmi_model: NWMv3_Forcing_Engine_BMI_model):
        self.bmi_model: NWMv3_Forcing_Engine_BMI_model = bmi_model
        self.mpi_config: MpiConfig = bmi_model._mpi_meta
        self.config_options: ConfigOptions = bmi_model._job_meta
        self.wrf_hydro_geo_meta: GeoMetaWrfHydro = bmi_model._wrf_hydro_geo_meta
        self.input_forcing_mod: dict = self.bmi_model._input_forcing_mod


class BMIForcingFixture_HistoricalRegrid(BMIForcingFixture):
    def __init__(
        self,
        bmi_model: NWMv3_Forcing_Engine_BMI_model,
        regrid_func: typing.Callable,
        regrid_arrays_to_trim_extra_elements: tuple[str],
        keys_to_check: tuple[str],
    ):
        """Writers of regrid tests must call the methods in this order. This is enforced by state attributes.
            self.pre_regrid()
            self.run_regrid()
            self.check_regrid_results()
            self.post_regrid()

        Parameters:
            regrid_func: The regrid function that is being tested.
            regrid_arrays_to_trim_extra_elements: These are output arrays which can contain extra unused elements which need to be removed during an equality check.
            keys_to_check: These are keys to include in the "expected" test results json, and are checked for equality versus "actual" results from regrid operation.
        """
        super().__init__(bmi_model=bmi_model)

        self.regrid_func = regrid_func
        self.regrid_arrays_to_trim_extra_elements = regrid_arrays_to_trim_extra_elements
        self.keys_to_check = keys_to_check
        self._state = None  # Test fixture state used to help ensure things happen in the right order

    @property
    def serialized_file_suffix(self) -> str:
        """Suffix for the file name for expected test results"""
        gpkg_basename = os.path.splitext(
            os.path.basename(self.config_options.geopackage)
        )[0]
        return f"_{gpkg_basename}_n{self.mpi_config.size}_rank{self.mpi_config.rank}_timestep{self.config_options.bmi_time_index}"

    @property
    def regrid_results_file_name_expect(self) -> str:
        """File name for expected test results."""
        test_dir = os.path.dirname(os.path.abspath(__file__))
        file_basename = (
            f"test_expect_{self.regrid_func.__name__}{self.serialized_file_suffix}.json"
        )
        file_path = os.path.join(
            test_dir, "test_data", "expected_results", file_basename
        )
        return file_path

    @property
    def regrid_results_file_name_actual(self) -> str:
        """File name for actual test results."""
        test_dir = os.path.dirname(os.path.abspath(__file__))
        file_basename = (
            f"test_actual_{self.regrid_func.__name__}{self.serialized_file_suffix}.json"
        )
        file_path = os.path.join(test_dir, "test_data", "actual_results", file_basename)
        return file_path

    def pre_regrid(self) -> None:
        """Run various timing setup methods and preprocessing steps needed *before*  each regrid call"""
        if self._state not in (None, "post_ran"):
            raise ValueError(
                f"In pre_regrid, expected state to be either None or 'post_ran' but got {repr(self._state)}. The test is set up incorrectly."
            )

        config_options = self.config_options
        mpi_config = self.mpi_config
        wrf_hydro_geo_meta = self.wrf_hydro_geo_meta
        supp_pcp_mod = self.bmi_model._supp_pcp_mod
        output_obj = self.bmi_model._output_obj
        input_forcing_mod = self.bmi_model._input_forcing_mod

        future_time = (
            self.bmi_model._values["current_model_time"]
            + self.bmi_model._values["time_step_size"]
        )
        model = self.bmi_model._model

        ### NOTE with the exception of setting the skip flag, the below
        ### block is copied verbatim from NWMv3ForcingEngineModel.run()
        (
            future_time,
            config_options,
        ) = model.determine_forecast(
            future_time,
            config_options,
        )
        (
            config_options,
            input_forcing_mod,
            mpi_config,
        ) = model.adjust_precip(
            config_options,
            input_forcing_mod,
            mpi_config,
        )
        (
            config_options,
            mpi_config,
        ) = model.log_forecast(
            config_options,
            mpi_config,
        )
        ### NOTE setting the flag causes the regrid step to be skipped
        self.set_input_forcings_skip_flags()
        (
            future_time,
            config_options,
            wrf_hydro_geo_meta,
            input_forcing_mod,
            supp_pcp_mod,
            mpi_config,
            output_obj,
            input_forcings,
        ) = model.loop_through_forcing_products(
            future_time,
            config_options,
            wrf_hydro_geo_meta,
            input_forcing_mod,
            supp_pcp_mod,
            mpi_config,
            output_obj,
        )

        # Update test fixture status
        self._state = "pre_ran"

    def set_input_forcings_skip_flags(self) -> None:
        """Set the `skip` flag on the InputForcings object so that historical forcing regrid will not occur during loop_through_forcing_products()."""
        logging.debug(
            "Setting input_forcing.skip = True for each value in dict self.input_forcing_mod"
        )
        for force_key, input_forcing in self.bmi_model._input_forcing_mod.items():
            input_forcing.skip = True

    def run_regrid(self, arg1: typing.Any) -> None:
        """Run the regrid function.

        Parameters:
            arg1 is the first argument to the regrid function, which can vary.
            For example is may be `input_forcings`, or `supplemental_precip`, or potentially others.
            Subsequent arguments to the regrid function should be standard and do not need to be provided by the test caller.
        """

        if self._state != "pre_ran":
            raise ValueError(
                f"In run_regrid, expected state to 'pre_ran' but got {repr(self._state)}. The test is set up incorrectly."
            )

        # regrid_inputs_json_str = serialize_to_json(
        #     arg1,
        #     out_file=f"tmp_regrid_inputs{self.serialized_file_suffix}.json",
        #     sort_keys=True,
        # )
        # wrf_hydro_geo_meta_json_str = serialize_to_json(
        #     self.wrf_hydro_geo_meta,
        #     out_file=f"tmp_wrf_hydro_geo_meta{self.serialized_file_suffix}.json",
        #     sort_keys=True,
        # )

        logging.info(
            f"Calling regrid function: {self.regrid_func.__name__} using arg1 of type {type(arg1)}"
        )
        self.regrid_func(
            arg1,
            config_options=self.config_options,
            wrf_hydro_geo_meta=self.wrf_hydro_geo_meta,
            mpi_config=self.mpi_config,
        )
        logging.info(f"Done calling regrid function: {self.regrid_func.__name__}")
        # Update test fixture status
        self._state = "regrid_ran"

    def remove_extra_data_from_regrid_results(
        self, input_forcings: InputForcings
    ) -> dict:
        """Validate some high-level aspects of the InputForcings object, such as length and sequence of some arrays.
        Then build a dictionary equivalent of it, and trim some of the arrays to the needed size for tests, and return that dictionary.

        Resulting output numerical arrays of regridding process may contain extra elements that are
        unused, contain unpredictable values, and should be ignored, i.e. should be removed from test results.

        This is detected by inspecting lengths and inspecting explicit array index positions
        referenced by `input_map_output`.

        For example:
            `input_map_output` may contain 8 elements spanning values 0 through 7 (in any order), while `regridded_forcings1` and `regridded_forcings2` may contain 9 elements each.
            In this case, we infer that index 8 (the ninth element) should be ignored.
            We assert that this is the case by confirming that index 8 does not exist in `input_map_output`.
            Then we remove that element from the right end of `regridded_forcings1` and `regridded_forcings2`.

        Parameters:
            input_forcings is the InputForcings object immediately after a ESMF regridding has occurred.

        Returns:
            A dictionary representation of input_forcings, but with some arrays trimmed and some keys dropped.
        """
        ### This is returned after being modified.
        input_forcings_deserial = json.loads(serialize_to_json(input_forcings))
        ### e.g. ['TMP_2maboveground', 'SPFH_2maboveground', 'UGRD_10maboveground', 'VGRD_10maboveground', 'APCP_surface', 'DSWRF_surface', 'DLWRF_surface', 'PRES_surface']
        netcdf_var_names = input_forcings.netcdf_var_names
        ### e.g. ['TMP', 'SPFH', 'UGRD', 'VGRD', 'APCP', 'DSWRF', 'DLWRF', 'PRES']
        grib_vars = input_forcings.grib_vars
        ### The order that the vars appear in the regridded output numerical arrays. e.g. [4, 5, 0, 1, 3, 7, 2, 6] means that "TMP" is at index 4 (the fifth item) in the numerical array.
        input_map_output = input_forcings.input_map_output

        errors: list[Exception] = []

        ### Assert that input_map_output has no duplicates
        if len(input_map_output) != len(set(input_map_output)):
            errors.append(
                ValueError(f"Duplicates exist in input_map_output: {input_map_output}")
            )

        ### Assert that input_map_output has no gaps
        for i in range(len(input_map_output)):
            if i not in input_map_output:
                errors.append(
                    ValueError(
                        f"Index {i} is missing from input_map_output: {input_map_output}"
                    )
                )

        ### Assert that the range of input_map_output is sequential from 0
        if min(input_map_output) != 0:
            errors.append(
                ValueError(
                    f"Expected min(input_map_output) to be 0 but got {min(input_map_output)}"
                )
            )
        if max(input_map_output) != len(input_map_output) - 1:
            errors.append(
                ValueError(
                    f"Expected max(input_map_output) to be (len(input_map_output) - 1) aka ({len(input_map_output) - 1}) but got {max(input_map_output)}"
                )
            )

        ### Assert that netcdf_var_names and grib_vars have equal length
        if len(netcdf_var_names) != len(grib_vars):
            errors.append(
                ValueError(
                    f"len(netcdf_var_names) != len(grib_vars): {len(netcdf_var_names)} vs {len(grib_vars)}"
                )
            )

        ### Remove extra indexes from output arrays.
        for key in self.regrid_arrays_to_trim_extra_elements:
            logging.debug(
                f"Trimming values of key {key} if they are longer than input_map_output (if longer than {len(input_map_output)})"
            )
            attr = input_forcings_deserial[key]
            ### Some are naturally None.
            if attr is None:
                continue
            ### If equal length already, then there's nothing to do.
            if len(attr) == len(input_map_output):
                continue
            ### Assert that length of the array is at least as long as input_map_output.
            if len(attr) < len(input_map_output):
                errors.append(
                    ValueError(
                        f"Expected length of array for key {key} to be at least as long as input_map_output ({len(input_map_output)}), but got length {len(attr)}"
                    )
                )
                continue
            ### Trim the 2d list. First assert it is a list of lists (it should have originated as a 2D array)
            if not isinstance(attr, list):
                errors.append(
                    f"Expected type list[list], got {type(attr)} for key {key}"
                )
                continue
            if not isinstance(attr[0], list):
                errors.append(
                    f"Expected type list[list], got {type(attr)} for key {key}"
                )
                continue
            attr = attr[: len(input_map_output)]
            input_forcings_deserial[key] = attr

        if errors:
            raise RuntimeError(f"input_forcings had invalid state. Errors: {errors}")

        return input_forcings_deserial

    def check_regrid_results(self, input_forcings: InputForcings) -> None:
        """Check the regrid results against previously serialized expected results data, which should be in the repository.
        Run this with a certain OS var to set up fresh test results expected data files.

        Parameters:
            input_forcings is the InputForcings object immediately after a ESMF regridding has occurred.
        """

        if self._state != "regrid_ran":
            raise ValueError(
                f"In check_regrid_results, expected state to 'regrid_ran' but got {repr(self._state)}. The test is set up incorrectly."
            )

        ### Check the output regrid weights file
        pass  # TODO is this needed?

        ### Convert the raw input_forcings object to a serialized-then-deserialized dictionary, trimming some of the arrays as needed.
        regrid_results_actual = self.remove_extra_data_from_regrid_results(
            input_forcings
        )
        ### Remove unchecked keys
        regrid_results_actual = {
            k: v for k, v in regrid_results_actual.items() if k in self.keys_to_check
        }
        # regrid_results_actual["nx_local"] = float("inf")  # This will trigger a test failure
        # regrid_results_actual["ny_local"] = float("-inf")  # This will trigger a test failure
        ### Serialize the cleaned up dictionary
        regrid_results_json_str = serialize_to_json(
            regrid_results_actual, sort_keys=True
        )

        logging.warning(f"Writing actual data: {self.regrid_results_file_name_actual}")
        with open(self.regrid_results_file_name_actual, "w") as f:
            f.write(regrid_results_json_str)

        ### NOTE this should be rarely used, only when updating the test expected outputs dataset
        if os.environ.get(OS_VAR__CREATE_TEST_EXPECT_DATA, "").lower() == "true":
            # Dump current results to disk, to save it as "expected" results for later test runs.
            # Should only be used when committing new test results to the repository.
            logging.warning(
                f"Writing test data: {self.regrid_results_file_name_expect}"
            )
            with open(self.regrid_results_file_name_expect, "w") as f:
                f.write(regrid_results_json_str)

        ### Load expected regrid outputs
        logging.info(
            f"Reading expected test results data: {self.regrid_results_file_name_expect}"
        )
        try:
            with open(self.regrid_results_file_name_expect) as f:
                regrid_results_expect = json.load(f)
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"Could not find {self.regrid_results_file_name_expect}. Try running the test using OS var {OS_VAR__CREATE_TEST_EXPECT_DATA}=true first to set up the test results expected data."
            ) from e

        # keys_to_check = ("nx_local", "ny_local", "nx_global", "ny_global")
        # regrid_results_expect = {
        #     k: v for k, v in regrid_results_expect.items() if k in keys_to_check
        # }

        try:
            assert_equal_with_tol(
                expect=regrid_results_expect, actual=regrid_results_actual
            )
        except ExpectVsActualError as e:
            raise RuntimeError(
                f"Unexpected results compared to {self.regrid_results_file_name_expect}: {e}"
            ) from e

    def post_regrid(self) -> None:
        """Run various timing setup methods and postprocessing steps needed *after* each regrid call"""
        if self._state != "regrid_ran":
            raise ValueError(
                f"In post_regrid, expected state to 'regrid_ran' but got {repr(self._state)}. The test is set up incorrectly."
            )

        # Manually update some timing attributes, following existing conventions. (20260227)
        # From bottom of model.py run()
        self.config_options.bmi_time_index += 1
        # From bmi_model.py update_until()
        self.bmi_model._values["current_model_time"] += self.bmi_model._values[
            "time_step_size"
        ]
        # Update test fixture status
        self._state = "post_ran"


@pytest.fixture
def bmi_forcing_fixture(request) -> BMIForcingFixture:
    """Constructor for minimal class of classes for running BMI forcing.
    For example usage, see: tests/esmf_regrid/test_esmf_regrid.test_regrid_aorc_aws.

    Parameters:
        request is a built-in convention for pytest.fixture.  It may be passed from @pytest.mark.parametrize usage elsewhere.
    """
    (config_file,) = request.param
    bmi_model = NWMv3_Forcing_Engine_BMI_model()
    bmi_model.initialize_with_params(
        config_file=config_file,
        b_date=None,
        geogrid=None,
        output_path=None,
    )
    return BMIForcingFixture(bmi_model=bmi_model)


@pytest.fixture
def bmi_forcing_fixture_historical_regrid(
    request,
) -> BMIForcingFixture_HistoricalRegrid:
    """Constructor for minimal class of classes for running BMI historical forcing ESMF regrid functions.
    For example usage, see: tests/esmf_regrid/test_esmf_regrid.test_regrid_aorc_aws.

    Parameters:
        request is a built-in convention for pytest.fixture.  It may be passed from @pytest.mark.parametrize usage elsewhere.
    """
    (
        regrid_func,
        config_file,
        regrid_arrays_to_trim_extra_elements,
        keys_to_check,
    ) = request.param

    bmi_model = NWMv3_Forcing_Engine_BMI_model()
    bmi_model.initialize_with_params(
        config_file=config_file,
        b_date=None,
        geogrid=None,
        output_path=None,
    )
    return BMIForcingFixture_HistoricalRegrid(
        bmi_model=bmi_model,
        regrid_func=regrid_func,
        regrid_arrays_to_trim_extra_elements=regrid_arrays_to_trim_extra_elements,
        keys_to_check=keys_to_check,
    )
