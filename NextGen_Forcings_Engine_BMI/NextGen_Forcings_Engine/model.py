from __future__ import annotations
import datetime
from contextlib import contextmanager
from time import perf_counter
from typing import TYPE_CHECKING

import ewts
import numpy as np
import pandas as pd

from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.core import (
    bias_correction,
    disaggregateMod,
    downscale,
    err_handler,
    forcingInputMod,
    layeringMod,
)
from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.historical_forcing import (
    AORCAlaskaProcessor,
    AORCConusProcessor,
    NWMV3AlaskaProcessor,
    NWMV3ConusProcessor,
    NWMV3OConusProcessor,
)

if TYPE_CHECKING:
    # To allow type hint without circular import error
    from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.bmi_model import (
        NWMv3_Forcing_Engine_BMI_model_Base,
    )

LOG = ewts.get_logger(ewts.FORCING_ID)


@contextmanager
def timing_block(step_str: str):
    """Context manager for timing code execution.

    Args:
        step_str: Description of the step being timed.

    """
    start = perf_counter()
    yield
    end = perf_counter()
    LOG.debug(f"  Execution time for {step_str}: {round(end - start, 2)} seconds")


def time_function(func):
    """Measure the execution time of a function."""

    def wrapper(*args, **kwargs):
        with timing_block(f"Executing {func.__name__}"):
            result = func(*args, **kwargs)
            return result

    return wrapper


class NWMv3ForcingEngineModel:
    """NextGen Forcings Engine BMI model class for NWMv3 forcings."""

    def __init__(self, bmi_model: NWMv3_Forcing_Engine_BMI_model_Base):
        """Initialize the NWMv3 Forcing Engine Model."""
        self.source_data_processor = None
        self._bmi = bmi_model

    # TODO: refactor the bmi_model.py file and this to have this type maintain its own state.
    # def __init__(self):
    #    super(ngen_model, self).__init__()
    #    #self._model = model

    # @dask.delayed
    # def aws_obj(files):
    #    return xr.open_mfdataset(files, engine="zarr", parallel=True, consolidated=True)

    def run(self, future_time: float) -> None:
        """Execute the full forcings engine BMI pipeline for a given future timestep.

        This method updates the `self._bmi._values` state dictionary with atmospheric forcings computed from
        available input datasets. It handles initialization, AWS Zarr loading, regridding, temporal
        interpolation, bias correction, downscaling, supplemental precipitation processing, and output
        population into the self._bmi._values structure.

        `self._bmi._job_meta`, an instance of ConfigOptions is also updated in-place, for example for time handling.

        The following steps are performed:

        1. Determine the current forecast and output times based on the future timestamp
           and analysis mode (AnA or forecast).
        2. Initialize or reset output grids and step counters.
        3. Loop over each input forcing product:
           a. Calculate neighboring input files.
           b. Load AWS-hosted Zarr datasets if needed.
           c. Regrid input forcings to the model grid.
           d. Perform temporal interpolation.
           e. Apply bias correction and downscaling.
           f. Layer final forcings into the output object.
        4. Optionally process supplemental precipitation forcings:
           a. Regrid and validate.
           b. Disaggregate and interpolate.
           c. Layer into the final output.
        5. Write output to NetCDF forcing files if requested.
        6. Update the self._bmi._values state dictionary with flattened arrays.
        7. Advance the BMI time index.

        :param future_time: The number of seconds into the future to advance the model.

        :raises RuntimeError: If the model fails to initialize or if required arguments are missing.
        """

        self.determine_forecast(future_time)
        self.adjust_precip()
        self.log_forecast()
        # TODO look into input_forcings usage in `process_suplemental_precip` and in `loop_through_forcing_products` at `disaggregate_fun`.
        input_forcings = self.loop_through_forcing_products(
            future_time,
        )
        self.process_suplemental_precip(input_forcings)
        self.write_output()
        self.update_dict()

        ## Update BMI model time index to next iteration
        self._bmi._job_meta.bmi_time_index += 1

    @time_function
    def determine_forecast(self, future_time: float) -> None:
        """Determine the forecast for the given future time and configuration.

        Warnings
        --------
            Modifies mutable arguments in-place.
        """
        # Assign the future time to the configuration
        self._bmi._job_meta.bmi_time = future_time
        self.disaggregate_fun = disaggregateMod.disaggregate_factory(
            self._bmi._job_meta
        )

        # Calculate current time stamp based on operational configuration
        if self._bmi._job_meta.ana_flag:
            # If we're in an AnA configuration, then must offset the BMI future
            # timestamp to account for the "lookback" period being properly iterated
            # over between 3-28 hour look back time period and operation configuration
            # TODO confirm these codes, and should they consider all input_forcings not just [0]?
            if self._bmi._job_meta.input_forcings[0] in [20, 22]:
                delta = pd.TimedeltaIndex(
                    np.array([future_time - 7200.0], dtype=float), "s"
                )[0]
                self._bmi._job_meta.current_fcst_cycle = (
                    self._bmi._job_meta.b_date_proc + delta
                )
                self._bmi._job_meta.current_time = (
                    self._bmi._job_meta.b_date_proc + delta
                )
                self._bmi._job_meta.future_time = future_time
            else:
                # Puerto Rico / Hawaii AnA: 1-hour lookback (based on 6-hourly forecast cycles)
                delta = pd.TimedeltaIndex(
                    np.array([future_time - 3600.0], dtype=float), "s"
                )[0]
                self._bmi._job_meta.current_fcst_cycle = (
                    self._bmi._job_meta.b_date_proc + delta
                )
                self._bmi._job_meta.current_time = (
                    self._bmi._job_meta.b_date_proc + delta
                )
        else:
            # Forecast-only mode — use BMI timestamp as-is
            self._bmi._job_meta.current_fcst_cycle = self._bmi._job_meta.b_date_proc
            self._bmi._job_meta.current_time = pd.Timestamp(
                self._bmi._job_meta.b_date_proc
            ) + pd.to_timedelta(future_time, unit="s")

        LOG.debug(
            "NextGen Forcings Engine processing meteorological forcings for BMI timestamp"
        )
        LOG.debug(f"Model.py current time: {self._bmi._job_meta.current_time}")
        LOG.debug(
            f"Model.py current fcst cycle: {self._bmi._job_meta.current_fcst_cycle}"
        )

        if self._bmi._job_meta.first_fcst_cycle is None:
            self._bmi._job_meta.first_fcst_cycle = (
                self._bmi._job_meta.current_fcst_cycle
            )

    @time_function
    def adjust_precip(self) -> None:
        """Adjust precipitation for the given forecast cycle.

        Warnings
        --------
            Modifies mutable arguments in-place.
        """
        if not self._bmi._job_meta.precip_only_flag:
            # reset skips if present
            for force_key in self._bmi._job_meta.input_forcings:
                self._bmi._input_forcing_mod[force_key].skip = False

            err_handler.check_program_status(self._bmi._job_meta, self._bmi._mpi_meta)

    @time_function
    def log_forecast(self) -> None:
        """Log information about the current forecast cycle.

        Warnings
        --------
            Modifies mutable arguments in-place.
        """
        # Log information about this forecast cycle
        if self._bmi._mpi_meta.rank == 0:
            self._bmi._job_meta.statusMsg = "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
            err_handler.log_msg(self._bmi._job_meta, self._bmi._mpi_meta, True)
            self._bmi._job_meta.statusMsg = (
                "Processing Forecast Cycle: "
                + self._bmi._job_meta.current_fcst_cycle.strftime("%Y-%m-%d %H:%M")
            )
            err_handler.log_msg(self._bmi._job_meta, self._bmi._mpi_meta, True)
            self._bmi._job_meta.statusMsg = (
                "Forecast Cycle Length is: "
                + str(self._bmi._job_meta.cycle_length_minutes)
                + " minutes"
            )
            err_handler.log_msg(self._bmi._job_meta, self._bmi._mpi_meta, True)
        # self._bmi._mpi_meta.comm.barrier()

    @time_function
    def loop_through_forcing_products(
        self, future_time: float
    ) -> forcingInputMod.InputForcingsHydrofabric:
        """Loop through each forcing product and process it for the current forecast cycle.

        Warnings
        --------
            Modifies mutable arguments in-place.
        """
        # Loop through each output timestep. Perform the following functions:
        # 1.) Calculate all necessary input files per user options.
        # 2.) Read in input forcings from GRIB/NetCDF files.
        # 3.) Regrid the forcings, and temporally interpolate.
        # 4.) Downscale.
        # 5.) Layer, and output as necessary.
        ana_factor = 1 if self._bmi._job_meta.ana_flag is False else 0
        if not self._bmi._job_meta.precip_only_flag:
            if self._bmi._job_meta.grid_type == "gridded":
                # Reset out final grids to missing values.
                self._bmi._output_obj.output_local[:, :, :] = (
                    self._bmi._job_meta.globalNdv
                )
            elif self._bmi._job_meta.grid_type == "unstructured":
                # Reset out final grids to missing values.
                self._bmi._output_obj.output_local[:, :] = self._bmi._job_meta.globalNdv
                self._bmi._output_obj.output_local_elem[:, :] = (
                    self._bmi._job_meta.globalNdv
                )
            elif self._bmi._job_meta.grid_type == "hydrofabric":
                # Reset out final grids to missing values.
                self._bmi._output_obj.output_local[:, :] = self._bmi._job_meta.globalNdv
            else:
                raise ValueError(
                    f"Unexpected grid_type: {repr(self._bmi._job_meta.grid_type)}"
                )

            # Increment or initialize output step count
            if self._bmi._job_meta.current_output_step is None:
                self._bmi._job_meta.current_output_step = 1
            else:
                self._bmi._job_meta.current_output_step += 1

            # Optional sub-output timestamp
            if self._bmi._job_meta.sub_output_hour is not None:
                # TODO This is not used
                subOutDate = self._bmi._job_meta.first_fcst_cycle + datetime.timedelta(
                    hours=self._bmi._job_meta.sub_output_hour
                )

            # Compute the output timestamp for this step
            if self._bmi._job_meta.ana_flag:
                self._bmi._output_obj.outDate = (
                    self._bmi._job_meta.current_fcst_cycle
                    + datetime.timedelta(seconds=self._bmi._job_meta.output_freq * 60)
                )
            else:
                self._bmi._output_obj.outDate = (
                    self._bmi._job_meta.current_fcst_cycle
                    + datetime.timedelta(seconds=future_time)
                )

            self._bmi._job_meta.current_output_date = self._bmi._output_obj.outDate

            # Adjust file_date for AnA if needed
            file_date = (
                self._bmi._output_obj.outDate
                - datetime.timedelta(seconds=self._bmi._job_meta.output_freq * 60)
                if self._bmi._job_meta.ana_flag
                else self._bmi._output_obj.outDate
            )

            # Compute previous output date (used for downscaling logic)
            if self._bmi._job_meta.current_output_step == ana_factor:
                self._bmi._job_meta.prev_output_date = (
                    self._bmi._job_meta.current_output_date
                )
            else:
                self._bmi._job_meta.prev_output_date = (
                    self._bmi._job_meta.current_output_date
                    - datetime.timedelta(seconds=future_time)
                )

            # Print message on log file indicating the timestamp
            # we are currently processing for forcings
            if self._bmi._mpi_meta.rank == 0:
                self._bmi._job_meta.statusMsg = (
                    "========================================="
                )
                err_handler.log_msg(self._bmi._job_meta, self._bmi._mpi_meta, True)
                self._bmi._job_meta.statusMsg = f"Processing for output timestep: {file_date.strftime('%Y-%m-%d %H:%M')}"
                err_handler.log_msg(self._bmi._job_meta, self._bmi._mpi_meta, True)

            self._bmi._job_meta.currentForceNum = 0
            self._bmi._job_meta.currentCustomForceNum = 0
            LOG.debug(
                f"config_options.input_forcings: {self._bmi._job_meta.input_forcings}"
            )
            # Loop over each of the input forcings specified.
            LOG.debug(
                f"Model.py forcing loop: {len(self._bmi._job_meta.input_forcings)} forcings configured: {self._bmi._job_meta.input_forcings}"
            )

            for force_key in self._bmi._job_meta.input_forcings:
                LOG.debug(f"force_key: {force_key}")
                LOG.debug(f"config_options.aws: {self._bmi._job_meta.aws}")
                # Pass these methods for AORC data is ERA5-Interim blend is requested
                # so we can finish filling in the missing gaps
                if (
                    force_key == 23
                    and 12 in self._bmi._job_meta.input_forcings
                    and 21 in self._bmi._job_meta.input_forcings
                ):
                    input_forcings = self._bmi._input_forcing_mod[force_key]

                    # These are not used
                    # AORC_mask = input_forcings.regridded_mask_AORC
                    # AORC_elem_mask = input_forcings.regridded_mask_elem_AORC
                else:
                    input_forcings = self._bmi._input_forcing_mod[force_key]
                    input_forcings.calc_neighbor_files(
                        self._bmi._job_meta,
                        self._bmi._output_obj.outDate,
                        self._bmi._mpi_meta,
                    )

                if force_key in [12, 21, 27]:
                    if self._bmi._job_meta.aws is None:
                        # Calculate the previous and next input cycle files from the inputs.
                        input_forcings.calc_neighbor_files(
                            self._bmi._job_meta,
                            self._bmi._output_obj.outDate,
                            self._bmi._mpi_meta,
                        )
                        err_handler.check_program_status(
                            self._bmi._job_meta, self._bmi._mpi_meta
                        )
                    else:
                        # Flag to indicate the AWS .zarr AORC method
                        if force_key == 12:
                            if self.source_data_processor is None:
                                self.source_data_processor = AORCConusProcessor(
                                    self._bmi._job_meta,
                                    self._bmi._mpi_meta,
                                    self._bmi.geo_meta,
                                )
                        elif force_key == 21:
                            if self.source_data_processor is None:
                                self.source_data_processor = AORCAlaskaProcessor(
                                    self._bmi._job_meta,
                                    self._bmi._mpi_meta,
                                    self._bmi.geo_meta,
                                )

                        # Flag to indicate the AWS .zarr NWMv3 Forcing file method
                        elif force_key == 27:
                            if self.source_data_processor is None:
                                if self._bmi._job_meta.nwm_domain == "CONUS":
                                    self.source_data_processor = NWMV3ConusProcessor(
                                        self._bmi._job_meta,
                                        self._bmi._mpi_meta,
                                        self._bmi.geo_meta,
                                    )
                                elif self._bmi._job_meta.nwm_domain in [
                                    "Hawaii",
                                    "PR",
                                ]:
                                    self.source_data_processor = NWMV3OConusProcessor(
                                        self._bmi._job_meta,
                                        self._bmi._mpi_meta,
                                        self._bmi.geo_meta,
                                    )
                                elif self._bmi._job_meta.nwm_domain == "Alaska":
                                    self.source_data_processor = NWMV3AlaskaProcessor(
                                        self._bmi._job_meta,
                                        self._bmi._mpi_meta,
                                        self._bmi.geo_meta,
                                    )
                                else:
                                    raise ValueError(
                                        f"Unsupported domain type ({self._bmi._job_meta.nwm_domain} for forcing type: {force_key} )"
                                    )

                        self._bmi._job_meta.aws_obj = (
                            self.source_data_processor.process_historical_data(
                                self._bmi._job_meta.current_time
                            )
                        )

                # If skipping this forcing, continue early
                if input_forcings.skip is True:
                    LOG.debug(f"Breaking loop for force_key {force_key}")
                    break
                # Regrid forcings.
                input_forcings.regrid_inputs(
                    self._bmi._job_meta, self._bmi.geo_meta, self._bmi._mpi_meta
                )
                err_handler.check_program_status(
                    self._bmi._job_meta, self._bmi._mpi_meta
                )

                # Run check on regridded fields for reasonable values that are not missing values.
                err_handler.check_forcing_bounds(
                    self._bmi._job_meta, input_forcings, self._bmi._mpi_meta
                )
                err_handler.check_program_status(
                    self._bmi._job_meta, self._bmi._mpi_meta
                )

                # If we are restarting a forecast cycle, re-calculate the neighboring files, and regrid the
                # next set of forcings as the previous step just regridded the previous forcing.
                if input_forcings.rstFlag == 1:
                    if (
                        input_forcings.regridded_forcings1 is not None
                        and input_forcings.regridded_forcings2 is not None
                    ):
                        # Set the forcings back to reflect we just regridded the previous set of inputs, not the next.
                        if self._bmi._job_meta.grid_type == "gridded":
                            input_forcings.regridded_forcings1[:, :, :] = (
                                input_forcings.regridded_forcings2[:, :, :]
                            )
                        elif self._bmi._job_meta.grid_type == "unstructured":
                            input_forcings.regridded_forcings1[:, :] = (
                                input_forcings.regridded_forcings2[:, :]
                            )
                            input_forcings.regridded_forcings1_elem[:, :] = (
                                input_forcings.regridded_forcings2_elem[:, :]
                            )
                        elif self._bmi._job_meta.grid_type == "hydrofabric":
                            input_forcings.regridded_forcings1[:, :] = (
                                input_forcings.regridded_forcings2[:, :]
                            )
                        else:
                            raise ValueError(
                                f"Unexpected grid_type: {repr(self._bmi._job_meta.grid_type)}"
                            )
                    # Re-calculate the neighbor files.
                    input_forcings.calc_neighbor_files(
                        self._bmi._job_meta,
                        self._bmi._output_obj.outDate,
                        self._bmi._mpi_meta,
                    )
                    err_handler.check_program_status(
                        self._bmi._job_meta, self._bmi._mpi_meta
                    )

                    # Regrid the forcings for the end of the window.
                    input_forcings.regrid_inputs(
                        self._bmi._job_meta, self._bmi.geo_meta, self._bmi._mpi_meta
                    )
                    err_handler.check_program_status(
                        self._bmi._job_meta, self._bmi._mpi_meta
                    )

                    input_forcings.rstFlag = 0

                # Run temporal interpolation on the grids.
                input_forcings.temporal_interpolate_inputs(
                    self._bmi._job_meta, self._bmi._mpi_meta
                )
                err_handler.check_program_status(
                    self._bmi._job_meta, self._bmi._mpi_meta
                )

                # Run bias correction.
                bias_correction.run_bias_correction(
                    input_forcings,
                    self._bmi._job_meta,
                    self._bmi.geo_meta,
                    self._bmi._mpi_meta,
                )
                err_handler.check_program_status(
                    self._bmi._job_meta, self._bmi._mpi_meta
                )

                # Run downscaling on grids for this output timestep.
                downscale.run_downscaling(
                    input_forcings,
                    self._bmi._job_meta,
                    self._bmi.geo_meta,
                    self._bmi._mpi_meta,
                )
                err_handler.check_program_status(
                    self._bmi._job_meta, self._bmi._mpi_meta
                )

                # Layer in forcings from this product.
                layeringMod.layer_final_forcings(
                    self._bmi._output_obj,
                    input_forcings,
                    self._bmi._job_meta,
                    self._bmi._mpi_meta,
                )
                err_handler.check_program_status(
                    self._bmi._job_meta, self._bmi._mpi_meta
                )

                self._bmi._job_meta.currentForceNum += 1

                if force_key == 10:
                    self._bmi._job_meta.currentCustomForceNum += 1

                LOG.debug(f"End of loop for force_key {force_key}")

            # Process supplemental precipitation if we specified in the configuration file.
            if self._bmi._job_meta.number_supp_pcp > 0:
                for supp_pcp_key in self._bmi._job_meta.supp_precip_forcings:
                    if supp_pcp_key != 13:
                        # Like with input forcings, calculate the neighboring files to use.
                        self._bmi._supp_pcp_mod[supp_pcp_key].calc_neighbor_files(
                            self._bmi._job_meta,
                            self._bmi._output_obj.outDate,
                            self._bmi._mpi_meta,
                        )
                        err_handler.check_program_status(
                            self._bmi._job_meta, self._bmi._mpi_meta
                        )

                        # Regrid the supplemental precipitation.
                        self._bmi._supp_pcp_mod[supp_pcp_key].regrid_inputs(
                            self._bmi._job_meta, self._bmi.geo_meta, self._bmi._mpi_meta
                        )
                        err_handler.check_program_status(
                            self._bmi._job_meta, self._bmi._mpi_meta
                        )

                        if (
                            self._bmi._supp_pcp_mod[supp_pcp_key].regridded_precip1
                            is not None
                            and self._bmi._supp_pcp_mod[supp_pcp_key].regridded_precip2
                            is not None
                        ):
                            # Run check on regridded fields for reasonable values that are not missing values.
                            err_handler.check_supp_pcp_bounds(
                                self._bmi._job_meta,
                                self._bmi._supp_pcp_mod[supp_pcp_key],
                                self._bmi._mpi_meta,
                                self._bmi.geo_meta,
                            )
                            err_handler.check_program_status(
                                self._bmi._job_meta, self._bmi._mpi_meta
                            )

                            # TODO input_forcings has not yet been initialized, so this is a bug waiting to happen
                            self.disaggregate_fun(
                                input_forcings,
                                self._bmi._supp_pcp_mod[supp_pcp_key],
                                self._bmi._job_meta,
                                self._bmi._mpi_meta,
                            )
                            err_handler.check_program_status(
                                self._bmi._job_meta, self._bmi._mpi_meta
                            )

                            # Run temporal interpolation on the grids.
                            self._bmi._supp_pcp_mod[
                                supp_pcp_key
                            ].temporal_interpolate_inputs(
                                self._bmi._job_meta, self._bmi._mpi_meta
                            )
                            err_handler.check_program_status(
                                self._bmi._job_meta, self._bmi._mpi_meta
                            )

                            # Layer in the supplemental precipitation into the current output object.
                            layeringMod.layer_supplemental_forcing(
                                self._bmi._output_obj,
                                self._bmi._supp_pcp_mod[supp_pcp_key],
                                self._bmi._job_meta,
                                self._bmi._mpi_meta,
                            )
                            err_handler.check_program_status(
                                self._bmi._job_meta, self._bmi._mpi_meta
                            )

            # Call the output routines
            #   adjust date for AnA if necessary
            if self._bmi._job_meta.ana_flag:
                self._bmi._output_obj.outDate = file_date

                ################ Commenting this out to bypass NWM forcing file output functionality #########
                # self._bmi._output_obj.output_final_ldasin(self._bmi._job_meta, self._bmi.geo_meta, self._bmi._mpi_meta)
                # err_handler.check_program_status(self._bmi._job_meta, self._bmi._mpi_meta)
                ##############################################################################################

        return input_forcings

    @time_function
    def process_suplemental_precip(self, input_forcings: dict) -> None:
        """Process supplemental precipitation for the current forecast cycle.

        Warnings
        --------
            Modifies mutable arguments in-place.
        """
        if self._bmi._job_meta.customSuppPcpFreq is not None:
            # Process supplemental precipitation if we specified in the configuration file.
            if self._bmi._job_meta.number_supp_pcp > 0:
                for supp_pcp_key in self._bmi._job_meta.supp_precip_forcings:
                    if supp_pcp_key == 14:
                        # Like with input forcings, calculate the neighboring files to use.
                        self._bmi._supp_pcp_mod[supp_pcp_key].calc_neighbor_files(
                            self._bmi._job_meta,
                            self._bmi._output_obj.outDate,
                            self._bmi._mpi_meta,
                        )
                        err_handler.check_program_status(
                            self._bmi._job_meta, self._bmi._mpi_meta
                        )

                        # Regrid the supplemental precipitation.
                        self._bmi._supp_pcp_mod[supp_pcp_key].regrid_inputs(
                            self._bmi._job_meta, self._bmi.geo_meta, self._bmi._mpi_meta
                        )
                        err_handler.check_program_status(
                            self._bmi._job_meta, self._bmi._mpi_meta
                        )

                        if (
                            self._bmi._supp_pcp_mod[supp_pcp_key].regridded_precip1
                            is not None
                            and self._bmi._supp_pcp_mod[supp_pcp_key].regridded_precip2
                            is not None
                        ):
                            # Run check on regridded fields for reasonable values that are not missing values.
                            err_handler.check_supp_pcp_bounds(
                                self._bmi._job_meta,
                                self._bmi._supp_pcp_mod[supp_pcp_key],
                                self._bmi._mpi_meta,
                                self._bmi.geo_meta,
                            )
                            err_handler.check_program_status(
                                self._bmi._job_meta, self._bmi._mpi_meta
                            )

                            self.disaggregate_fun(
                                input_forcings,
                                self._bmi._supp_pcp_mod[supp_pcp_key],
                                self._bmi._job_meta,
                                self._bmi._mpi_meta,
                            )
                            err_handler.check_program_status(
                                self._bmi._job_meta, self._bmi._mpi_meta
                            )

                            # Run temporal interpolation on the grids.
                            self._bmi._supp_pcp_mod[
                                supp_pcp_key
                            ].temporal_interpolate_inputs(
                                self._bmi._job_meta, self._bmi._mpi_meta
                            )
                            err_handler.check_program_status(
                                self._bmi._job_meta, self._bmi._mpi_meta
                            )

                            # Layer in the supplemental precipitation into the current output object.
                            layeringMod.layer_supplemental_forcing(
                                self._bmi._output_obj,
                                self._bmi._supp_pcp_mod[supp_pcp_key],
                                self._bmi._job_meta,
                                self._bmi._mpi_meta,
                            )
                            err_handler.check_program_status(
                                self._bmi._job_meta, self._bmi._mpi_meta
                            )

    @time_function
    def write_output(self) -> None:
        """Write the output for the current forecast cycle.

        Warnings
        --------
            Modifies mutable arguments in-place.
        """
        # If user requests output for given domain, then call
        # the I/O module to update opened netcdf file with forcing fields
        if (
            self._bmi._job_meta.forcing_output == 1
            or self._bmi._job_meta.grid_type == "hydrofabric"
        ):
            self._bmi._output_obj.gather_global_outputs(
                self._bmi._job_meta, self._bmi.geo_meta, self._bmi._mpi_meta
            )

        """##################Step 6: flatten and update dict##########################################################################"""

    @time_function
    def update_dict(self) -> None:
        """Flatten the Forcings Engine output object and update the BMI dictionary.

        Warnings
        --------
            Modifies mutable arguments in-place.
        """
        # Now loop through Forcings Engine output object
        # and flatten the 2D forcing array and append to
        # the BMI object to advertise to BMIinterface
        # 0.) U-Wind (m/s)
        # 1.) V-Wind (m/s)
        # 2.) Surface incoming longwave radiation flux (W/m^2)
        # 3.) Precipitation rate (mm/s)
        # 4.) 2-meter temperature (K)
        # 5.) 2-meter specific humidity (kg/kg)
        # 6.) Surface pressure (Pa)
        # 7.) Surface incoming shortwave radiation flux (W/m^2)
        # 8.) Liquid Precipitation Fraction (%), Only available in certain operational configurations

        if self._bmi._job_meta.include_lqfrac == 1:
            variables = [
                "U2D",
                "V2D",
                "LWDOWN",
                "RAINRATE",
                "T2D",
                "Q2D",
                "PSFC",
                "SWDOWN",
                "LQFRAC",
            ]
        else:
            variables = [
                "U2D",
                "V2D",
                "LWDOWN",
                "RAINRATE",
                "T2D",
                "Q2D",
                "PSFC",
                "SWDOWN",
            ]
        if self._bmi._job_meta.grid_type == "gridded":
            for count, variable in enumerate(variables):
                self._bmi._values[variable + "_ELEMENT"] = (
                    self._bmi._output_obj.output_local[count, :, :].flatten()
                )
        elif self._bmi._job_meta.grid_type == "unstructured":
            for count, variable in enumerate(variables):
                self._bmi._values[variable + "_ELEMENT"] = (
                    self._bmi._output_obj.output_local_elem[count, :].flatten()
                )
                self._bmi._values[variable + "_NODE"] = (
                    self._bmi._output_obj.output_local[count, :].flatten()
                )
        elif self._bmi._job_meta.grid_type == "hydrofabric":
            for count, variable in enumerate(variables):
                self._bmi._values[variable + "_ELEMENT"] = (
                    self._bmi._output_obj.output_global[count, :].flatten()
                )
                self._bmi._values["CAT-ID"] = self._bmi.geo_meta.element_ids_global
        else:
            raise ValueError(
                f"Unexpected grid_type: {repr(self._bmi._job_meta.grid_type)}"
            )
