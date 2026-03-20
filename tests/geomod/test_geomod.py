"""pytest tests for GeoMod.

Setup requirements:
    1. Create the forcing config.yml files using RTE.
    2. Enter the RTE devcontainer.

Usage:
    The initial test data was generated using RTE to create a calibration realization
    for gage 01123000, starting at time 2013-07-01 00:00:00, and running for 3 timesteps,
    using RTE's run_suite.sh.  See RETRO_FORCING_CONFIG_FILE__AORC_CONUS.

    Run like this for a typical test run (checking against existing test output data)
        Single processor: ( cd src/ngen-forcing && pytest )
        Multiple processors: ( cd src/ngen-forcing && mpirun -n 2 pytest )

    Run like this to create new test output data (created expected outputs for subsequent tests):
        Single processor: ( cd src/ngen-forcing && FORCING_PYTEST_WRITE_TEST_EXPECTED_DATA=true pytest )
        Multiple processors: ( cd src/ngen-forcing && FORCING_PYTEST_WRITE_TEST_EXPECTED_DATA=true mpirun -n 2 pytest )
"""

import importlib.util
import os

import pytest

### Load import tests.test_utils as test_utils, referring explicitly to its path.
### This explicit load is necessary since March 2026 versions of ngen which introduced /ngen-app/ngen/extern/topoflow-glacier/tests
spec = importlib.util.spec_from_file_location(
    "tests.test_utils", os.path.abspath("tests/test_utils.py")
)
test_utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(test_utils)


### This disables a LOG call which was causing a crash at ioMod.py: LOG.debug(f"Wgrib2 command: {Wgrib2Cmd}", True)
os.environ["MFE_SILENT"] = "true"


RETRO_FORCING_CONFIG_FILE__AORC_CONUS = (
    "/ngwpc/run_ngen/kge_dds/test_bmi/01123000/Input/forcing_config/aorc_config.yml"
)
FORECAST_FORCING_CONFIG_FILE__SHORT_RANGE_CONUS = "/ngwpc/run_ngen/kge_dds/test_bmi/01123000/Output/Forecast_Run/fcst_run1_short_range/forcing_config/short_range_config.yml"

COMPOSITE_KEYS_TO_CHECK = ()
GRID_TYPE = "hydrofabric"  # ["gridded","hydrofabric","unstructured"]


@pytest.mark.parametrize(
    "bmi_forcing_fixture_geomod",
    [(RETRO_FORCING_CONFIG_FILE__AORC_CONUS, COMPOSITE_KEYS_TO_CHECK, GRID_TYPE)],
    indirect=True,
)
def test_geomod(
    bmi_forcing_fixture_geomod: test_utils.BMIForcingFixture_GeoMod,  # pyright: ignore
) -> None:
    """Pytest function for testing GeoMod functionality."""
    ### Total number of timesteps needs to be at least 2, since the 1st one behaves differently than the others, e.g. see `if config_options.current_output_step == 1` throughout the code.
    total_timesteps = 3

    fixt = bmi_forcing_fixture_geomod
    if len(fixt.input_forcing_mod) != 1:
        raise ValueError(
            f"Expected 1 key for input_forcing_mod, got {len(fixt.input_forcing_mod)}: {list(fixt.input_forcing_mod.keys())}"
        )

    fixt.after_intitialization_check()
    for i in range(total_timesteps):
        fixt.bmi_model.update()
        fixt.after_bmi_model_update(
            current_output_step=i + 1,
        )
    fixt.bmi_model.finalize()
    fixt.after_finalize()
