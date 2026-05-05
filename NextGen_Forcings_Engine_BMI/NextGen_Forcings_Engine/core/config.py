import configparser
import json
import os
import re
from datetime import datetime, timedelta, timezone
from functools import cached_property

import ewts
import numpy as np

from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.core import mpi_utils
from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.core.consts import (
    CONFIGOPTIONS,
    FORCINGINPUTMOD,
)
from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.core.err_handler import (
    err_out_screen,
)
from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.core.time_handling import (
    calculate_lookback_window,
)

LOG = ewts.get_logger(ewts.FORCING_ID)


class ConfigOptions:
    """Configuration abstract class for configuration options read in from the file specified by the user."""

    def __init__(self, cfg_bmi: dict, b_date: str = None, geogrid: str = None) -> None:
        """Initialize the configuration class to empty None attributes.

        The attributes of this class are populated by the validate_config function, which reads in the configuration file and checks that all necessary options are provided and properly formatted. The attributes of this class are used to control the flow of the program and the processing of input forcings.

        Args:
            cfg_bmi (dict): The configuration dictionary read in from the configuration file specified by the user. This should be read in using the config_utils.read_config function, which also handles any necessary preprocessing of the configuration file.
            b_date (str, optional): The beginning date of processing in the format YYYYMMDDHHMM. This is used to calculate the processing window for realtime simulations. If not provided, it will be read from the configuration file.
            geogrid (str, optional): The filepath to the geogrid file to be used for processing. This is used to specify the grid information for regridding input forcings. If not provided, it will be read from the configuration file.

        """
        self.bmi_time_index = 0
        self.precip_only_flag = False
        self.number_custom_inputs = 0
        self.useCompression = 0
        self.useFloats = 0
        self._b_date_proc = b_date
        self._cfg_bmi = cfg_bmi
        self.runCfsNldasBiasCorrect = False
        self.rqiThresh = 1.0
        self.globalNdv = -9999.0
        self.d_program_init = datetime.now(timezone.utc)
        self.errFlag = 0
        self.aorc_conus_source = "s3://noaa-nws-aorc-v1-1-1km"
        self.aorc_conus_year_url = "{source}/{year}.zarr"
        self.aorc_alaska_source = "s3://ngwpc-data/AORC/Alaska"
        self.aorc_alaska_url = (
            "{source}/{year}/{year}{month:02d}/AK_AORC-OWP_{date}.nc4"
        )
        self.nwm_source = "s3://noaa-nwm-retrospective-3-0-pds"
        self._geogrid = geogrid
        self.broadcast_new_64bit_uid()

        self._scratch_dir_has_been_uniquefied = False

        # set list of attibutes from consts.py to None.
        # These are indexed from the consts dictionary using the class name
        for attr in CONFIGOPTIONS[self.__class__.__name__]:
            setattr(self, attr, None)
        self._validate_config()

    @property
    def cfg_bmi(self) -> dict:
        """Return the configuration dictionary read in from the configuration file specified by the user."""
        return self._cfg_bmi

    @cfg_bmi.setter
    def cfg_bmi(self, value: dict) -> None:
        """Set the configuration dictionary read in from the configuration file specified by the user."""
        if not isinstance(value, dict):
            raise TypeError(
                f"Expected dict, got {type(value)} for type of cfg_bmi: {value}"
            )
        self._validate_config()
        self._cfg_bmi = value

    @property
    def force_count(self) -> int:
        """Calculate the number of total possible input forcing options based on the length of the InputForcings list in the consts.py file. This is used for error checking to ensure users specify valid input forcing options in the configuration file."""
        return len(FORCINGINPUTMOD["InputForcings"]["PRODUCT_NAME"])

    @property
    def supp_precip_count(self) -> int:
        """Calculate the number of total possible supplemental precip forcing options based on the length of the SuppPrecipForcings list in the consts.py file. This is used for error checking to ensure users specify valid supplemental precip forcing options in the configuration file."""
        # TODO make this dynamic based on the length of the SUPPPRECIPMOD list in consts.py, but for now hardcoding to 15 since that is the number of options currently available in consts.py and this will avoid any issues with the formatting of the consts.py file causing errors in the program. This is used for error checking to ensure users specify valid supplemental precip forcing options in the configuration file.
        # return len(SUPPPRECIPMOD["suppPrecipMod"]["PRODUCT_NAMES"])
        return 15

    @property
    def number_supp_pcp(self) -> int:
        """Calculate the number of supplemental precip forcings specified by the user in the configuration file."""
        return len(self.supp_precip_forcings)

    @property
    def precip_only_flag(self) -> bool:
        """Flag to indicate whether the user has chosen to run the supplemental precip forcings module only, which will trigger some different processing pathways and error checking for certain configuration options."""
        if self.number_supp_pcp == 1:
            if int(self.supp_precip_forcings[0]) == 14:
                return True

    def set_attrs(self):
        """Set the attributes of the class based on the configuration file. This is used to populate the attributes of the class after they have been read in and validated from the configuration file."""
        for cfg_bmi_attr, config_options_attr in CONFIGOPTIONS[
            "cfg_bmi_to_attrs_map"
        ].items():
            setattr(
                self, config_options_attr, self.extract_input_variable(cfg_bmi_attr)
            )

        if self.output_freq <= 0:
            err_out_screen(
                "Please specify an OutputFrequency that is greater than zero minutes."
            )

    def extract_input_variable(self, variable_name: str) -> str:
        """Extract the variable name from the configuration file for a given variable."""
        try:
            return self.cfg_bmi[variable_name]
        except ValueError as e:
            err_out_screen(
                f"Improper {variable_name} value specified  in the configuration file. Error: {e}"
            )
        except (KeyError, configparser.NoOptionError) as e:
            err_out_screen(
                f"Unable to locate {variable_name} in the configuration file. Error: {e}"
            )
        except json.decoder.JSONDecodeError as e:
            err_out_screen(
                f"Improper {variable_name} file option specified in configuration file. Error: {e}",
                e,
            )

    def extract_input_variable_set_default(self, variable_name: str, default=0) -> str:
        """Extract the variable name from the configuration file for a given variable, and set it to a default value if it is not found."""
        try:
            variable = self.cfg_bmi[variable_name]
        except (KeyError, configparser.NoOptionError) as e:
            variable = default
        except ValueError as e:
            err_out_screen(
                f"Improper {variable_name} value: {self.cfg_bmi[variable_name]}", e
            )
        if variable not in [0, 1]:
            err_out_screen(f"Please choose a {variable_name} value of 0  or 1.")
        return variable

    def try_config_get(self, variable_name: str, default=None) -> str:
        """Try to get a variable from the configuration file, and return a default value if it is not found."""
        try:
            var = self.cfg_bmi.get(variable_name, default)
            if var is None:
                err_out_screen(
                    f"Unable to locate {variable_name} in the configuration file."
                )
            return var
        except (KeyError, configparser.NoOptionError) as e:
            err_out_screen(
                f"Unable to locate {variable_name} in the configuration file.", e
            )

    def check_number_of_inputs(
        self, value: list, variable_name: str, input_type: str
    ) -> None:
        """Check that the number of inputs specified by the user in the configuration file matches the expected number of inputs for a given variable."""
        if len(value) != self.number_inputs:
            err_out_screen(
                f"Number of {variable_name} values must match the number of {input_type} in the configuration file."
            )

    def check_number_of_inputs_forcings(self, value: list, variable_name: str) -> None:
        """Check that the number of inputs specified by the user in the configuration file matches the expected number of inputs for a given variable, specifically for input forcings variables which should match the number of input forcing options specified by the user in the configuration file."""
        return self.check_number_of_inputs(value, variable_name, " InputForcings")

    def check_number_of_inputs_supp_pcp(self, value: list, variable_name: str) -> None:
        """Check that the number of inputs specified by the user in the configuration file matches the expected number of inputs for a given variable, specifically for supplemental precip forcing variables which should match the number of supplemental precip forcing options specified by the user in the configuration file."""
        return self.check_number_of_inputs(
            value, variable_name, " supplemental precip forcings"
        )

    def check_input_values_in_range(
        self, value: list, variable_name: str, valid_input_options: list
    ) -> None:
        """Check that the input values specified by the user in the configuration file are within a valid range for a given variable."""
        for val in value:
            if val in valid_input_options:
                err_out_screen(
                    f"Invalid {variable_name} value '{val}' specified in configuration file. Please specify valid values: {valid_input_options}."
                )

    def check_input_values_positive(self, value: list, variable_name: str) -> None:
        """Check that the input values specified by the user in the configuration file are positive for a given variable."""
        for val in value:
            if val <= 0:
                err_out_screen(
                    f"Invalid {variable_name} value '{val}' specified in configuration file. Please specify values greater than zero."
                )

    def uniquefy_scratch_dir_as_child(self, uid: str) -> None:
        """Modify the existing scratch dir by adding the UID string available to all ranks from the MpiConfig class.

        This may only be called once. Subsequent calls will result in an error.
        This must be called by all ranks, once.
        """
        LOG.debug(f"Uniquefying scratch dir: adding suffix {uid} to {self.scratch_dir}")
        if not isinstance(uid, str):
            raise TypeError(f"Expected str, got {type(uid)} for type of uid: {uid}")
        if self.scratch_dir is None:
            raise ValueError("This cannot be ran while scratch_dir is None")
        if self._scratch_dir_has_been_uniquefied is True:
            raise ValueError(
                f"scratch_dir path has already been uniquefied: {self.scratch_dir}"
            )
        self.scratch_dir = os.path.join(self.scratch_dir, uid)
        self._scratch_dir_has_been_uniquefied = True
        self.make_scratch_dir()

    def make_scratch_dir(self) -> None:
        """Make the scratch dir and its parents."""
        os.makedirs(self.scratch_dir, exist_ok=True)
        LOG.debug(f"Scratch dir: {self.scratch_dir}")

    def broadcast_new_64bit_uid(self) -> None:
        """Broadcast a random uint64 then save the hash of that to self.uid64, which effectively broadcasts the same unique string to all ranks.

        Should be called once to avoid confusion.
        """
        if self.uid64 is not None:
            raise RuntimeError("self.uid64 has already been initialized.")
        self.uid64 = mpi_utils.get_new_broadcasted_uid()

    @property
    def b_date_proc(self) -> str:
        """Get the beginning date of processing for reforecast simulations. This is used to calculate the processing window for reforecast simulations, and is only necessary if the user is running a reforecast simulation with a specified processing window rather than a realtime simulation."""
        return self._bdate_proc

    @b_date_proc.setter
    def b_date_proc(self, value: str | datetime) -> None:
        """Set the beginning date of processing for reforecast simulations. This is used to calculate the processing window for reforecast simulations, and is only necessary if the user is running a reforecast simulation with a specified processing window rather than a realtime simulation."""
        if value is None:
            value = self.try_config_get("RefcstBDateProc")
        if isinstance(value, datetime):
            self._b_date_proc = value
        if value != -9999:
            if isinstance(value, str) and len(value) != 12:
                err_out_screen(
                    "Improper RefcstBDateProc length entered into the configuration file. Please check your entry."
                )
            try:
                self._b_date_proc = datetime.strptime(value, "%Y%m%d%H%M")
            except ValueError as e:
                err_out_screen(
                    "Improper RefcstBDateProc value entered into the configuration file. Please check your entry.",
                    e,
                )
        else:
            self._b_date_proc = -9999
        LOG.info(f"Begin date: {value}")

    @property
    def realtime_flag(self) -> bool:
        """Flag to indicate whether the user has chosen to run a realtime simulation, which will trigger some different processing pathways and error checking for certain configuration options, and will also control how the processing window is calculated."""
        if self.look_back == -9999:
            return False
        elif self.b_date_proc == -9999:
            return True
        else:
            return False

    @property
    def refcst_flag(self) -> bool:
        """Flag to indicate whether the user has chosen to run a reforecast simulation, which will trigger some different processing pathways and error checking for certain configuration options, and will also control how the processing window is calculated."""
        if self.look_back == -9999:
            return True
        elif self.b_date_proc == -9999:
            return True
        else:
            return False

    @property
    def geopackage(self) -> str:
        """Get the pathway to the geopackage file to be used for processing. This is used to specify the grid information for regridding input forcings, and is only necessary if the user is running a simulation that requires regridding of input forcings."""
        return self._geopackage

    @geopackage.setter
    def geopackage(self, value: str) -> None:
        """Set the pathway to the geopackage file to be used for processing. This is used to specify the grid information for regridding input forcings, and is only necessary if the user is running a simulation that requires regridding of input forcings."""
        if value is not None:
            self._geopackage = value
        else:
            self._geopackage = self.try_config_get("Geopackage")

    @property
    def geogrid(self) -> str:
        """Get the pathway to the geogrid file to be used for processing. This is used to specify the grid information for regridding input forcings, and is only necessary if the user is running a simulation that requires regridding of input forcings."""
        return self._geogrid

    @geogrid.setter
    def geogrid(self, value: str) -> None:
        """Set the pathway to the geogrid file to be used for processing. This is used to specify the grid information for regridding input forcings, and is only necessary if the user is running a simulation that requires regridding of input forcings."""
        if value is not None:
            self._geogrid = value
        else:
            geogrid_base = self.try_config_get("GeogridIn")
            if geogrid_base is None:
                err_out_screen("Unable to locate GeogridIn in the configuration file.")
                self.geogrid = None
            else:
                geogrid_parent = os.path.dirname(geogrid_base)
                geogrid_filename = os.path.basename(geogrid_base)
                if self.uid64 is None:
                    raise ValueError("self.uid64 cannot be None, please initialize it.")
                self._geogrid = os.path.join(
                    geogrid_parent, f"{self.uid64}_{geogrid_filename}"
                )
        self.try_make_dir(geogrid_parent, " esmf_mesh")

    def try_make_dir(self, directory: str, optional_str: str = "") -> None:
        """Try to make a directory, and catch any errors."""
        if not os.path.isdir(directory):
            try:
                os.makedirs(directory, exist_ok=True)
                LOG.debug(f"Created{optional_str} directory: {directory}")
            except OSError as e:
                err_out_screen(
                    f"Unable to create{optional_str} directory: {directory}. Error: {e}"
                )

    @property
    def input_forcing_options(self) -> list:
        """Get the list of input forcing options specified by the user in the configuration file. This is used to control which input forcings are processed and how they are processed based on the other configuration options specified for each input forcing."""
        return self._input_forcing_options

    @input_forcing_options.setter
    def input_forcing_options(self, value: list) -> None:
        """Set the list of input forcing options specified by the user in the configuration file. This is used to control which input forcings are processed and how they are processed based on the other configuration options specified for each input forcing."""
        if value is None and not self.precip_only_flag:
            value = self.extract_input_variable("InputForcings")
        if not self.precip_only_flag:
            for force_opt in value:
                self.check_input_values_in_range(
                    value, "InputForcings", list(range(1, self.force_count + 1))
                )
            self._input_forcing_options = value

    @property
    def number_inputs(self) -> int:
        """Calculate the number of input forcing options specified by the user in the configuration file. This is used for error checking to ensure users specify valid input forcing options in the configuration file, and to control the flow of the program based on how many input forcings are being processed."""
        if not self.precip_only_flag:
            if len(self.input_forcings) == 0:
                err_out_screen(
                    "Please choose at least one InputForcings dataset to process"
                )
            return len(self.input_forcing_options)

    @property
    def number_custom_inputs(self) -> int:
        """Calculate the number of custom input forcing options specified by the user in the configuration file. This is used to control the flow of the program based on how many custom input forcings are being processed, since custom input forcings require some different processing pathways."""
        if not self.precip_only_flag:
            count = 0
            for force_opt in self.input_forcing_options:
                if force_opt == 10:
                    count += 1
            return count

    @property
    def nwm_geogrid(self) -> str:
        """Get the pathway to the NWM geogrid file specified by the user in the configuration file. This is used to specify the grid information for regridding NWM input forcings, and is only necessary if the user has chosen to regrid NWM input forcings in the configuration file."""
        return self._nwm_geogrid

    @nwm_geogrid.setter
    def nwm_geogrid(self, value: str) -> None:
        """Set the pathway to the NWM geogrid file specified by the user in the configuration file. This is used to specify the grid information for regridding NWM input forcings, and is only necessary if the user has chosen to regrid NWM input forcings in the configuration file."""
        if value is None and not self.precip_only_flag:
            if 27 in self.input_forcing_options:
                value = self.extract_input_variable("NWM_Geogrid")
        self._nwm_geogrid = value

    @property
    def input_force_types(self) -> list:
        """Get the list of input forcing file types specified by the user in the configuration file. This is used to control how input forcings are read in and processed based on the file type specified for each input forcing in the configuration file."""
        return self._input_force_types

    @input_force_types.setter
    def input_force_types(self, value: list) -> None:
        """Set the list of input forcing file types specified by the user in the configuration file. This is used to control how input forcings are read in and processed based on the file type specified for each input forcing in the configuration file."""
        if value is None and not self.precip_only_flag:
            value = self.extract_input_variable("InputForcingTypes")
        if not self.precip_only_flag:
            if value == [""]:
                value = []
            self.check_number_of_inputs_forcings(value, "InputForcingTypes")
            self.check_input_values_in_range(
                value, "InputForcingTypes", self.file_types
            )
            self._input_force_types = value

    @property
    def file_types(self):
        """Get the list of input forcing file types specified by the user in the configuration file. This is used to control how input forcings are read in and processed based on the file type specified for each input forcing in the configuration file."""
        return self.CONFIGOPTIONS["file_types"]

    @property
    def input_force_dirs(self) -> list:
        """Get the list of input forcing directories specified by the user in the configuration file. This is used to control where input forcings are read in from for each input forcing specified by the user in the configuration file."""
        return self._input_force_dirs

    @input_force_dirs.setter
    def input_force_dirs(self, value: list) -> None:
        """Set the list of input forcing directories specified by the user in the configuration file. This is used to control where input forcings are read in from for each input forcing specified by the user in the configuration file."""
        if value is None and not self.precip_only_flag:
            value = self.extract_input_variable("InputForcingDirectories")
        if not self.precip_only_flag:
            self.check_number_of_inputs_forcings(value, "InputForcingDirectories")
            # Loop through and ensure all input directories exist. Also strip out any whitespace
            # or new line characters.
            for dir_tmp in range(0, len(value)):
                value[dir_tmp] = value[dir_tmp].strip()
                dir_path = value[dir_tmp]
                forcing_type = self.input_forcing_options[dir_tmp]
                is_aws_forcing = forcing_type in [12, 21, 27]

                if not os.path.isdir(dir_path):
                    if is_aws_forcing:
                        self.aws = True
                    else:
                        self.try_make_dir(dir_path, " forcing")
            self._input_force_dirs = value

    def input_force_mandatory(self) -> list:
        """Get the list of input forcing mandatory flags specified by the user in the configuration file. This is used to control whether the program should raise an error if input forcings for a given forecast cycle are not found for each input forcing specified by the user in the configuration file."""
        return self._input_force_mandatory

    @input_force_mandatory.setter
    def input_force_mandatory(self, value: list) -> None:
        """Set the list of input forcing mandatory flags specified by the user in the configuration file. This is used to control whether the program should raise an error if input forcings for a given forecast cycle are not found for each input forcing specified by the user in the configuration file."""
        if value is None and not self.precip_only_flag:
            value = self.extract_input_variable("InputMandatory")
            self.check_number_of_inputs_forcings(value, "InputMandatory")
            self.check_input_values_in_range(value, "InputMandatory", [0, 1])
        self._input_force_mandatory = value

    def customSuppPcpFreq(self) -> int:
        """Get the custom supplemental precip output frequency specified by the user in the configuration file. This is used to control the output frequency of supplemental precip forcings if the user has chosen to run the supplemental precip forcings module only."""
        return self._customSuppPcpFreq

    @customSuppPcpFreq.setter
    def customSuppPcpFreq(self, value: int) -> None:
        """Set the custom supplemental precip output frequency specified by the user in the configuration file. This is used to control the output frequency of supplemental precip forcings if the user has chosen to run the supplemental precip forcings module only."""
        if value is None and self.precip_only_flag:
            value = self.extract_input_variable("customSuppPcpFreq")
            self.check_input_values_positive([value], "customSuppPcpFreq")
        self._customSuppPcpFreq = value

    @property
    def include_lqfrac(self):
        """Get the flag for whether to include the liquid/solid precipitation fraction variable in the output files specified by the user in the configuration file. This is used to control whether the liquid/solid precipitation fraction variable is included in the output files."""
        return self._include_lqfrac

    @include_lqfrac.setter
    def include_lqfrac(self, value):
        """Set the flag for whether to include the liquid/solid precipitation fraction variable in the output files specified by the user in the configuration file. This is used to control whether the liquid/solid precipitation fraction variable is included in the output files."""
        if value is None:
            value = self.extract_input_variable_set_default("includeLQFrac", default=0)

    @property
    def include_lqfrac(self):
        """Get the flag for whether to include the liquid/solid precipitation fraction variable in the output files specified by the user in the configuration file. This is used to control whether the liquid/solid precipitation fraction variable is included in the output files."""
        return self._include_lqfrac

    @include_lqfrac.setter
    def include_lqfrac(self, value):
        if value is None:
            value = self.extract_input_variable_set_default("includeLQFrac", default=0)
        self._include_lqfrac = value

    @property
    def forcing_output(self) -> int:
        """Get the flag for whether to output the input forcings specified by the user in the configuration file. This is used to control whether the input forcings are output in addition to the processed forcings."""
        return self._forcing_output

    @forcing_output.setter
    def forcing_output(self, value: int) -> None:
        if value is None:
            value = self.extract_input_variable_set_default("Output", default=0)
        self._forcing_output = value

    def fcst_shift(self) -> int:
        """Get the forecast shift specified by the user in the configuration file. This is used to control the calculation of the processing window for realtime simulations."""
        return self._fcst_shift

    @fcst_shift.setter
    def fcst_shift(self, value: int) -> None:
        if value is None:
            value = self.extract_input_variable("ForecastShift")
        self.check_input_values_positive([value], "ForecastShift")
        self._fcst_shift = value

    @property
    def fcst_input_horizons(self) -> list:
        """Get the list of forecast input horizons specified by the user in the configuration file. This is used to control the calculation of the forecast cycle length and the processing of input forcings based on the forecast time horizons specified for each input forcing."""
        return self._fcst_input_horizons

    @fcst_input_horizons.setter
    def fcst_input_horizons(self, value: list) -> None:
        if value is None and not self.precip_only_flag:
            value = self.extract_input_variable("ForecastInputHorizons")
        if not self.precip_only_flag:
            self.check_number_of_inputs_forcings(value, "ForecastInputHorizons")
            self.check_input_values_positive(value, "ForecastInputHorizons")
        else:
            if value is None:
                value = self.extract_input_variable("ForecastInputHorizons")
        self._fcst_input_horizons = value

    @property
    def fcst_input_offsets(self):
        """Get the list of forecast input offsets specified by the user in the configuration file. This is used to control the calculation of the processing window for both realtime and reforecast simulations based on the forecast time horizons and input offsets specified for each input forcing."""
        return self._fcst_input_offsets

    @fcst_input_offsets.setter
    def fcst_input_offsets(self, value: list) -> None:
        if value is None and not self.precip_only_flag:
            value = self.extract_input_variable("ForecastInputOffsets")
        if not self.precip_only_flag:
            self.check_number_of_inputs_forcings(value, "ForecastInputOffsets")
            self.check_input_values_positive(value, "ForecastInputOffsets")
            self._fcst_input_offsets = value

    @property
    def cycle_length_minutes(self) -> int:
        """Get the forecast cycle length in minutes, which is calculated based on the maximum of the forecast input horizons specified by the user in the configuration file.

        Ensure the number maximum cycle length is an equal divider of the output time step specified by the user.
        """
        cycle_len = max(self.fcst_input_horizons)
        if cycle_len % self.output_freq != 0:
            err_out_screen(
                "Please specify an output time step that is an equal divider of the maximum of the forecast time horizons specified."
            )
        return cycle_len

    def num_output_steps(self) -> int:
        """Calculate the number of output time steps per forecast cycle based on the forecast cycle length and the output frequency specified by the user in the configuration file."""
        if self.sub_output_hour is None:
            num_steps = int(self.cycle_length_minutes / self.output_freq)
        else:
            num_steps = (
                int(
                    (self.cycle_length_minutes - (self.sub_output_hour * 60))
                    / self.sub_output_freq
                )
                + int((self.sub_output_hour * 60) / self.output_freq)
                - 1
            )
        return num_steps

    def num_supp_output_steps(self) -> int:
        """Calculate the number of supplemental precip output time steps per forecast cycle based on the forecast cycle length and the custom supplemental precip output frequency specified by the user in the configuration file."""
        if self.precip_only_flag:
            return int(self.cycle_length_minutes / self.customSuppPcpFreq)

    def actual_output_steps(self) -> int:
        """Calculate the actual number of output time steps per forecast cycle based on whether the user has chosen to run a reforecast simulation with a specified processing window, which will only output time steps for which input forcings are available based on the processing window and forecast time horizons specified by the user in the configuration file."""
        if self.ana_flag:
            return np.int32(self.nFcsts)
        else:
            return np.int32(self.num_output_steps)

    @property
    def grid_type(self) -> str:
        """Get the grid type specified by the user in the configuration file. This is used to control how the program reads in and processes the geogrid information for regridding input forcings based on the grid type specified by the user in the configuration file."""
        return self._grid_type

    @grid_type.setter
    def grid_type(self, value: str) -> None:
        """Set the grid type specified by the user in the configuration file. This is used to control how the program reads in and processes the geogrid information for regridding input forcings based on the grid type specified by the user in the configuration file."""
        if value is None:
            value = self.extract_input_variable("GRID_TYPE")
        self.check_input_values_in_range(
            [value], "GRID_TYPE", ["gridded", "unstructured", "hydrofabric"]
        )
        self._grid_type = value.lower()

    def raise_grid_type_error(self, grid_type: str, variable_name: str) -> None:
        """Raise an error if a variable is requested that is not valid for the given grid type."""
        err_out_screen(
            f"{variable_name} is not a valid variable for grid type {grid_type}. Please check your configuration file."
        )

    @property
    def lon_var(self) -> str:
        """Get the longitude variable name specified by the user in the configuration file. This is used to control how the program reads in and processes the geogrid information for regridding input forcings if the user has chosen a gridded grid type in the configuration file."""
        if self.grid_type == "gridded":
            return self.extract_input_variable("LONVAR")
        else:
            self.raise_grid_type_error(self.grid_type, "LONVAR")

    @property
    def lat_var(self) -> str:
        """Get the latitude variable name specified by the user in the configuration file. This is used to control how the program reads in and processes the geogrid information for regridding input forcings if the user has chosen a gridded grid type in the configuration file."""
        if self.grid_type == "gridded":
            return self.extract_input_variable("LATVAR")
        else:
            self.raise_grid_type_error(self.grid_type, "LATVAR")

    @property
    def nodecoords_var(self) -> str:
        """Get the node coordinates variable name specified by the user in the configuration file. This is used to control how the program reads in and processes the geogrid information for regridding input forcings if the user has chosen an unstructured or hydrofabric grid type in the configuration file."""
        if self.grid_type in ["unstructured", "hydrofabric"]:
            return self.extract_input_variable("NodeCoords")
        else:
            self.raise_grid_type_error(self.grid_type, "NodeCoords")

    @property
    def elemcoords_var(self) -> str:
        """Get the element coordinates variable name specified by the user in the configuration file. This is used to control how the program reads in and processes the geogrid information for regridding input forcings if the user has chosen an unstructured or hydrofabric grid type in the configuration file."""
        if self.grid_type in ["unstructured", "hydrofabric"]:
            return self.extract_input_variable("ElemCoords")
        else:
            self.raise_grid_type_error(self.grid_type, "ElemCoords")

    @property
    def elemconn_var(self) -> str:
        """Get the element connectivity variable name specified by the user in the configuration file. This is used to control how the program reads in and processes the geogrid information for regridding input forcings if the user has chosen an unstructured or hydrofabric grid type in the configuration file."""
        if self.grid_type in ["unstructured", "hydrofabric"]:
            return self.extract_input_variable("ElemConn")
        else:
            self.raise_grid_type_error(self.grid_type, "ElemConn")

    @property
    def numelemconn_var(self) -> str:
        """Get the number of element connectivity variable name specified by the user in the configuration file. This is used to control how the program reads in and processes the geogrid information for regridding input forcings if the user has chosen an unstructured or hydrofabric grid type in the configuration file."""
        if self.grid_type in ["unstructured", "hydrofabric"]:
            return self.extract_input_variable("NumElemConn")
        else:
            self.raise_grid_type_error(self.grid_type, "NumElemConn")

    @property
    def element_id_var(self) -> str:
        """Get the element ID variable name specified by the user in the configuration file. This is used to control how the program reads in and processes the geogrid information for regridding input forcings if the user has chosen a hydrofabric grid type in the configuration file."""
        if self.grid_type == "hydrofabric":
            return self.extract_input_variable("ElemID")
        else:
            self.raise_grid_type_error(self.grid_type, "ElemID")

    @property
    def ignored_border_widths(self) -> list:
        """Get the list of ignored border widths specified by the user in the configuration file. This is used to control how the program processes input forcings based on the ignored border widths specified for each input forcing in the configuration file."""
        return self._ignored_border_widths

    @ignored_border_widths.setter
    def ignored_border_widths(self, value: list) -> None:
        """Set the list of ignored border widths specified by the user in the configuration file. This is used to control how the program processes input forcings based on the ignored border widths specified for each input forcing in the configuration file."""
        if value is None and not self.precip_only_flag:
            value = self.extract_input_variable("IgnoredBorderWidths")
        if self.precip_only_flag:
            self.check_number_of_inputs_forcings(value, "IgnoredBorderWidths")
            self.check_input_values_positive(value, "IgnoredBorderWidths")
            self._ignored_border_widths = value

    @property
    def regrid_opt(self):
        """Get the list of regridding options specified by the user in the configuration file. This is used to control how input forcings are regridded based on the regridding option specified for each input forcing in the configuration file."""
        return self._regrid_opt

    @regrid_opt.setter
    def regrid_opt(self, value: list) -> None:
        """Set the list of regridding options specified by the user in the configuration file. This is used to control how input forcings are regridded based on the regridding option specified for each input forcing in the configuration file."""
        if value is None and not self.precip_only_flag:
            value = self.extract_input_variable("RegridOpt")
        if self.precip_only_flag:
            self.check_number_of_inputs_forcings(value, "RegridOpt")
            self.check_input_values_in_range(value, "RegridOpt", [1, 2, 3])
            self._regrid_opt = value

    @property
    def weightsDir(self) -> str:
        """Get the pathway to the ESMF weights directory specified by the user in the configuration file. This is used to control where the program looks for ESMF weights files if the user has chosen to use pre-generated ESMF weights files for regridding input forcings in the configuration file."""
        return self._weightsDir

    @weightsDir.setter
    def weightsDir(self, value: str) -> None:
        """Set the pathway to the ESMF weights directory specified by the user in the configuration file. This is used to control where the program looks for ESMF weights files if the user has chosen to use pre-generated ESMF weights files for regridding input forcings in the configuration file."""
        if value is None and not self.precip_only_flag:
            value = self.try_config_get("RegridWeightsDir")
        if self.precip_only_flag:
            if value is not None and not os.path.exists(value):
                err_out_screen(
                    f"ESMF Weights file directory specified ({value}) but does not exist"
                )
            self._weightsDir = value

    @property
    def forceTemoralInterp(self) -> list:
        """Get the list of forcing temporal interpolation options specified by the user in the configuration file. This is used to control how input forcings are temporally interpolated based on the temporal interpolation option specified for each input forcing in the configuration file."""
        return self._forceTemoralInterp

    @forceTemoralInterp.setter
    def forceTemoralInterp(self, value: list) -> None:
        """Set the list of forcing temporal interpolation options specified by the user in the configuration file. This is used to control how input forcings are temporally interpolated based on the temporal interpolation option specified for each input forcing in the configuration file."""
        if value is None and not self.precip_only_flag:
            value = self.extract_input_variable("ForcingTemporalInterpolation")
        if not self.precip_only_flag:
            self.check_number_of_inputs_forcings(value, "ForcingTemporalInterpolation")
            self.check_input_values_in_range(
                value, "ForcingTemporalInterpolation", [0, 1, 2]
            )
            self._forceTemoralInterp = value

    @property
    def forceTemoralInterp(self):
        """Get the list of forcing temporal interpolation options specified by the user in the configuration file. This is used to control how input forcings are temporally interpolated based on the temporal interpolation option specified for each input forcing in the configuration file."""
        return self._forceTemoralInterp

    @forceTemoralInterp.setter
    def forceTemoralInterp(self, value):
        """Set the list of forcing temporal interpolation options specified by the user in the configuration file. This is used to control how input forcings are temporally interpolated based on the temporal interpolation option specified for each input forcing in the configuration file."""
        if value is None and not self.precip_only_flag:
            value = self.extract_input_variable("ForcingTemporalInterpolation")
        if not self.precip_only_flag:
            self.check_number_of_inputs_forcings(value, "ForcingTemporalInterpolation")
            self.check_input_values_in_range(
                value, "ForcingTemporalInterpolation", [0, 1, 2]
            )
            self._forceTemoralInterp = value

    @property
    def t2dDownscaleOpt(self) -> list:
        """Get the list of temperature downscaling options specified by the user in the configuration file. This is used to control how temperature input forcings are downscaled based on the temperature downscaling option specified for each input forcing in the configuration file."""
        return self._t2dDownscaleOpt

    @t2dDownscaleOpt.setter
    def t2dDownscaleOpt(self, value: list) -> None:
        """Set the list of temperature downscaling options specified by the user in the configuration file. This is used to control how temperature input forcings are downscaled based on the temperature downscaling option specified for each input forcing in the configuration file."""
        if value is None and not self.precip_only_flag:
            value = self.extract_input_variable("TemperatureDownscaling")
        if not self.precip_only_flag:
            self.check_number_of_inputs_forcings(value, "TemperatureDownscaling")
            self.check_input_values_in_range(value, "TemperatureDownscaling", [0, 1, 2])
            self._t2dDownscaleOpt = value

    @property
    def psfcDownscaleOpt(self) -> list:
        """Get the list of pressure downscaling options specified by the user in the configuration file. This is used to control how pressure input forcings are downscaled based on the pressure downscaling option specified for each input forcing in the configuration file."""
        return self._psfcDownscaleOpt

    @psfcDownscaleOpt.setter
    def psfcDownscaleOpt(self, value: list) -> None:
        """Set the list of pressure downscaling options specified by the user in the configuration file. This is used to control how pressure input forcings are downscaled based on the pressure downscaling option specified for each input forcing in the configuration file."""
        if value is None and not self.precip_only_flag:
            value = self.extract_input_variable("PressureDownscaling")
        if not self.precip_only_flag:
            self.check_number_of_inputs_forcings(value, "PressureDownscaling")
            self.check_input_values_in_range(value, "PressureDownscaling", [0, 1])
            self._psfcDownscaleOpt = value

    @property
    def swDownscaleOpt(self) -> list:
        """Get the list of shortwave downscaling options specified by the user in the configuration file. This is used to control how shortwave radiation input forcings are downscaled based on the shortwave downscaling option specified for each input forcing in the configuration file."""
        return self._swDownscaleOpt

    @swDownscaleOpt.setter
    def swDownscaleOpt(self, value: list) -> None:
        """Set the list of shortwave downscaling options specified by the user in the configuration file. This is used to control how shortwave radiation input forcings are downscaled based on the shortwave downscaling option specified for each input forcing in the configuration file."""
        if value is None and not self.precip_only_flag:
            value = self.extract_input_variable("ShortwaveDownscaling")
        if not self.precip_only_flag:
            self.check_number_of_inputs_forcings(value, "ShortwaveDownscaling")
            self.check_input_values_in_range(value, "ShortwaveDownscaling", [0, 1])
            self._swDownscaleOpt = value

    @property
    def q2dDownscaleOpt(self) -> list:
        """Get the list of humidity downscaling options specified by the user in the configuration file. This is used to control how humidity input forcings are downscaled based on the humidity downscaling option specified for each input forcing in the configuration file."""
        return self._q2dDownscaleOpt

    @q2dDownscaleOpt.setter
    def q2dDownscaleOpt(self, value: list) -> None:
        """Set the list of humidity downscaling options specified by the user in the configuration file. This is used to control how humidity input forcings are downscaled based on the humidity downscaling option specified for each input forcing in the configuration file."""
        if value is None and not self.precip_only_flag:
            value = self.extract_input_variable("HumidityDownscaling")
        if not self.precip_only_flag:
            self.check_number_of_inputs_forcings(value, "HumidityDownscaling")
            self.check_input_values_in_range(value, "HumidityDownscaling", [0, 1])
            self._q2dDownscaleOpt = value

    @property
    def precipDownscaleOpt(self) -> list:
        """Get the list of precipitation downscaling options specified by the user in the configuration file. This is used to control how precipitation input forcings are downscaled based on the precipitation downscaling option specified for each input forcing in the configuration file."""
        return self._precipDownscaleOpt

    @precipDownscaleOpt.setter
    def precipDownscaleOpt(self, value: list) -> None:
        """Set the list of precipitation downscaling options specified by the user in the configuration file. This is used to control how precipitation input forcings are downscaled based on the precipitation downscaling option specified for each input forcing in the configuration file."""
        if value is None:
            value = self.extract_input_variable("PrecipDownscaling")
        self.check_number_of_inputs_forcings(value, "PrecipDownscaling")
        self.check_input_values_in_range(value, "PrecipDownscaling", [0, 1])

        self._precipDownscaleOpt = value

    @property
    def dScaleParamDirs(self) -> list:
        """Get the list of downscaling parameter directories specified by the user in the configuration file. This is used to control where the program looks for downscaling parameter files for each input forcing based on the downscaling parameter directory specified for each input forcing in the configuration file."""
        return self._dScaleParamDirs

    @dScaleParamDirs.setter
    def dScaleParamDirs(self, value: list) -> None:
        """Set the list of downscaling parameter directories specified by the user in the configuration file. This is used to control where the program looks for downscaling parameter files for each input forcing based on the downscaling parameter directory specified for each input forcing in the configuration file."""
        if value is None:
            value = self.extract_input_variable("DownscalingParamDirs")
        self.check_number_of_inputs_forcings(value, "DownscalingParamDirs")
        for dirTmp in range(0, len(value)):
            dir_path = value[dirTmp]
            if not os.path.isdir(dir_path):
                err_out_screen(
                    f"Unable to locate parameter directory: {os.path.abspath(dir_path)}"
                )
        self._dScaleParamDirs = value

    def perform_downscaling(self) -> bool:
        """Determine whether downscaling of input forcings is necessary based on the downscaling options specified by the user for each input forcing in the configuration file."""
        if (
            1 in self.q2dDownscaleOpt
            or 1 in self.swDownscaleOpt
            or 1 in self.psfcDownscaleOpt
            or 1 in self.t2dDownscaleOpt
            or 2 in self.t2dDownscaleOpt
        ):
            return True

    @property
    def sinalpha_var(self) -> str:
        """Get the sine of the grid orientation variable name specified by the user in the configuration file. This is used to control how the program reads in and processes the geogrid information for downscaling input forcings based on the grid orientation variable specified for each input forcing in the configuration file."""
        if self.perform_downscaling:
            return self.extract_input_variable("SINALPHA")

    @property
    def cosalpha_var(self) -> str:
        """Get the cosine of the grid orientation variable name specified by the user in the configuration file. This is used to control how the program reads in and processes the geogrid information for downscaling input forcings based on the grid orientation variable specified for each input forcing in the configuration file."""
        if self.perform_downscaling:
            return self.extract_input_variable("COSALPHA")

    @property
    def slope_var(self) -> str:
        """Get the slope variable name specified by the user in the configuration file. This is used to control how the program reads in and processes the geogrid information for downscaling input forcings based on the slope variable specified for each input forcing in the configuration file."""
        if self.perform_downscaling:
            return self.extract_input_variable("SLOPE")

    @property
    def slope_azimuth_var(self) -> str:
        """Get the slope azimuth variable name specified by the user in the configuration file. This is used to control how the program reads in and processes the geogrid information for downscaling input forcings based on the slope azimuth variable specified for each input forcing in the configuration file."""
        if self.perform_downscaling:
            return self.extract_input_variable("SLOPE_AZIMUTH")

    @property
    def slope_var_elem(self) -> str:
        """Get the slope variable name specified by the user in the configuration file for element-based grids. This is used to control how the program reads in and processes the geogrid information for downscaling input forcings based on the slope variable specified for each input forcing in the configuration file for element-based grids."""
        if self.perform_downscaling:
            if self.grid_type == "unstructured":
                return self.extract_input_variable("SLOPE_ELEM")
            else:
                self.raise_grid_type_error(self.grid_type, "SLOPE_ELEM")

    @property
    def slope_azimuth_var_elem(self) -> str:
        """Get the slope azimuth variable name specified by the user in the configuration file for element-based grids. This is used to control how the program reads in and processes the geogrid information for downscaling input forcings based on the slope azimuth variable specified for each input forcing in the configuration file for element-based grids."""
        if self.perform_downscaling:
            if self.grid_type == "unstructured":
                return self.extract_input_variable("SLOPE_AZIMUTH_ELEM")
            else:
                self.raise_grid_type_error(self.grid_type, "SLOPE_AZIMUTH_ELEM")

    @property
    def hgt_elem_var(self) -> str:
        """Get the height variable name specified by the user in the configuration file for element-based grids. This is used to control how the program reads in and processes the geogrid information for downscaling input forcings based on the height variable specified for each input forcing in the configuration file for element-based grids."""
        if self.perform_downscaling:
            if self.grid_type == "unstructured":
                return self.extract_input_variable("HGT_ELEM")
            else:
                self.raise_grid_type_error(self.grid_type, "HGT_ELEM")

    @property
    def hgt_var(self) -> str:
        """Get the height variable name specified by the user in the configuration file. This is used to control how the program reads in and processes the geogrid information for downscaling input forcings based on the height variable specified for each input forcing in the configuration file."""
        if self.perform_downscaling:
            return self.extract_input_variable("HGT")

    @property
    def t2BiasCorrectOpt(self) -> list:
        """Get the list of temperature bias correction options specified by the user in the configuration file. This is used to control how temperature input forcings are bias corrected based on the temperature bias correction option specified for each input forcing in the configuration file."""
        return self._t2BiasCorrectOpt

    @t2BiasCorrectOpt.setter
    def t2BiasCorrectOpt(self, value: list) -> None:
        """Set the list of temperature bias correction options specified by the user in the configuration file. This is used to control how temperature input forcings are bias corrected based on the temperature bias correction option specified for each input forcing in the configuration file."""
        if value is None and not self.precip_only_flag:
            value = self.extract_input_variable("TemperatureBiasCorrection")
        if not self.precip_only_flag:
            self.check_number_of_inputs_forcings(value, "TemperatureBiasCorrection")
            self.check_input_values_in_range(
                value, "TemperatureBiasCorrection", [0, 1, 2, 3, 4]
            )
            self._t2BiasCorrectOpt = value

    @property
    def psfcBiasCorrectOpt(self) -> list:
        """Get the list of pressure bias correction options specified by the user in the configuration file. This is used to control how pressure input forcings are bias corrected based on the pressure bias correction option specified for each input forcing in the configuration file."""
        return self._psfcBiasCorrectOpt

    @psfcBiasCorrectOpt.setter
    def psfcBiasCorrectOpt(self, value: list) -> None:
        """Set the list of pressure bias correction options specified by the user in the configuration file. This is used to control how pressure input forcings are bias corrected based on the pressure bias correction option specified for each input forcing in the configuration file."""
        if value is None and not self.precip_only_flag:
            value = self.extract_input_variable("PressureBiasCorrection")
        if not self.precip_only_flag:
            self.check_number_of_inputs_forcings(value, "PressureBiasCorrection")
            self.check_input_values_in_range(value, "PressureBiasCorrection", [0, 1])
            self._psfcBiasCorrectOpt = value

    @property
    def q2BiasCorrectOpt(self):
        """Get the list of humidity bias correction options specified by the user in the configuration file. This is used to control how humidity input forcings are bias corrected based on the humidity bias correction option specified for each input forcing in the configuration file."""
        return self._q2BiasCorrectOpt

    @q2BiasCorrectOpt.setter
    def q2BiasCorrectOpt(self, value):
        """Set the list of humidity bias correction options specified by the user in the configuration file. This is used to control how humidity input forcings are bias corrected based on the humidity bias correction option specified for each input forcing in the configuration file."""
        if value is None and not self.precip_only_flag:
            value = self.extract_input_variable("HumidityBiasCorrection")
        if not self.precip_only_flag:
            self.check_number_of_inputs_forcings(value, "HumidityBiasCorrection")
            self.check_input_values_in_range(value, "HumidityBiasCorrection", [0, 1, 2])
            self._q2BiasCorrectOpt = value

    @property
    def windBiasCorrect(self):
        """Get the list of wind bias correction options specified by the user in the configuration file. This is used to control how wind input forcings are bias corrected based on the wind bias correction option specified for each input forcing in the configuration file."""
        return self._windBiasCorrect

    @windBiasCorrect.setter
    def windBiasCorrect(self, value):
        """Set the list of wind bias correction options specified by the user in the configuration file. This is used to control how wind input forcings are bias corrected based on the wind bias correction option specified for each input forcing in the configuration file."""
        if value is None and not self.precip_only_flag:
            value = self.extract_input_variable("WindBiasCorrection")
        if not self.precip_only_flag:
            self.check_number_of_inputs_forcings(value, "WindBiasCorrection")
            self.check_input_values_in_range(value, "WindBiasCorrection", [0, 4])
            self._windBiasCorrect = value

    @property
    def swBiasCorrectOpt(self) -> list:
        """Get the list of shortwave radiation bias correction options specified by the user in the configuration file. This is used to control how shortwave radiation input forcings are bias corrected based on the shortwave radiation bias correction option specified for each input forcing in the configuration file."""
        return self._swBiasCorrectOpt

    @swBiasCorrectOpt.setter
    def swBiasCorrectOpt(self, value: list) -> None:
        """Set the list of shortwave radiation bias correction options specified by the user in the configuration file. This is used to control how shortwave radiation input forcings are bias corrected based on the shortwave radiation bias correction option specified for each input forcing in the configuration file."""
        if value is None and not self.precip_only_flag:
            value = self.extract_input_variable("ShortwaveBiasCorrection")
        if not self.precip_only_flag:
            self.check_number_of_inputs_forcings(value, "ShortwaveBiasCorrection")
            self.check_input_values_in_range(
                value, "ShortwaveBiasCorrection", [0, 1, 2]
            )
            self._swBiasCorrectOpt = value

    @property
    def lwBiasCorrectOpt(self) -> list:
        """Get the list of longwave radiation bias correction options specified by the user in the configuration file. This is used to control how longwave radiation input forcings are bias corrected based on the longwave radiation bias correction option specified for each input forcing in the configuration file."""
        return self._lwBiasCorrectOpt

    @lwBiasCorrectOpt.setter
    def lwBiasCorrectOpt(self, value: list) -> None:
        """Set the list of longwave radiation bias correction options specified by the user in the configuration file. This is used to control how longwave radiation input forcings are bias corrected based on the longwave radiation bias correction option specified for each input forcing in the configuration file."""
        if value is None and not self.precip_only_flag:
            value = self.extract_input_variable("LongwaveBiasCorrection")
        if not self.precip_only_flag:
            self.check_number_of_inputs_forcings(value, "LongwaveBiasCorrection")
            self.check_input_values_in_range(
                value, "LongwaveBiasCorrection", [0, 1, 2, 4]
            )
            self._lwBiasCorrectOpt = value

    @property
    def precipBiasCorrectOpt(self):
        """Get the list of precipitation bias correction options specified by the user in the configuration file. This is used to control how precipitation input forcings are bias corrected based on the precipitation bias correction option specified for each input forcing in the configuration file."""
        return self._precipBiasCorrectOpt

    @precipBiasCorrectOpt.setter
    def precipBiasCorrectOpt(self, value):
        """Set the list of precipitation bias correction options specified by the user in the configuration file. This is used to control how precipitation input forcings are bias corrected based on the precipitation bias correction option specified for each input forcing in the configuration file."""
        if value is None and not self.precip_only_flag:
            value = self.extract_input_variable("PrecipBiasCorrection")
        if not self.precip_only_flag:
            self.check_number_of_inputs_forcings(value, "PrecipBiasCorrection")
            self.check_input_values_in_range(value, "PrecipBiasCorrection", [0, 1])
            self._precipBiasCorrectOpt = value

    @property
    def bias_correction_properties(self) -> dict:
        """Get the dictionary of bias correction properties specified by the user in the configuration file. This is used to control how input forcings are bias corrected based on the bias correction options specified for each input forcing in the configuration file."""
        bias_correction_properties = {
            "surface temperature": self.t2BiasCorrectOpt,
            "surface pressure": self.psfcBiasCorrectOpt,
            "specific humidity": self.q2BiasCorrectOpt,
            "wind forcings": self.windBiasCorrect,
            "short-wave radiation": self.swBiasCorrectOpt,
            "long-wave radiation": self.lwBiasCorrectOpt,
            "Precipitation": self.precipBiasCorrectOpt,
        }
        return bias_correction_properties

    @property
    def runCfsNldasBiasCorrect(self) -> bool:
        """Get the flag for whether to run the NWM-specific bias correction of CFSv2 input forcings specified by the user in the configuration file. This is used to control whether the NWM-specific bias correction of CFSv2 input forcings is run based on whether the user has chosen to run this bias correction in the configuration file."""
        for optTmp in self.bias_correction_properties.values():
            if optTmp == 1:
                runCfsNldasBiasCorrect = True
                break
        if runCfsNldasBiasCorrect:
            for (
                bias_correct_name,
                bias_correct,
            ) in self.bias_correction_properties.items():
                if min(bias_correct) != 1 and max(bias_correct) != 1:
                    err_out_screen(
                        f"CFSv2-NLDAS NWM bias correction must be activated for {bias_correct_name} under this configuration."
                    )
                # Make sure we don't have any other forcings activated. This can only be ran for CFSv2.
                for opt_tmp in self.input_forcings:
                    if opt_tmp != 7:
                        err_out_screen(
                            "CFSv2-NLDAS NWM bias correction can only be used in CFSv2-only configurations"
                        )

    def number_supp_pcp(self) -> int:
        """Get the number of supplemental precipitation input forcings specified by the user in the configuration file. This is used to control how many supplemental precipitation input forcings are processed based on the number of supplemental precipitation input forcings specified in the configuration file."""
        return len(self.supp_precip_forcings)

    @property
    def supp_precip_file_types(self) -> list:
        """Get the list of supplemental precipitation input forcing file types specified by the user in the configuration file. This is used to control how supplemental precipitation input forcing files are read in and processed based on the file types specified for each supplemental precipitation input forcing in the configuration file."""
        return self._supp_precip_file_types

    @supp_precip_file_types.setter
    def supp_precip_file_types(self, value: list) -> None:
        """Set the list of supplemental precipitation input forcing file types specified by the user in the configuration file. This is used to control how supplemental precipitation input forcing files are read in and processed based on the file types specified for each supplemental precipitation input forcing in the configuration file."""
        if value is None:
            value = self.try_config_get("SuppPcpForcingTypes")
        if value is not None:
            value = [stype.strip() for stype in value]
        if value == [""]:
            value = []

        self.check_number_of_inputs_supp_pcp(value, "SuppPcpForcingTypes")
        self.check_input_values_in_range(
            value,
            "SuppPcpForcingTypes",
            self.supplemental_precip_file_type_options,
        )
        self._supp_precip_file_types = value

    @property
    def supplemental_precip_file_type_options(self) -> list:
        """Get the list of valid supplemental precipitation input forcing file types that can be specified by the user in the configuration file. This is used to control how supplemental precipitation input forcing files are read in and processed based on the file types specified for each supplemental precipitation input forcing in the configuration file."""
        return ["GRIB1", "GRIB2", "NETCDF"]

    @property
    def rqiMethod(self) -> list:
        """Get the list of radar quality index (RQI) thresholding methods specified by the user in the configuration file. This is used to control how radar-based supplemental precipitation input forcings are processed based on the RQI thresholding method specified for each radar-based supplemental precipitation input forcing in the configuration file."""
        if self.number_supp_pcp > 0:
            for suppOpt in self.supp_precip_forcings:
                # Read in RQI threshold to apply to radar products.
                if suppOpt in (1, 2, 7, 10, 11, 12):
                    rqiMethod = self.extract_input_variable("RqiMethod")

                    # Check that if we have more than one RqiMethod, it's the correct number
                    if type(rqiMethod) is list:
                        self.check_number_of_inputs_supp_pcp(rqiMethod, "RqiMethod")
                    elif type(rqiMethod) is int:
                        # Support 'classic' mode of single method
                        rqiMethod = [rqiMethod] * self.number_supp_pcp

                    # Make sure the RqiMethod(s) makes sense.
                    for method in rqiMethod:
                        self.check_input_values_in_range(method, "RqiMethod", [0, 1, 2])
            return rqiMethod

    @property
    def rqiThresh(self):
        """Get the radar quality index (RQI) threshold value specified by the user in the configuration file. This is used to control how radar-based supplemental precipitation input forcings are processed based on the RQI threshold value specified in the configuration file."""
        if self.number_supp_pcp > 0:
            for suppOpt in self.supp_precip_forcings:
                # Read in RQI threshold to apply to radar products.
                if suppOpt in (1, 2, 7, 10, 11, 12):
                    rqiThresh = self.extract_input_variable("RqiThresh")

                    # Check that if we have more than one RqiThresh, it's the correct number
                    if type(rqiThresh) is list:
                        self.check_number_of_inputs_supp_pcp(rqiThresh, "RqiThresh")
                    elif type(rqiThresh) is (int, float):
                        # Support 'classic' mode of single threshold
                        rqiThresh = [rqiThresh] * self.number_supp_pcp

                    # Make sure the RqiThresh(es) makes sense.
                    for threshold in self.rqiThresh:
                        if threshold < 0.0 or threshold > 1.0:
                            err_out_screen(
                                "Please specify RqiThresholds between 0.0 and 1.0."
                            )
            return threshold

    @property
    def supp_precip_dirs(self):
        """Get the list of pathways to the supplemental precipitation input forcing directories specified by the user in the configuration file. This is used to control where the program looks for supplemental precipitation input forcing files for each supplemental precipitation input forcing based on the directory specified for each supplemental precipitation input forcing in the configuration file."""
        if self.number_supp_pcp > 0:
            return self._supp_precip_dirs

    @supp_precip_dirs.setter
    def supp_precip_dirs(self, value):
        """Set the list of pathways to the supplemental precipitation input forcing directories specified by the user in the configuration file. This is used to control where the program looks for supplemental precipitation input forcing files for each supplemental precipitation input forcing based on the directory specified for each supplemental precipitation input forcing in the configuration file."""
        if value is None and self.number_supp_pcp > 0:
            value = self.extract_input_variable("SuppPcpDirectories")
        if value > 0:
            self.check_number_of_inputs_supp_pcp(value, "SuppPcpDirectories")
            for dirTmp in range(0, len(value)):
                value[dirTmp] = value[dirTmp].strip()
                if not os.path.isdir(value[dirTmp]):
                    try:
                        os.makedirs(value[dirTmp], exist_ok=True)
                        LOG.debug(f"Created supp pcp directory: {value[dirTmp]}")
                    except OSError as e:
                        err_out_screen(
                            f"Unable to create supp pcp directory: {value[dirTmp]}. Error: {e}"
                        )
            self._supp_precip_dirs = value

    @property
    def supp_precip_mandatory(self):
        """Get the list of flags for whether each supplemental precipitation input forcing specified by the user in the configuration file is mandatory or optional. This is used to control whether an error is raised if supplemental precipitation input forcing files are not found for each supplemental precipitation input forcing based on whether the user has specified each supplemental precipitation input forcing as mandatory or optional in the configuration file."""
        return self._supp_precip_mandatory

    @supp_precip_mandatory.setter
    def supp_precip_mandatory(self, value):
        """Set the list of flags for whether each supplemental precipitation input forcing specified by the user in the configuration file is mandatory or optional. This is used to control whether an error is raised if supplemental precipitation input forcing files are not found for each supplemental precipitation input forcing based on whether the user has specified each supplemental precipitation input forcing as mandatory or optional in the configuration file."""
        if value is None and self.number_supp_pcp > 0:
            value = self.extract_input_variable("SuppPcpMandatory")
        if self.number_supp_pcp > 0:
            for enforceOpt in value:
                self.check_input_values_in_range(enforceOpt, "SuppPcpMandatory", [0, 1])
            self._supp_precip_mandatory = value

    @property
    def regrid_opt_supp_pcp(self):
        """Get the list of regridding options for supplemental precipitation input forcings specified by the user in the configuration file. This is used to control how supplemental precipitation input forcings are regridded based on the regridding option specified for each supplemental precipitation input forcing in the configuration file."""
        return self._regrid_opt_supp_pcp

    @regrid_opt_supp_pcp.setter
    def regrid_opt_supp_pcp(self, value):
        """Set the list of regridding options for supplemental precipitation input forcings specified by the user in the configuration file. This is used to control how supplemental precipitation input forcings are regridded based on the regridding option specified for each supplemental precipitation input forcing in the configuration file."""
        if value is None and self.number_supp_pcp > 0:
            value = self.extract_input_variable("RegridOptSuppPcp")
        if self.number_supp_pcp > 0:
            for optTmp in value:
                self.check_input_values_in_range(optTmp, "RegridOptSuppPcp", [1, 2, 3])
            self._regrid_opt_supp_pcp = value

    @property
    def suppTemporalInterp(self):
        """Get the list of flags for whether temporal interpolation of supplemental precipitation input forcings specified by the user in the configuration file is performed or not. This is used to control whether temporal interpolation of supplemental precipitation input forcings is performed based on whether the user has chosen to perform temporal interpolation for each supplemental precipitation input forcing in the configuration file."""
        if self.number_supp_pcp > 0:
            return self._suppTemporalInterp

    @suppTemporalInterp.setter
    def suppTemporalInterp(self, value):
        """Set the list of flags for whether temporal interpolation of supplemental precipitation input forcings specified by the user in the configuration file is performed or not. This is used to control whether temporal interpolation of supplemental precipitation input forcings is performed based on whether the user has chosen to perform temporal interpolation for each supplemental precipitation input forcing in the configuration file."""
        if value is None and self.number_supp_pcp > 0:
            value = self.extract_input_variable("SuppPcpTemporalInterpolation")
        if self.number_supp_pcp > 0:
            for optTmp in value:
                self.check_input_values_in_range(
                    optTmp, "SuppPcpTemporalInterpolation", [0, 1, 2]
                )
            self._suppTemporalInterp = value

    @property
    def supp_pcp_max_hours(self):
        """Get the list of maximum forecast hours for supplemental precipitation input forcings specified by the user in the configuration file. This is used to control how supplemental precipitation input forcings are processed based on the maximum forecast hour specified for each supplemental precipitation input forcing in the configuration file."""
        if self.number_supp_pcp > 0:
            return self._supp_pcp_max_hours

    @supp_pcp_max_hours.setter
    def supp_pcp_max_hours(self, value):
        """Set the list of maximum forecast hours for supplemental precipitation input forcings specified by the user in the configuration file. This is used to control how supplemental precipitation input forcings are processed based on the maximum forecast hour specified for each supplemental precipitation input forcing in the configuration file."""
        if value is None and self.number_supp_pcp > 0:
            value = self.extract_input_variable("SuppPcpMaxHours")
        if self.number_supp_pcp > 0:
            if isinstance(value, list):
                self.check_input_values_positive(value, "SuppPcpMaxHours")
            elif isinstance(value, float) or isinstance(value, int):
                self.check_input_values_positive(value, "SuppPcpMaxHours")
                value = [value] * self.number_supp_pcp
            self._supp_pcp_max_hours = value

    @property
    def supp_input_offsets(self):
        """Get the list of time offsets to apply to supplemental precipitation input forcing files specified by the user in the configuration file. This is used to control how supplemental precipitation input forcing files are processed based on the time offset specified for each supplemental precipitation input forcing in the configuration file."""
        return self._supp_input_offsets

    @supp_input_offsets.setter
    def supp_input_offsets(self, value):
        """Set the list of time offsets to apply to supplemental precipitation input forcing files specified by the user in the configuration file. This is used to control how supplemental precipitation input forcing files are processed based on the time offset specified for each supplemental precipitation input forcing in the configuration file."""
        if value is None and self.number_supp_pcp > 0:
            value = self.extract_input_variable("SuppPcpInputOffsets")
        if self.number_supp_pcp > 0:
            self.check_number_of_inputs_supp_pcp(value, "SuppPcpInputOffsets")

    @property
    def supp_precip_param_dir(self):
        """Get the directory where downscaling parameters for supplemental precipitation input forcings are stored specified by the user in the configuration file. This is used to control where the program looks for downscaling parameter files for supplemental precipitation input forcings based on the directory specified for supplemental precipitation input forcings in the configuration file."""
        if self.number_supp_pcp > 0:
            return self._supp_precip_param_dir

    @supp_precip_param_dir.setter
    def supp_precip_param_dir(self, value):
        """Set the directory where downscaling parameters for supplemental precipitation input forcings are stored specified by the user in the configuration file. This is used to control where the program looks for downscaling parameter files for supplemental precipitation input forcings based on the directory specified for supplemental precipitation input forcings in the configuration file."""
        if value is None and self.number_supp_pcp > 0:
            value = self.extract_input_variable("SuppPcpDownscalingParamDir")
        if self.number_supp_pcp > 0:
            if not os.path.isdir(value):
                err_out_screen(
                    f"Unable to locate parameter directory: {os.path.abspath(value)}"
                )
            self._supp_precip_param_dir = value

    @property
    def supp_precip_dirs(self):
        """Get the list of pathways to the supplemental precipitation input forcing directories specified by the user in the configuration file. This is used to control where the program looks for supplemental precipitation input forcing files for each supplemental precipitation input forcing based on the directory specified for each supplemental precipitation input forcing in the configuration file."""
        if self.number_supp_pcp > 0:
            return self._supp_precip_dirs

    @supp_precip_dirs.setter
    def supp_precip_dirs(self, value):
        """Set the list of pathways to the supplemental precipitation input forcing directories specified by the user in the configuration file. This is used to control where the program looks for supplemental precipitation input forcing files for each supplemental precipitation input forcing based on the directory specified for each supplemental precipitation input forcing in the configuration file."""
        if value is None and self.number_supp_pcp > 0:
            value = self.extract_input_variable("SuppPcpDirectories")
        if self.number_supp_pcp > 0:
            # Loop through and ensure all supp pcp directories exist. Also strip out any whitespace
            # or new line characters.
            for dirTmp in range(0, len(value)):
                value[dirTmp] = value[dirTmp].strip()
                if not os.path.isdir(value[dirTmp]):
                    try:
                        os.makedirs(value[dirTmp], exist_ok=True)
                        LOG.debug(f"Created supp pcp directory: {value[dirTmp]}")
                    except OSError as e:
                        err_out_screen(
                            f"Unable to create supp pcp directory: {value[dirTmp]}. Error: {e}"
                        )

            # Special case for ExtAnA where we treat comma separated stage IV, MRMS data as one SuppPcp input
            if 11 in self.supp_precip_forcings or 12 in self.supp_precip_forcings:
                if len(self.supp_precip_forcings) != 1:
                    err_out_screen(
                        "CONUS or Alaska Stage IV/MRMS SuppPcp option is only supported as a standalone option"
                    )
                value = [",".join(value)]
            self._supp_precip_dirs = value

    @property
    def supp_precip_param_dir(self):
        """Get the directory where downscaling parameters for supplemental precipitation input forcings are stored specified by the user in the configuration file. This is used to control where the program looks for downscaling parameter files for supplemental precipitation input forcings based on the directory specified for supplemental precipitation input forcings in the configuration file."""
        if self.number_supp_pcp > 0:
            return self._supp_precip_param_dir

    @supp_precip_param_dir.setter
    def supp_precip_param_dir(self, value):
        """Set the directory where downscaling parameters for supplemental precipitation input forcings are stored specified by the user in the configuration file. This is used to control where the program looks for downscaling parameter files for supplemental precipitation input forcings based on the directory specified for supplemental precipitation input forcings in the configuration file."""
        if value is None and self.number_supp_pcp > 0:
            value = self.extract_input_variable("SuppPcpDownscalingParamDir")
        if self.number_supp_pcp > 0:
            try:
                os.makedirs(value, exist_ok=True)
                LOG.debug(f"Created missing SuppPcpParamDir: {value}")
            except OSError as e:
                err_out_screen(f"Unable to locate SuppPcpParamDir: {value}. Error: {e}")

    @property
    def cfsv2EnsMember(self):
        """Get the CFSv2 ensemble member to process specified by the user in the configuration file. This is used to control which CFSv2 ensemble member is processed for CFSv2 input forcings based on the ensemble member specified in the configuration file."""
        return self._cfsv2EnsMember

    @cfsv2EnsMember.setter
    def cfsv2EnsMember(self, value):
        """Set the CFSv2 ensemble member to process specified by the user in the configuration file. This is used to control which CFSv2 ensemble member is processed for CFSv2 input forcings based on the ensemble member specified in the configuration file."""
        if value is None and not self.precip_only_flag:
            # Read in Ensemble information
            # Read in CFS ensemble member information IF we have chosen CFSv2 as an input
            # forcing.
            for opt_tmp in self.input_forcings:
                if opt_tmp == 7:
                    value = self.extract_input_variable("cfsEnsNumber")
                    self.check_input_values_in_range(
                        value, "cfsEnsNumber", [1, 2, 3, 4]
                    )

    @property
    def customFcstFreq(self):
        """Get the custom forecast frequency in minutes specified by the user in the configuration file. This is used to control how often forecasts are issued based on the custom forecast frequency specified in the configuration file."""
        return self._customFcstFreq

    @customFcstFreq.setter
    def customFcstFreq(self, value):
        """Set the custom forecast frequency in minutes specified by the user in the configuration file. This is used to control how often forecasts are issued based on the custom forecast frequency specified in the configuration file."""
        if value is None and not self.precip_only_flag:
            value = self.extract_input_variable("CustomFcstFreq")
            if len(self.customFcstFreq) != self.number_custom_inputs:
                err_out_screen(
                    f"Improper custom_input fcst_freq specified. This number ({len(self.customFcstFreq)}) must match the frequency of custom input forcings selected ({self.number_custom_inputs})."
                )
            self._customFcstFreq = value

    def _validate_config(self) -> None:
        """Validate in options from the configuration file and check that proper options were provided."""
        self.b_date_proc

        # if not self.precip_only_flag:

        if self.output_freq <= 0:
            err_out_screen(
                "Please specify an OutputFrequency that is greater than zero minutes."
            )

        if self.sub_output_hour < 0:
            err_out_screen(
                "Please specify an SubOutputHour that is greater than zero minutes."
            )
        if self.sub_output_hour == 0:
            self.sub_output_hour = None

        if self.sub_output_freq < 0:
            err_out_screen(
                "Please specify an SubOutFreq that is greater than zero minutes."
            )
        if self._sub_output_freq == 0:
            self.sub_output_freq = None

        # TODO Can this be a /tmp directory?
        self.make_scratch_dir()

        if self.useCompression not in [0, 1]:
            err_out_screen("Please choose a compressOut value of 0 or 1.")

        if self.ana_flag in [0, 1]:
            err_out_screen("Please choose a AnAFlag value of 0 or 1.")

        if self.look_back <= 0 and self.look_back != -9999:
            err_out_screen("Please specify a positive LookBack or -9999 for realtime.")

        if self.fcst_freq <= 0:
            err_out_screen(
                "Please specify a ForecastFrequency in the configuration file greater than zero."
            )
        # Currently, we only support daily or sub-daily forecasts. Any other iterations should
        # be done using custom config files for each forecast cycle.
        if self.fcst_freq > 1440:
            err_out_screen(
                "Only forecast cycles of daily or sub-daily are supported at this time"
            )

        # Read in the ForecastShift option. This is ONLY done for the realtime instance as
        # it's used to calculate the beginning of the processing window.
        if True:  # was: self.realtime_flag:
            self.fcst_shift = self.extract_input_variable("ForecastShift")
            if self.fcst_shift < 0:
                err_out_screen(
                    "Please specify a ForecastShift in the configuration file greater than or equal to zero."
                )

            # Calculate the beginning/ending processing dates if we are running realtime
            if self.realtime_flag:
                calculate_lookback_window(self)

        # if self.refcst_flag:
        # Calculate the number of forecasts to issue, and verify the user has chosen a
        # correct divider based on the dates
        # dt_tmp = self.e_date_proc - self.b_date_proc
        # if (dt_tmp.days * 1440 + dt_tmp.seconds / 60.0) % self.fcst_freq != 0:
        #    err_out_screen('Please choose an equal divider forecast frequency for your '
        #                               'specified reforecast range.')
        # self.nFcsts = int((dt_tmp.days * 1440 + dt_tmp.seconds / 60.0) / self.fcst_freq)

        # Flag to constrain AORC forcing data cycle output
        # for optTmp in self.input_forcings:
        # if optTmp == 12:
        # self.nFcsts = 1
        self.nFcsts = 1

        if self.look_back != -9999:
            calculate_lookback_window(self)

        # Process geospatial information

        if len(self.spatial_meta) == 0:
            # No spatial metadata file found.
            self.spatial_meta = None
        else:
            if not os.path.isfile(self.spatial_meta):
                err_out_screen(
                    "Unable to locate optional spatial metadata file: "
                    + self.spatial_meta
                )

        # Calculate the beginning/ending processing dates if we are running realtime
        if self.realtime_flag:
            calculate_lookback_window(self)

        # Create temporary array to hold flags if we need input parameter files.
        param_flag = np.zeros([len(self.input_forcings)], int)

        count_tmp = 0
        for optTmp in self.precipDownscaleOpt:
            if optTmp == 1:
                param_flag[count_tmp] = 1
            count_tmp = count_tmp + 1

            for suppOpt in self.supp_precip_forcings:
                if suppOpt not in list(range(1, self.supp_precip_count + 1)):
                    err_out_screen(
                        f"Please specify SuppForcing values between 1 and {self.supp_precip_count}."
                    )

    @property
    def nwm_domain(self) -> str:
        """Extract NWM domain from the geogrid filename, using regex pattern."""
        if self.nwm_geogrid is None:
            return None
        pattern = r"geo_em_([a-zA-Z-_]+)\.nc$"  # E.g. extract "Puerto_Rico" from /foo/bar/esmf_mesh/NWM/domain/geo_em_Puerto_Rico.nc
        groups = re.findall(pattern, self.nwm_geogrid)
        if len(groups) != 1:
            raise ValueError(
                f"Could not determine NWM domain. {len(groups)} groups found (expected 1) in {self.nwm_geogrid} using regex pattern {pattern}"
            )
        domain = groups[0]
        if domain in ["PuertoRico", "Puerto_Rico", "PR"]:
            return "PR"
        else:
            return domain

    @property
    def nwm_url(self):
        """Construct NWM Zarr URL based on domain."""
        if self.nwm_domain is None:
            return None
        elif self.nwm_domain == "CONUS":
            return "{source}/{domain}/zarr/forcing/{var}.zarr"
        elif self.nwm_domain in ["Hawaii", "PR", "Alaska"]:
            return "{source}/{domain}/zarr/forcing.zarr"
        else:
            raise ValueError(
                f"Unknown domain. Expected 'CONUS', 'Hawaii', 'PR', or 'Alaska'; received: '{self.nwm_domain}'"
            )

    @property
    def use_data_at_current_time(self):
        """Determine if supplemental precipitation data can be used at the current output time."""
        if self.supp_pcp_max_hours:
            hrs_since_start = self.current_output_date - self.current_fcst_cycle
            return hrs_since_start <= timedelta(hours=self.supp_pcp_max_hours)
        else:
            return True
