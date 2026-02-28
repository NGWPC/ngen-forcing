"""Utilities for ngen-forcing tests"""

import json

import pytest

from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.bmi_model import (
    NWMv3_Forcing_Engine_BMI_model,
)
from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.core.config import (
    ConfigOptions,
)
from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.core.forcingInputMod import (
    init_dict as initialize_input_forcings_dict,
)
from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.core.geoMod import (
    GeoMetaWrfHydro,
)
from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.core.parallel import MpiConfig


JSON_SERIALIZE_FALLBACK_VALUE = "ERR_NOT_JSON_SERIALIZABLE"


def serializer_with_fallback(obj):
    if hasattr(obj, "__dict__"):
        # It is serializable
        return obj.__dict__
    else:
        # It is not serializable
        return JSON_SERIALIZE_FALLBACK_VALUE


def serialize_to_json(obj, out_file: str = None) -> str:
    """Serialize the provided object, and optionally write it to a new file"""
    json_str = json.dumps(obj, default=serializer_with_fallback, indent=2)
    if out_file is not None:
        print(f"Writing: {out_file}")
        with open(out_file, "w") as f:
            f.write(json_str)
    return json_str


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


@pytest.fixture
def bmi_forcing_fixture(request) -> BMIForcingFixture:
    """Constructor for minimal class of classes for running BMI forcing.
    For example usage, see: tests/esmf_regrid/test_esmf_regrid.test_regrid_aorc_aws.
    """
    bmi_model = NWMv3_Forcing_Engine_BMI_model()
    bmi_model.initialize_with_params(
        config_file=request.param,
        b_date=None,
        geogrid=None,
        output_path=None,
    )
    return BMIForcingFixture(bmi_model=bmi_model)
