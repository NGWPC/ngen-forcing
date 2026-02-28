"""pytest tests for ESMF regrid functions"""

import json
import logging

import pytest

from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.core.regrid import (
    regrid_aorc_aws,
)
from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.historical_forcing import (
    AORCConusProcessor,
)

from tests.test_utils import bmi_forcing_fixture, BMIForcingFixture, serialize_to_json


RETRO_FORCING_CONFIG_FILE__AORC_CONUS = (
    "/ngwpc/run_ngen/kge_dds/test_bmi/01123000/Input/forcing_config/aorc_config.yml"
)


@pytest.mark.parametrize(
    "bmi_forcing_fixture", [RETRO_FORCING_CONFIG_FILE__AORC_CONUS], indirect=True
)
def test_regrid_aorc_aws(bmi_forcing_fixture: BMIForcingFixture) -> None:
    """pytest function for testing ESMF regrid functionality for AORC historical forcing data."""
    bff = bmi_forcing_fixture

    # Total number of timesteps needs to be at least 2, since the 1st one behaves differently than the others,
    # for example see `if config_options.current_output_step == 1` throughout the code
    total_timesteps = 3

    if len(bff.input_forcings_mod) != 1:
        raise ValueError(
            f"Expected 1 key for input_forcings_mod, got {len(bff.input_forcings_mod)}: {list(bff.input_forcings_mod.keys())}"
        )
    force_key = list(bff.input_forcings_mod.keys())[0]

    source_data_processor = AORCConusProcessor(
        bff.config_options,
        bff.mpi_config,
        bff.wrf_hydro_geo_meta,
    )

    for i in range(total_timesteps):
        # Populate config_options.current_time
        bff.bmi_model._model.determine_forecast(
            future_time=bff.bmi_model._values["current_model_time"]
            + bff.bmi_model._values["time_step_size"],
            config_options=bff.config_options,
        )

        input_forcings = bff.input_forcings_mod[force_key]

        # process_historical_data has a side-effect of updating self.current_time, and may have other important side-effects. (20260227)
        bff.config_options.aws_obj = source_data_processor.process_historical_data(
            bff.config_options.current_time
        )

        logging.info("Calling regrid_aorc_aws")
        regrid_aorc_aws(
            input_forcings,
            bff.config_options,
            bff.wrf_hydro_geo_meta,
            bff.mpi_config,
        )
        logging.info("Done calling regrid_aorc_aws")

        # Check the output regrid weights file
        pass  # TODO

        # Check the objects in memory
        json_str = serialize_to_json(input_forcings)
        json_str_loaded = json.loads(json_str)
        pass  # TODO

        # Manually update some timing attributes, following existing conventions. (20260227)
        # From bottom of model.py run()
        bff.config_options.bmi_time_index += 1
        # From bmi_model.py update_until()
        bff.bmi_model._values["current_model_time"] += bff.bmi_model._values[
            "time_step_size"
        ]

    raise NotImplementedError("This test is a work in progress")
