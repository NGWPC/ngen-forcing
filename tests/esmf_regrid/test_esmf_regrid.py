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

### These are output arrays which can contain extra unused elements which need to be removed during an equality check.
REGRID_ARRAYS_TO_TRIM_EXTRA_ELEMENTS = (
    "regridded_forcings1",
    "regridded_forcings1_elem",
    "regridded_forcings2",
    "regridded_forcings2_elem",
)

### These are keys to include in the "expected" test results json, and are checked for equality versus "actual" results from regrid operation.
REGRID_KEYS_TO_CHECK = REGRID_ARRAYS_TO_TRIM_EXTRA_ELEMENTS + (
    # "esmf_field_in",
    # "esmf_field_in_elem",
    # "esmf_grid_in",
    # "esmf_grid_in_elem",
    # "esmf_field_out",
    # "esmf_field_out_elem",
    "regridded_mask",
    ### TODO revisit to see if this should be checked. Some notes in the code indicate that it is not used, but this has not been confirmed globally.
    # "regridded_mask_AORC",
    "regridded_mask_elem",
    "regridded_mask_elem_AORC",
    "regridded_precip1",
    "regridded_precip1_elem",
    "regridded_precip2",
    "regridded_precip2_elem",
)


@pytest.mark.parametrize(
    "bmi_forcing_fixture_historical_regrid",
    [
        (
            regrid_aorc_aws,
            RETRO_FORCING_CONFIG_FILE__AORC_CONUS,
            REGRID_ARRAYS_TO_TRIM_EXTRA_ELEMENTS,
            REGRID_KEYS_TO_CHECK,
        )
    ],
    indirect=True,
)
def test_regrid_aorc_aws(
    bmi_forcing_fixture_historical_regrid: BMIForcingFixture_HistoricalRegrid,  # noqa: F811
) -> None:
    """pytest function for testing ESMF regrid functionality for AORC historical forcing data.
    NOTE vvv this has been tested for the following conditions only vvv
        1. Hydrofabric discretization, AORC historical forcing, CONUS domain, nprocs == 1 (number of MPI ranks == 1).
    NOTE ^^^ this has been tested for the above conditions only ^^^
    """
    fixt = bmi_forcing_fixture_historical_regrid

    # Total number of timesteps needs to be at least 2, since the 1st one behaves differently than the others,
    # for example see `if config_options.current_output_step == 1` throughout the code
    total_timesteps = 3

    if len(fixt.input_forcing_mod) != 1:
        raise ValueError(
            f"Expected 1 key for input_forcing_mod, got {len(fixt.input_forcing_mod)}: {list(fixt.input_forcing_mod.keys())}"
        )
    force_key = list(fixt.input_forcing_mod.keys())[0]
    input_forcings = fixt.input_forcing_mod[force_key]

    for i in range(total_timesteps):
        fixt.pre_regrid()
        fixt.run_regrid(input_forcings)
        fixt.remove_extra_data_from_regrid_results(input_forcings)
        fixt.check_regrid_results(input_forcings)
        fixt.post_regrid()

    raise NotImplementedError("This test is a work in progress")
