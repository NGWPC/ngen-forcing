"""Utilities for ngen-forcing tests"""

import json
import logging
import os
import typing

import numpy as np
import pytest

from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.bmi_model import (
    NWMv3_Forcing_Engine_BMI_model,
)
from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.core.config import (
    ConfigOptions,
)
from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.core.forcingInputMod import (
    init_dict as initialize_input_forcings_dict,
    InputForcings,
)
from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.core.geoMod import (
    GeoMetaWrfHydro,
)
from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.core.parallel import MpiConfig


JSON_NOT_SERIALIZABLE_FORMAT = "ERR_NOT_JSON_SERIALIZABLE:TYPE:{typ}"
OS_VAR__CREATE_TEST_EXPECT_DATA = "FORCING_PYTEST_WRITE_TEST_EXPECTED_DATA"


class ExpectVsActualError(Exception):
    """Raised by assert_equal_with_tol"""


def serializer_with_fallback(obj):
    if hasattr(obj, "__dict__"):
        # It is serializable
        return obj.__dict__
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, np.generic):
        return obj.item()
    else:
        # It is not serializable
        return JSON_NOT_SERIALIZABLE_FORMAT.format(typ=str(type(obj)))


def serialize_to_json(obj, out_file: str = None) -> str:
    """Serialize the provided object, and optionally write it to a new file"""
    json_str = json.dumps(obj, default=serializer_with_fallback, indent=2)
    if out_file is not None:
        print(f"Writing: {out_file}")
        with open(out_file, "w") as f:
            f.write(json_str)
    return json_str


def assert_equal_with_tol(expect: dict, actual: dict):
    """Assert that the key,value pairs in `expect` have matching key,value pairs in `actual`, with numerical tolerance.
    It is okay if actual has extra keys that are not present in expect.
    TODO: implement the numerical tolerance (this currently uses hard equality check without tolerance).
    """
    errors: list[Exception] = []
    logging.debug(
        f"Asserting equality with tolerance for {len(expect)} keys: {list(expect.keys())}"
    )
    for k, v_expect in expect.items():
        logging.debug(f"Key {repr(k)} has expected value {v_expect}")
        v_actual = actual[k]
        logging.debug(
            f"Key {repr(k)} has expected value {v_expect} and actual value {v_actual}"
        )
        if v_actual != v_expect:
            errors.append(
                ValueError(
                    f"Not equal: for key {repr(k)}, expected {v_expect} but got {v_actual}"
                )
            )
    if errors:
        raise ExpectVsActualError(errors)


class BMIForcingFixture:
    """Minimal class of classes for running BMI forcing.
    For example usage, see: tests/esmf_regrid/test_esmf_regrid.test_regrid_aorc_aws.
    """

    def __init__(self, bmi_model: NWMv3_Forcing_Engine_BMI_model):
        self.bmi_model: NWMv3_Forcing_Engine_BMI_model = bmi_model
        self.mpi_config: MpiConfig = bmi_model._mpi_meta
        self.config_options: ConfigOptions = bmi_model._job_meta
        self.wrf_hydro_geo_meta: GeoMetaWrfHydro = bmi_model._wrf_hydro_geo_meta
        self.input_forcings_mod: dict = initialize_input_forcings_dict(
            config_options=self.config_options,
            geo_meta_wrf_hydro=self.wrf_hydro_geo_meta,
            mpi_config=self.mpi_config,
        )


class BMIForcingFixture_HistoricalRegrid(BMIForcingFixture):
    def __init__(
        self,
        bmi_model: NWMv3_Forcing_Engine_BMI_model,
        regrid_func: typing.Callable,
        source_data_processor_factory: type | typing.Callable,
    ):
        """Writers of regrid tests must call the methods in this order. This is enforced by state attributes.
            self.pre_regrid()
            self.run_regrid()
            # Then check results before calling self.post_regrid()
            # ...
            # ...
            # ...
            self.post_regrid()
        source_data_processor_factory could be AORCConusProcessor or another function that makes and returns an analogous class instance
        """
        super().__init__(bmi_model=bmi_model)

        self.regrid_func = regrid_func
        self.source_data_processor = source_data_processor_factory(
            self.config_options,
            self.mpi_config,
            self.wrf_hydro_geo_meta,
        )
        self._state = None  # Test fixture state used to help ensure things happen in the right order

    @property
    def regrid_results_expect_data_file_name(self) -> str:
        """File name for expected test results."""
        test_dir = os.path.dirname(os.path.abspath(__file__))
        file_basename = f"test_expect_{self.regrid_func.__name__}_{self.config_options.bmi_time_index}.json"
        file_path = os.path.join(
            test_dir, "test_data", "expected_results", file_basename
        )
        return file_path

    def pre_regrid(self):
        """Run various timing setup methods and preprocessing steps needed *before*  each regrid call"""
        if self._state not in (None, "post_ran"):
            raise ValueError(
                f"In pre_regrid, expected state to be either None or 'post_ran' but got {repr(self._state)}. The test is set up incorrectly."
            )

        # Populate config_options.current_time
        self.bmi_model._model.determine_forecast(
            future_time=self.bmi_model._values["current_model_time"]
            + self.bmi_model._values["time_step_size"],
            config_options=self.config_options,
        )
        # process_historical_data has a side-effect of updating self.current_time, and may have other important side-effects. (20260227)
        self.config_options.aws_obj = (
            self.source_data_processor.process_historical_data(
                self.config_options.current_time
            )
        )
        # Update test fixture status
        self._state = "pre_ran"

    def run_regrid(self, arg1: typing.Any):
        """Run the regrid function. arg1 is the first argument to the regrid function, which can vary.
        For example is may be `input_forcings`, or `supplemental_precip`, or potentially others.
        Subsequent arguments to the regrid function should be standard and do not need to be provided by the test caller."""

        if self._state != "pre_ran":
            raise ValueError(
                f"In run_regrid, expected state to 'pre_ran' but got {repr(self._state)}. The test is set up incorrectly."
            )

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

    def check_regrid_results(self, input_forcings: InputForcings):
        """Check the regrid results against previously serialized expected results data, which should be in the repository.
        Run this with a certain OS var to set up fresh test results expected data files."""

        if self._state != "regrid_ran":
            raise ValueError(
                f"In check_regrid_results, expected state to 'regrid_ran' but got {repr(self._state)}. The test is set up incorrectly."
            )

        # Check the output regrid weights file
        pass  # TODO

        regrid_results_json_str = serialize_to_json(input_forcings)
        regrid_results_actual = json.loads(regrid_results_json_str)
        # regrid_results_actual["nx_local"] = float("inf")  # This will trigger a test failure
        # regrid_results_actual["ny_local"] = float("-inf")  # This will trigger a test failure

        if os.environ.get(OS_VAR__CREATE_TEST_EXPECT_DATA, "").lower() == "true":
            # Dump current results to disk, to save it as "expected" results for later test runs.
            # Should only be used when committing new test results to the repository.
            logging.warning(
                f"Writing test data: {self.regrid_results_expect_data_file_name}"
            )
            with open(self.regrid_results_expect_data_file_name, "w") as f:
                f.write(regrid_results_json_str)

        logging.info(
            f"Reading expected test results data: {self.regrid_results_expect_data_file_name}"
        )
        try:
            with open(self.regrid_results_expect_data_file_name) as f:
                regrid_results_expect = json.load(f)
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"Could not find {self.regrid_results_expect_data_file_name}. Try running the test using OS var {OS_VAR__CREATE_TEST_EXPECT_DATA}=true first to set up the test results expected data."
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
                f"Unexpected results compared to {self.regrid_results_expect_data_file_name}: {e}"
            ) from e

    def post_regrid(self):
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
    """
    # Passed from @pytest.mark.parametrize usage
    (regrid_func, source_data_processor_factory, config_file) = request.param

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
        source_data_processor_factory=source_data_processor_factory,
    )
