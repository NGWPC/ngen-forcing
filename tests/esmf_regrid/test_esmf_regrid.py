"""pytest tests for ESMF regrid functions"""

import logging

import pytest

from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.core.regrid import (
    regrid_aorc_aws,
)
from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.historical_forcing import (
    AORCConusProcessor,
)

from tests.test_utils import (
    bmi_forcing_fixture_historical_regrid,  # noqa: F401
    BMIForcingFixture_HistoricalRegrid,
)


RETRO_FORCING_CONFIG_FILE__AORC_CONUS = (
    "/ngwpc/run_ngen/kge_dds/test_bmi/01123000/Input/forcing_config/aorc_config.yml"
)


@pytest.mark.parametrize(
    "bmi_forcing_fixture_historical_regrid",
    [(regrid_aorc_aws, AORCConusProcessor, RETRO_FORCING_CONFIG_FILE__AORC_CONUS)],
    indirect=True,
)
def test_regrid_aorc_aws(
    bmi_forcing_fixture_historical_regrid: BMIForcingFixture_HistoricalRegrid,  # noqa: F811
) -> None:
    """pytest function for testing ESMF regrid functionality for AORC historical forcing data."""
    fixt = bmi_forcing_fixture_historical_regrid

    # Total number of timesteps needs to be at least 2, since the 1st one behaves differently than the others,
    # for example see `if config_options.current_output_step == 1` throughout the code
    total_timesteps = 3

    if len(fixt.input_forcings_mod) != 1:
        raise ValueError(
            f"Expected 1 key for input_forcings_mod, got {len(fixt.input_forcings_mod)}: {list(fixt.input_forcings_mod.keys())}"
        )
    force_key = list(fixt.input_forcings_mod.keys())[0]
    input_forcings = fixt.input_forcings_mod[force_key]

    for i in range(total_timesteps):
        fixt.pre_regrid()
        fixt.run_regrid(input_forcings)
        fixt.check_regrid_results(input_forcings)
        fixt.post_regrid()

    raise NotImplementedError("This test is a work in progress")
