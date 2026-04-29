"""Conventional pytest file conftest.py. Automatically discovered and implicitly imported by pytest."""

import pytest

from test_utils import (
    BMIForcingFixture,
    BMIForcingFixture_GeoMod,
    BMIForcingFixture_InputForcing,
    BMIForcingFixture_Regrid,
)

from test_config_classes import (
    TestConfig_Base,
    TestConfig_GeoMod,
    TestConfig_InputForcing,
    TestConfig_Regrid,
)

from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.bmi_model import (
    BMIMODEL,
    NWMv3_Forcing_Engine_BMI_model,
)


@pytest.fixture
def bmi_forcing_fixture(request) -> BMIForcingFixture:
    """Construct class for tests.

    Args:
        request: A built-in convention for pytest.fixture.  It may be passed from @pytest.mark.parametrize usage elsewhere.
    """
    cfg = request.param
    assert isinstance(cfg, TestConfig_Base)
    bmi_model = NWMv3_Forcing_Engine_BMI_model()
    bmi_model.initialize_with_params(config_file=cfg.config_file)
    return BMIForcingFixture(bmi_model=bmi_model)


@pytest.fixture
def bmi_forcing_fixture_regrid(
    request,
) -> BMIForcingFixture_Regrid:
    """Construct class for tests of ESMF regrid functions.
    For example usage, see: tests/esmf_regrid/test_esmf_regrid.py.

    Args:
        request: A built-in convention for pytest.fixture.  It may be passed from @pytest.mark.parametrize usage elsewhere.
    """
    cfg = request.param
    assert isinstance(cfg, TestConfig_Regrid)

    bmi_model = BMIMODEL[cfg.grid_type]()
    bmi_model.initialize_with_params(config_file=cfg.config_file)
    return BMIForcingFixture_Regrid(
        bmi_model=bmi_model,
        regrid_func=cfg.regrid_func,
        force_key=cfg.force_key,
        keys_to_exclude=cfg.keys_to_exclude,
        extra_attrs=cfg.extra_attrs,
        regrid_arrays_to_trim_extra_elements=cfg.regrid_arrays_to_trim_extra_elements,
        keys_to_check=cfg.keys_to_check,
    )


@pytest.fixture
def bmi_forcing_fixture_geomod(
    request,
) -> BMIForcingFixture_GeoMod:
    """Construct class for tests of GeoMod.
    For example usage, see: tests/geomod/test_geomod.py.

    Args:
        request: A built-in convention for pytest.fixture.  It may be passed from @pytest.mark.parametrize usage elsewhere.
    """
    cfg = request.param
    assert isinstance(cfg, TestConfig_GeoMod)

    bmi_model = BMIMODEL[cfg.grid_type]()
    bmi_model.initialize_with_params(config_file=cfg.config_file)
    return BMIForcingFixture_GeoMod(
        bmi_model=bmi_model,
        keys_to_check=cfg.keys_to_check,
        keys_to_exclude=cfg.keys_to_exclude,
    )


def pytest_addoption(parser):
    """Add command line options to pytest."""
    parser.addoption(
        "--map_old_to_new_var_names",
        action="store",
        default=True,
        help="Argument to specify if old variables names should be mapped to new variable names.",
    )


@pytest.fixture
def bmi_forcing_fixture_input_forcing(
    request,
) -> BMIForcingFixture_InputForcing:
    """Construct class for tests of input_forcing.
    For example usage, see: tests/input_forcing/test_input_forcing.py.

    Args:
        request: A built-in convention for pytest.fixture.  It may be passed from @pytest.mark.parametrize usage elsewhere.
    """
    cfg = request.param
    assert isinstance(cfg, TestConfig_InputForcing)

    bmi_model = BMIMODEL[cfg.grid_type]()
    bmi_model.initialize_with_params(config_file=cfg.config_file)

    map_old_to_new_var_names = request.config.getoption("--map_old_to_new_var_names")
    if map_old_to_new_var_names == "True" or map_old_to_new_var_names is True:
        map_old_to_new_var_names = True
    elif map_old_to_new_var_names == "False" or map_old_to_new_var_names is False:
        map_old_to_new_var_names = False
    else:
        raise ValueError(
            f"Unexpected value for arg: map_old_to_new_var_names. Expected True or False; recieved: {map_old_to_new_var_names}"
        )

    return BMIForcingFixture_InputForcing(
        bmi_model=bmi_model,
        keys_to_check=cfg.keys_to_check,
        keys_to_exclude=cfg.keys_to_exclude,
        force_key=cfg.force_key,
        map_old_to_new_var_names=map_old_to_new_var_names,
    )
