"""Conventional pytest file conftest.py. Automatically discovered and implicitly imported by pytest."""

import pytest

from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.bmi_model import (
    NWMv3_Forcing_Engine_BMI_model,
)

from test_utils import BMIForcingFixture, BMIForcingFixture_Regrid


@pytest.fixture
def bmi_forcing_fixture(request) -> BMIForcingFixture:
    """Constructor for minimal class of classes for running BMI forcing.
    For example usage, see: tests/esmf_regrid/test_esmf_regrid.test_regrid.

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
def bmi_forcing_fixture_regrid(
    request,
) -> BMIForcingFixture_Regrid:
    """Constructor for minimal class of classes for running forcing ESMF regrid functions.
    For example usage, see: tests/esmf_regrid/test_esmf_regrid.test_regrid.

    Parameters:
        request is a built-in convention for pytest.fixture.  It may be passed from @pytest.mark.parametrize usage elsewhere.
    """
    (
        regrid_func,
        config_file,
        force_key,
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
    return BMIForcingFixture_Regrid(
        bmi_model=bmi_model,
        regrid_func=regrid_func,
        force_key=force_key,
        regrid_arrays_to_trim_extra_elements=regrid_arrays_to_trim_extra_elements,
        keys_to_check=keys_to_check,
    )
