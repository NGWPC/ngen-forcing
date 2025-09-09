"""
BMI Forcings Engine standalone mode wrapper script.

Provides ability to run the BMI Forcings Engine pipeline in standalone mode using a single command.

example usage: python bmi_wrapper.py short_range Gage_01011000.gpkg
"""

import argparse
import os
import tempfile
from datetime import datetime, timedelta

import yaml

from git_util import print_git_info_all
from util.conda_util import run_conda_command

# Constants for time deltas
ONE_HOUR = timedelta(hours=1)
TWO_HOURS = timedelta(hours=2)
THREE_HOURS = timedelta(hours=3)
SEVEN_HOURS = timedelta(hours=7)
TWELVE_HOURS = timedelta(hours=12)
SIXTEEN_HOURS = timedelta(hours=16)
SEVENTEEN_HOURS = timedelta(hours=17)
TWENTY_TWO_HOURS = timedelta(hours=22)
FORTY_EIGHT_HOURS = timedelta(hours=48)
TEN_DAYS = timedelta(hours=240)


def execute(hyfab_name: str, forcing_config_input: str, config_input: str = None, output_path: str = None, csv_path: str = None, np: str = None):
    """
    Execute the full forcings engine BMI pipeline in standalone mode.

    Modules executed: ESMF Mesh Conversion, Forcing Extraction, Forcing Engine BMI.

    This method accepts the cycle name, hydrofabric file, configuration file path,
    output path, and number of processes to run the BMI Forcings Engine pipeline.
    It handles mesh conversion, forcing extraction, and finally the execution of the
    BMI engine using the specified parameters.

    :param hyfab_name: The full path of the hydrofabric domain file to use (e.g., /srv/data/Gage_01011000.gpkg)
    :param forcing_config: Path to forcing engine configuration file for forecast run
    :param config_input: Optional path to the wrapper config file.
    :param output_path: Optional full path to specify forcing engine output location.
    :param csv_path: Optional path for CSV output, if desired.
    :param np: Optional number of processes to use.
    :return: None
    """
    print_git_info_all()

    # Read in the configuration file to access paths and settings
    if config_input:
        config_read = config_input
    else:
        config_read = './wrapper_config.yml'

    with open(config_read, 'r') as config_file:
        config = yaml.safe_load(config_file)

    # Read in forcing engine configuration file
    with open(forcing_config_input, 'r') as forcing_config_file:
        forcing_config = yaml.safe_load(forcing_config_file)

    # Set the mesh file name based on the hydrofabric file
    base_geo_name = os.path.splitext(os.path.basename(hyfab_name))[0]
    mesh_fileName = f"{base_geo_name}_ESMF_Mesh.nc"

    # Extract paths and environment names from the configuration file
    mesh_scriptPath = config['global']['mesh_script_path']
    mesh_inPath = hyfab_name
    mesh_outPath = os.path.join(config['global']['mesh_out_base_path'], mesh_fileName)
    extraction_scriptPath = config['global']['extraction_script_path']
    # extraction_outPath = config['global']['extraction_out_path']
    bmi_scriptPath = config['global']['bmi_script_path']
    mesh_env = config['global']['mesh_env']
    extraction_env = config['global']['extract_env']
    engine_env = config['global']['engine_env']

    # Get parameters from the forcing engine config file
    refcstbdate = datetime.strptime(forcing_config['RefcstBDateProc'], "%Y%m%d%H%M")
    input_forcings = forcing_config['InputForcings'] + [f"supp{val}" for val in forcing_config['SuppPcp']]
    input_forcing_dirs = forcing_config['InputForcingDirectories'] + forcing_config['SuppPcpDirectories']
    input_horizons = forcing_config['ForecastInputHorizons']
    input_horizons = input_horizons + [input_horizons[0]] * len(forcing_config['SuppPcp'])
    ens_number = forcing_config['cfsEnsNumber']
    ana_flag = forcing_config['AnAFlag']
    look_back = forcing_config['LookBack']

    # Check if the mesh file already exists and skip conversion if it does
    if not os.path.exists(mesh_outPath):
        run_conda_command(
            env_name=mesh_env,
            command=["python", mesh_scriptPath, mesh_inPath, mesh_outPath]
        )
    else:
        print(f"ESMF mesh file already exists at {mesh_outPath}, skipping conversion.")

    # Set mapping between InputForcings codes and forcing extraction scripts
    forcing_src = {1: "NLDAS",
                   2: "NARR",
                   3: "Global/get_prod_GFS.py",
                   4: "NAM",
                   5: "CONUS/get_conus_HRRR.py",
                   6: "CONUS/get_conus_RAP.py",
                   7: "Global/get_CFSv2.py",
                   8: "WRF_ARW_HI",
                   9: "GFS_grid",
                   10: "netcdf_hour_0",
                   11: "netcdf_hour_1",
                   12: "AORC",
                   13: "NAM_Nest_HI",
                   14: "NAM_Nest_PR",
                   15: "AK_Nest",
                   16: "NAM_Nest_HI_Rad",
                   17: "NAM_Nest_PR_Rad",
                   18: "WRF_ARW_PR",
                   19: "HRRR_AK",
                   20: "AK_AnA",
                   21: "AK_AORC",
                   22: "AK_Ext_AnA",
                   23: "ERA5",
                   24: "CONUS/get_prod_NBM_Conus.py",
                   25: "NDFD",
                   26: "HRRR_15",
                   27: "NWM",
                   "supp1": "MRMS_radar",
                   "supp2": "MRMS_gage",
                   "supp3": "WRF_ARM_HI",
                   "supp4": "WRF_ARW_PR",
                   "supp5": "MRMS_Multi_CONUS",
                   "supp6": "MRMS_Multi_HI",
                   "supp7": "MRMS_SBCv2",
                   "supp8": "CONUS/get_prod_NBM_Conus.py",
                   "supp9": "NBM_AK",
                   "supp10": "MRMS_AK",
                   "supp11": "Stage_IV_AK",
                   "supp12": "Stage_IV_CONUS",
                   "supp13": "MRMS_PrecipFlag",
                   "supp14": "CFSP",
                   "supp15": "NBM_PR"
                   }

    # Set mapping between InputForcings codes and forcing extraction scripts
    forcing_ana_src = {5: "CONUS/get_conus_HRRR_AnA.py",
                       6: "CONUS/get_conus_RAP_AnA.py",
                       "supp1": "CONUS/get_conus_MRMS_MultiSensor.py",
                       "supp2": "CONUS/get_conus_MRMS_Radar.py"}

    # Set time variables for forcing engine
    b_date_dt = refcstbdate
    b_date = b_date_dt.strftime("%Y%m%d%H%M")

    if ana_flag == 0:
        start_time_dt = b_date_dt + ONE_HOUR
        end_time_dt = b_date_dt + timedelta(minutes=input_horizons[0])
    if ana_flag == 1:
        end_time_dt = b_date_dt
        start_time_dt = b_date_dt - timedelta(minutes=look_back)

    start_time = start_time_dt.strftime("%Y-%m-%d %H:%M:%S")
    end_time = end_time_dt.strftime("%Y-%m-%d %H:%M:%S")

    # Extract forcing data from appropriate sources
    for i in range(len(input_forcings)):

        # Format extraction path
        extract_outPath = input_forcing_dirs[i]

        # Set lookback hours and extraction scripts
        if ana_flag == 0:
            look_back_hours = 1
            forcing_script = forcing_src.get(input_forcings[i])
        elif ana_flag == 1:
            look_back_hours = int(look_back / 60)
            forcing_script = forcing_ana_src.get(input_forcings[i])

        # Set path to extraction script
        extract_scriptPath = os.path.join(extraction_scriptPath, forcing_script)

        # Format forcing extraction command
        command_list = list(["python", extract_scriptPath, extract_outPath,
                            start_time, f"--lookBackHours={look_back_hours}", "--lagBackHours=0"])

        if ens_number != '':
            command_list.append(f"--ensNumber={ens_number}")

        # Run forcing extraction script
        run_conda_command(
            env_name=extraction_env,
            command=command_list
        )

    # # Process based on NWM forecast cycle
    # if cycle_name == 'short_range':
    #     """
    #     The short_range cycle processes the forcing data for short-range weather forecasts, typically looking back
    #     2 hours for HRRR data and 1 hour for RAP data.

    #     - **Default lagback**: 1 hour (lookback time for RAP).
    #     - **Default lookback**: 2 hours for HRRR (using a 2-hour lookback window).

    #     The cycle will extract HRRR and RAP forcing data from the appropriate sources. This is done by extracting HRRR 
    #     data for the last 2 hours and RAP data for the last 1 hour.
    #     """
    #     # Set cycle-specific path variables
    #     configPath = forcing_config_input
    #     hrrr_extract_scriptPath = os.path.join(extraction_scriptPath, "CONUS", "get_conus_HRRR.py")
    #     hrrr_extract_outPath = os.path.join(extraction_outPath, config['short_range']['hrrr_out_path'].lstrip('/'))
    #     rap_extract_scriptPath = os.path.join(extraction_scriptPath, "CONUS", "get_conus_RAP.py")
    #     rap_extract_outPath = os.path.join(extraction_outPath, config['short_range']['rap_out_path'].lstrip('/'))

    #     # Set cycle-specific time variables for short-range forecast
    #     # TODO: Make timesteps configurable with defaults set in config file?
    #     b_date_dt = refcstbdate
    #     start_time_dt = b_date_dt + ONE_HOUR
    #     end_time_dt = start_time_dt + SEVENTEEN_HOURS
    #     b_date = b_date_dt.strftime("%Y%m%d%H%M")
    #     start_time = start_time_dt.strftime("%Y-%m-%d %H:%M:%S")
    #     end_time = end_time_dt.strftime("%Y-%m-%d %H:%M:%S")

    #     # Run the forcing_extraction script for HRRR
    #     run_conda_command(
    #         env_name=extraction_env,
    #         command=list([
    #             "python", hrrr_extract_scriptPath, hrrr_extract_outPath,
    #             start_time,
    #             "--lookBackHours=1",
    #             "--lagBackHours=0"
    #         ])
    #     )

    #     # Run the forcing_extraction script for RAP
    #     run_conda_command(
    #         env_name=extraction_env,
    #         command=list([
    #             "python", rap_extract_scriptPath, rap_extract_outPath,
    #             start_time,
    #             "--lookBackHours=1",
    #             "--lagBackHours=0"
    #         ])
    #     )

    # elif cycle_name == 'medium_range_blend':
    #     """
    #     The medium_range_blend cycle combines multiple sources for medium-range forecasting, typically using GFS and 
    #     NBM data sources.

    #     - **Default lagback**: The lagback is calculated dynamically based on the hours difference between the 
    #       current time and the base date for GFS and NBM data.
    #     - **Default lookback**: The lookback is also calculated dynamically based on the hours difference.

    #     The cycle will extract GFS data, which uses a 6-hourly cycle, and NBM data, adjusting the lagback and lookback
    #     windows based on the current time and the selected base date.
    #     """
    #     # Set cycle-specific path variables for GFS and NBM
    #     configPath = forcing_config_input
    #     gfs_extract_scriptPath = os.path.join(extraction_scriptPath, "Global", "get_prod_GFS.py")
    #     gfs_extract_outPath = os.path.join(extraction_outPath, config['medium_range_blend']['gfs_out_path'].lstrip('/'))
    #     nbm_extract_scriptPath = os.path.join(extraction_scriptPath, "CONUS", "get_prod_NBM_Conus.py")
    #     nbm_extract_outPath = os.path.join(extraction_outPath, config['medium_range_blend']['nbm_out_path'].lstrip('/'))

    #     # Set cycle-specific time variables for medium-range forecast
    #     # TODO: Make timesteps configurable with defaults set in config file?
    #     # TODO: Set end time to actual NWM cycle (10-day)

    #     # This must be a 6-hour multiple!
    #     # Therefore, the start time must be a 6-hour multiple + 1 hour
    #     b_date_dt = refcstbdate
    #     start_time_dt = b_date_dt + ONE_HOUR
    #     end_time_dt = start_time_dt + TEN_DAYS
    #     b_date = b_date_dt.strftime("%Y%m%d%H%M")
    #     start_time = start_time_dt.strftime("%Y-%m-%d %H:%M:%S")
    #     end_time = end_time_dt.strftime("%Y-%m-%d %H:%M:%S")

    #     # Run the forcing_extraction script for GFS
    #     run_conda_command(
    #         env_name=extraction_env,
    #         command=list([
    #             "python", gfs_extract_scriptPath, gfs_extract_outPath,
    #             start_time,
    #             "--lookBackHours=1",
    #             "--lagBackHours=0"
    #         ])
    #     )

    #     # Run the forcing_extraction script for NBM
    #     run_conda_command(
    #         env_name=extraction_env,
    #         command=list([
    #             "python", nbm_extract_scriptPath, nbm_extract_outPath,
    #             start_time,
    #             "--lookBackHours=1",
    #             "--lagBackHours=0"
    #         ])
    #     )

    # elif cycle_name == 'standard_ana':
    #     """
    #     The standard_ana cycle focuses on analysis runs for multiple sources like HRRR, RAP, and MRMS.

    #     - **Default lagback**: 0 (no lagback for this cycle).
    #     - **Default lookback**: The lookback is calculated based on the hours difference from the base date and is adjusted 
    #       to include a fixed 4-hour window for this cycle.

    #     This cycle runs HRRR, RAP, and MRMS MultiSensor and Radar extraction scripts, with a lagback of 0 hours and 
    #     a dynamic lookback based on the difference in hours between the current time and the base date.
    #     """
    #     # Set cycle-specific path variables for HRRR, RAP, MRMS
    #     configPath = config['standard_ana']['ana_config_path']
    #     hrrr_extract_scriptPath = os.path.join(extraction_scriptPath, "CONUS", "get_conus_HRRR_AnA.py")
    #     hrrr_extract_outPath = os.path.join(extraction_outPath, config['standard_ana']['hrrr_out_path'].lstrip('/'))
    #     rap_extract_scriptPath = os.path.join(extraction_scriptPath, "CONUS", "get_conus_RAP_AnA.py")
    #     rap_extract_outPath = os.path.join(extraction_outPath, config['standard_ana']['rap_out_path'].lstrip('/'))
    #     mrms_ms_extract_scriptPath = os.path.join(extraction_scriptPath, "CONUS", "get_conus_MRMS_MultiSensor.py")
    #     mrms_ms_extract_outPath = os.path.join(extraction_outPath, config['standard_ana']['mrms_ms_out_path'].lstrip('/'))
    #     mrms_ro_extract_scriptPath = os.path.join(extraction_scriptPath, "CONUS", "get_conus_MRMS_Radar.py")
    #     mrms_ro_extract_outPath = os.path.join(extraction_outPath, config['standard_ana']['mrms_ro_out_path'].lstrip('/'))

    #     # Set cycle-specific time variables for analysis run
    #     # TODO: Make timesteps configurable with defaults set in config file?
    #     b_date_dt = dNow - ONE_HOUR
    #     start_time_dt = b_date_dt - THREE_HOURS
    #     end_time_dt = b_date_dt - ONE_HOUR
    #     b_date = b_date_dt.strftime("%Y%m%d%H%M")
    #     start_time = start_time_dt.strftime("%Y-%m-%d %H:%M:%S")
    #     end_time = end_time_dt.strftime("%Y-%m-%d %H:%M:%S")

    #     # Calculate lookback window
    #     hours_difference = (dNow - b_date_dt).total_seconds() // 3600
    #     lagback = 0  # No lagback for this cycle
    #     lookback = hours_difference + 4  # Fixed 4-hour window for lookback

    #     # Run the forcing_extraction script for HRRR
    #     run_conda_command(
    #         env_name=extraction_env,
    #         command=list([
    #             "python", hrrr_extract_scriptPath, hrrr_extract_outPath,
    #             f"--lookBackHours={int(lookback)}",
    #             f"--lagBackHours={int(lagback)}",
    #             "--cleanBackHours=0"
    #         ])
    #     )

    #     # Run the forcing_extraction script for RAP
    #     run_conda_command(
    #         env_name=extraction_env,
    #         command=list([
    #             "python", rap_extract_scriptPath, rap_extract_outPath,
    #             f"--lookBackHours={int(lookback)}",
    #             f"--lagBackHours={int(lagback)}",
    #             "--cleanBackHours=0"
    #         ])
    #     )

    #     # Run the forcing_extraction script for MRMS_MS

    #     run_conda_command(
    #         env_name=extraction_env,
    #         command=list([
    #             "python", mrms_ms_extract_scriptPath, mrms_ms_extract_outPath,
    #             f"--lookBackHours={int(lookback)}",
    #             f"--lagBackHours={int(lagback)}",
    #         ])
    #     )

    #     # Run the forcing_extraction script for MRMS_RO
    #     run_conda_command(
    #         env_name=extraction_env,
    #         command=list([
    #             "python", mrms_ro_extract_scriptPath, mrms_ro_extract_outPath,
    #             f"--lookBackHours={int(lookback)}",
    #             f"--lagBackHours={int(lagback)}",
    #         ])
    #     )

    # elif cycle_name == "long_range":
    #     """
    #     The long_range cycle focuses on ensemble forecasting for long-term predictions (typically a 30-day range).
    #     It extracts data from the CFSv2 model, with adjustments to the lookback and lagback windows based on the current 
    #     time and the specific cycle times.

    #     - **Default lagback**: The lagback is calculated dynamically based on the hours difference between the current time
    #       and the base date (`b_date_dt`). The lagback is typically 1 hour.
    #     - **Default lookback**: The lookback is also calculated dynamically based on the hours difference.

    #     This cycle runs data extraction for the CFSv2 model, which uses a 6-hour cycle, and adjusts the lagback and lookback
    #     windows accordingly.
    #     """
    #     # TODO: alter for NWM cycle - ensemble forecasting, 30 day

    #     # Set cycle-specific path variables for CFS
    #     configPath = forcing_config_input
    #     cfs_extract_scriptPath = os.path.join(extraction_scriptPath, "Global", "get_CFSv2.py")
    #     cfs_extract_outPath = os.path.join(extraction_outPath, config['long_range']['cfs_out_path'].lstrip('/'))

    #     # Set cycle-specific time variables for long-range forecast (ensemble forecasting)
    #     # This checks the current hour and adjusts the base time (b_date) accordingly
    #     # TODO: Make timesteps configurable with defaults set in config file?
    #     # TODO: Set end time to actual NWM cycle (30-day)
    #     if dNowUTC.hour in [1, 2, 7, 8, 13, 14, 19, 20]:
    #         b_date_dt = dNow - THREE_HOURS
    #     else:
    #         b_date_dt = dNow - SEVEN_HOURS

    #     b_date_dt = b_date_dt.replace(hour=(b_date_dt.hour // 6) * 6, minute=0, second=0, microsecond=0)
    #     start_time_dt = b_date_dt + ONE_HOUR
    #     end_time_dt = start_time_dt + FORTY_EIGHT_HOURS
    #     b_date = b_date_dt.strftime("%Y%m%d%H%M")
    #     start_time = start_time_dt.strftime("%Y-%m-%d %H:%M:%S")
    #     end_time = end_time_dt.strftime("%Y-%m-%d %H:%M:%S")

    #     # Calculate lookback window since CFS is on a 6-hourly cycle
    #     hours_difference = (dNow - b_date_dt).total_seconds() // 3600
    #     lagback = hours_difference - 1  # Default lagback of 1 hour
    #     lookback = hours_difference

    #     # Run the forcing_extraction script for CFS
    #     run_conda_command(
    #         env_name=extraction_env,
    #         command=list([
    #             "python", cfs_extract_scriptPath, cfs_extract_outPath,
    #             f"--lookBackHours={int(lookback)}",
    #             f"--lagBackHours={int(lagback)}",
    #         ])
    #     )

    # elif cycle_name == 'extended_ana':
    #     """
    #     The extended_ana cycle performs analysis runs using multiple sources like HRRR, RAP, and Stage-IV data.

    #     - **Default lagback**: 0 (no lagback for this cycle).
    #     - **Default lookback**: The lookback is calculated based on the hours difference from the base date (`b_date_dt`).
    #       Additionally, 18 hours are added for this specific analysis cycle.

    #     The cycle runs HRRR, RAP, and Stage-IV extraction scripts with specific handling for radar data from Stage-IV.
    #     """
    #     # Set cycle-specific path variables for HRRR, RAP, and Stage-IV
    #     configPath = config['extended_ana']['ana_config_path']
    #     hrrr_extract_scriptPath = os.path.join(extraction_scriptPath, "CONUS", "get_conus_HRRR_AnA.py")
    #     hrrr_extract_outPath = os.path.join(extraction_outPath, config['extended_ana']['hrrr_out_path'].lstrip('/'))
    #     rap_extract_scriptPath = os.path.join(extraction_scriptPath, "CONUS", "get_conus_RAP_AnA.py")
    #     rap_extract_outPath = os.path.join(extraction_outPath, config['extended_ana']['rap_out_path'].lstrip('/'))
    #     stage_iv_extract_scriptPath = os.path.join(extraction_scriptPath, "CONUS", "get_conus_StageIV.py")
    #     stage_iv_extract_outPath = os.path.join(extraction_outPath, config['extended_ana']['stage_iv_out_path'].lstrip('/'))

    #     # Set cycle-specific time variables for extended analysis run
    #     # TODO: Make timesteps configurable with defaults set in config file?

    #     b_date_dt = dNow - ONE_HOUR
    #     start_time_dt = b_date_dt - SIXTEEN_HOURS
    #     end_time_dt = b_date_dt - ONE_HOUR
    #     b_date = b_date_dt.strftime("%Y%m%d%H%M")
    #     start_time = start_time_dt.strftime("%Y-%m-%d %H:%M:%S")
    #     end_time = end_time_dt.strftime("%Y-%m-%d %H:%M:%S")

    #     # Calculate lookback window since this is an AnA run
    #     hours_difference = (dNow - b_date_dt).total_seconds() // 3600
    #     lagback = 0  # No lagback for this cycle
    #     lookback = hours_difference + 18  # Fixed 18-hour window for lookback

    #     # Run the forcing_extraction script for HRRR
    #     run_conda_command(
    #         env_name=extraction_env,
    #         command=list([
    #             "python", hrrr_extract_scriptPath, hrrr_extract_outPath,
    #             f"--lookBackHours={int(lookback)}",
    #             f"--lagBackHours={int(lagback)}",
    #             "--cleanBackHours=0"
    #         ])
    #     )

    #     # Run the forcing_extraction script for RAP
    #     run_conda_command(
    #         env_name=extraction_env,
    #         command=list([
    #             "python", rap_extract_scriptPath, rap_extract_outPath,
    #             f"--lookBackHours={int(lookback)}",
    #             f"--lagBackHours={int(lagback)}",
    #             "--cleanBackHours=0"
    #         ])
    #     )

    #     # Run the forcing_extraction script for Stage-IV (Radar data)
    #     run_conda_command(
    #         env_name=extraction_env,
    #         command=list([
    #             "python", stage_iv_extract_scriptPath, stage_iv_extract_outPath,
    #             f"--lookBackHours={int(lookback)}",
    #             f"--lagBackHours={int(lagback)}"
    #         ])
    #     )

    # elif cycle_name == 'pr_short_range':
    #     """
    #     The pr_short_range cycle focuses on Puerto Rico’s weather forecast for short-range time periods, using NAM, NBM,
    #     and ARW data sources.

    #     - **Default lagback**: The lagback is calculated dynamically based on the hours difference from the current time and
    #       the base date (`b_date_dt`).
    #     - **Default lookback**: The lookback is calculated dynamically, depending on the current time.

    #     This cycle calculates the nearest forecast cycle based on the current hour (either 6 or 18). It extracts NAM, NBM, 
    #     and ARW data sources and processes them based on the calculated lookback and lagback windows.
    #     """
    #     # Set cycle-specific path variables for Puerto Rico
    #     configPath = config['pr_short_range']['pr_sr_config_path']
    #     nam_extract_scriptPath = os.path.join(extraction_scriptPath, "Puerto_Rico", "get_prod_NAM_Nest_Puerto_Rico.py")
    #     nam_extract_outPath = os.path.join(extraction_outPath, config['pr_short_range']['nam_out_path'].lstrip('/'))
    #     nbm_extract_scriptPath = os.path.join(extraction_scriptPath, "Puerto_Rico", "get_prod_NBM_Puerto_Rico.py")
    #     nbm_extract_outPath = os.path.join(extraction_outPath, config['pr_short_range']['nbm_out_path'].lstrip('/'))
    #     arw_extract_scriptPath = os.path.join(extraction_scriptPath, "Puerto_Rico", "get_ARW_Puerto_Rico.py")
    #     arw_extract_outPath = os.path.join(extraction_outPath, config['pr_short_range']['arw_out_path'].lstrip('/'))

    #     # Function to determine the nearest forecast cycle for Puerto Rico
    #     dNow = datetime.now(timezone.utc)
    #     b_date_dt = get_nearest_cycle(dNow, cycles=[6, 18])
    #     start_time_dt = b_date_dt + ONE_HOUR
    #     end_time_dt = start_time_dt + SEVENTEEN_HOURS

    #     # Convert times to strings for command use
    #     b_date = b_date_dt.strftime("%Y%m%d%H%M")
    #     start_time = start_time_dt.strftime("%Y-%m-%d %H:%M:%S")
    #     end_time = end_time_dt.strftime("%Y-%m-%d %H:%M:%S")

    #     # Calculate the hours difference for lagback and lookback calculations
    #     hours_difference = (dNow - b_date_dt).total_seconds() // 3600
    #     lagback = hours_difference - 1
    #     lookback = hours_difference

    #     # Run the forcing_extraction script for NAM
    #     run_conda_command(
    #         env_name=extraction_env,
    #         command=list([
    #             "python", nam_extract_scriptPath, nam_extract_outPath,
    #             f"--lookBackHours={int(lookback)}",
    #             f"--lagBackHours={int(lagback)}"
    #         ])
    #     )

    #     # Run the forcing_extraction script for NBM
    #     run_conda_command(
    #         env_name=extraction_env,
    #         command=list([
    #             "python", nbm_extract_scriptPath, nbm_extract_outPath,
    #             f"--lookBackHours={int(lookback)}",
    #             f"--lagBackHours={int(lagback)}",
    #             "--cleanBackHours=0"
    #         ])
    #     )

    #     # Run the forcing_extraction script for ARW
    #     run_conda_command(
    #         env_name=extraction_env,
    #         command=list([
    #             "python", arw_extract_scriptPath, arw_extract_outPath,
    #             f"--lookBackHours={int(lookback)}",
    #             f"--lagBackHours={int(lagback)}",
    #             "--cleanBackHours=0"
    #         ])
    #     )

    # elif cycle_name == 'hi_short_range':
    #     """
    #     The hi_short_range cycle processes weather forecasts for Hawaii, using NAM and ARW data sources.

    #     - **Default lagback**: The lagback is calculated dynamically based on the hours difference from the current time and
    #       the base date (`b_date_dt`).
    #     - **Default lookback**: The lookback is calculated dynamically, depending on the current time.

    #     This cycle calculates the nearest forecast cycle based on the current hour (either 0 or 12). It processes NAM and
    #     ARW data sources using the calculated lagback and lookback windows.
    #     """
    #     # Set cycle-specific path variables for Hawaii
    #     configPath = config['hi_short_range']['hi_sr_config_path']
    #     nam_extract_scriptPath = os.path.join(extraction_scriptPath, "Hawaii", "get_prod_NAM_Nest_Hawaii.py")
    #     nam_extract_outPath = os.path.join(extraction_outPath, config['hi_short_range']['nam_out_path'].lstrip('/'))
    #     arw_extract_scriptPath = os.path.join(extraction_scriptPath, "Hawaii", "get_ARW_Hawaii.py")
    #     arw_extract_outPath = os.path.join(extraction_outPath, config['hi_short_range']['arw_out_path'].lstrip('/'))

    #     # Function to determine the nearest forecast cycle for Hawaii
    #     dNow = datetime.now(timezone.utc)
    #     b_date_dt = get_nearest_cycle(dNow, cycles=[0, 12])
    #     start_time_dt = b_date_dt + ONE_HOUR
    #     end_time_dt = start_time_dt + SEVENTEEN_HOURS

    #     # Convert times to strings for command use
    #     b_date = b_date_dt.strftime("%Y%m%d%H%M")
    #     start_time = start_time_dt.strftime("%Y-%m-%d %H:%M:%S")
    #     end_time = end_time_dt.strftime("%Y-%m-%d %H:%M:%S")

    #     # Calculate the hours difference for lagback and lookback calculations
    #     hours_difference = (dNow - b_date_dt).total_seconds() // 3600
    #     lagback = hours_difference - 1
    #     lookback = hours_difference

    #     # Run the forcing_extraction script for NAM
    #     run_conda_command(
    #         env_name=extraction_env,
    #         command=list([
    #             "python", nam_extract_scriptPath, nam_extract_outPath,
    #             f"--lookBackHours={int(lookback)}",
    #             f"--lagBackHours={int(lagback)}",
    #             "--cleanBackHours=0"
    #         ])
    #     )

    #     # Run the forcing_extraction script for ARW
    #     run_conda_command(
    #         env_name=extraction_env,
    #         command=list([
    #             "python", arw_extract_scriptPath, arw_extract_outPath,
    #             f"--lookBackHours={int(lookback)}",
    #             f"--lagBackHours={int(lagback)}",
    #             "--cleanBackHours=0"
    #         ])
    #     )

    # elif cycle_name == "ak_short_range":
    #     """
    #     The ak_short_range cycle focuses on weather forecasting for Alaska, using HRRR and NBM data sources.
    #     The nearest forecast cycle is determined based on the current time, similar to the other regional cycles.
    #     This cycle processes multiple forecast hours and adjusts the lookback and lagback windows accordingly.
    #     """
    #     # Set cycle-specific path variables for Alaska
    #     configPath = config['ak_short_range']['ak_sr_config_path']
    #     hrrr_extract_scriptPath = os.path.join(extraction_scriptPath, "Alaska", "get_Alaska_HRRR.py")
    #     hrrr_extract_outPath = os.path.join(extraction_outPath, config['ak_short_range']['hrrr_out_path'].lstrip('/'))
    #     nbm_extract_scriptPath = os.path.join(extraction_scriptPath, "Alaska", "get_prod_NBM_Alaska.py")
    #     nbm_extract_outPath = os.path.join(extraction_outPath, config['ak_short_range']['nbm_out_path'].lstrip('/'))

    #     # Get the current time in UTC and calculate the base date for the cycle
    #     dNow = datetime.now(timezone.utc)
    #     # Set specific cycle for Alaska
    #     cycles = [0, 3, 6, 9, 12, 15, 18, 21]
    #     b_date_dt = get_nearest_cycle(dNow, cycles)
    #     start_time_dt = b_date_dt + ONE_HOUR
    #     end_time_dt = start_time_dt + SEVENTEEN_HOURS

    #     # Convert times to strings for command use
    #     b_date = b_date_dt.strftime("%Y%m%d%H%M")
    #     start_time = start_time_dt.strftime("%Y-%m-%d %H:%M:%S")
    #     end_time = end_time_dt.strftime("%Y-%m-%d %H:%M:%S")

    #     # Calculate the hours difference for lagback and lookback calculations
    #     hours_difference = (dNow - b_date_dt).total_seconds() // 3600
    #     lagback = hours_difference - 1
    #     lookback = hours_difference

    #     # Run the forcing_extraction script for HRRR
    #     run_conda_command(
    #         env_name=extraction_env,
    #         command=list([
    #             "python", hrrr_extract_scriptPath, hrrr_extract_outPath,
    #             f"--lookBackHours={int(lookback)}",
    #             f"--lagBackHours={int(lagback)}",
    #             "--cleanBackHours=0"
    #         ])
    #     )

    #     # Run the forcing_extraction script for NBM
    #     run_conda_command(
    #         env_name=extraction_env,
    #         command=list([
    #             "python", nbm_extract_scriptPath, nbm_extract_outPath,
    #             f"--lookBackHours={int(lookback)}",
    #             f"--lagBackHours={int(lagback)}",
    #             "--cleanBackHours=0"
    #         ])
    #     )

    # else:
    #     raise Exception(
    #         "valid cycle options: short_range, medium_range_blend, standard_ana, long_range, extended_ana, pr_short_range, hi_short_range, ak_short_range")

    output_path = (
        output_path or tempfile.NamedTemporaryFile(suffix=".nc", delete=False).name if csv_path
        else None
    )

    # Build command for the BMI engine
    command = []

    # Optional: mpirun prefix
    if np is not None:
        command += ["mpirun", "-np", str(np)]

    # Main Python call
    command += [
        "python", bmi_scriptPath,
        f"-config_path={forcing_config_input}",
        f"-b_date={b_date}",
        f"-geogrid={mesh_outPath}",
    ]

    # Optional: -output_path
    if output_path:
        command.append(f"-output_path={output_path}")

    # Always add start/end time
    command += [start_time, end_time]

    # Now run using utility
    run_conda_command(
        env_name=engine_env,
        command=command
    )

    if csv_path:
        # Get the directory of the current Python module
        module_dir = os.path.dirname(os.path.abspath(__file__))
        # Build the full path to the script
        post_process_script = os.path.join(module_dir, "post_process", "netcdf_to_csv.py")

        run_conda_command(
            env_name=engine_env,
            command=[
                "python", post_process_script, f"{output_path}", f"{csv_path}"]
        )


def get_nearest_cycle(dt: datetime, cycles: list[int], buffer_hours: int = 3) -> datetime:
    """
    Find the nearest forecast cycle based on the given cycles list. This function calculates
    the nearest forecast cycle time by checking the current hour and selecting the closest
    cycle from a predefined list of cycles. It considers both the forward and backward distance
    to the cycles. If the calculated cycle time is too close to the current time (within the
    specified buffer), it adjusts by going back to the previous cycle (to ensure enough lead time
    for forecast).

    Forecast cycles represent hourly intervals (e.g., 3-hour, 6-hour, etc.) to which the
    current time is rounded. The function finds the nearest cycle time, and if the forecast
    cycle time is too close to the current time, it adjusts the time to the previous cycle
    to avoid forecasting too soon.

    :param dt: The current datetime to round to the nearest forecast cycle.
    :param cycles: A list of cycle hours (e.g., [3, 6, 12]) representing the forecast intervals.
    :param buffer_hours: The minimum number of hours to buffer when determining the nearest cycle.
    :return: A datetime object corresponding to the nearest cycle time.
    """
    current_hour = dt.hour

    # Find the nearest cycle by checking the remainder when dividing the current hour by each cycle.
    nearest_cycle = min(cycles, key=lambda cycle: min((current_hour - cycle) % 24, (cycle - current_hour) % 24))

    # Create a datetime object for the nearest cycle, using the same date but adjusting the hour
    cycle_dt = dt.replace(hour=nearest_cycle, minute=0, second=0, microsecond=0)

    # If the cycle is too close to the current time or in the future (based on the buffer), go back one cycle
    if (dt - cycle_dt).total_seconds() / 3600 < buffer_hours:
        cycle_dt -= timedelta(hours=12)  # Adjust to the previous cycle if the calculated one is too close

    return cycle_dt


def main():
    """
    Main function to handle command-line execution.

    This function parses command-line arguments and calls the execute() method.
    It allows the script to be run both programmatically or from the command line.

    :return: None
    """
    # Parse command-line arguments
    args = get_options()

    # Call execute with parsed arguments
    execute(
        hyfab_name=args.hyfab_name,
        forcing_config_input=args.forcing_config_input,
        config_input=args.config_input,
        output_path=args.output_path,
        np=args.np,
        csv_path=args.csv_path
    )


def get_options():
    """
    Function to accept and parse arguments.

    This function handles the command-line argument parsing and returns the parsed arguments.

    :return: An argparse.Namespace object containing the parsed arguments
    """
    # TODO keyword arguments should start with --
    parser = argparse.ArgumentParser()
    parser.add_argument('hyfab_name',
                        type=str,
                        help='Path to hydrofabric file for conversion to ESMF. Ex: /srv/data/Gage_01011000.gpkg')
    parser.add_argument('forcing_config_input',
                        type=str,
                        help='Path to forcing engine configuration file for forecast run')
    parser.add_argument('-output_path',
                        type=str,
                        help='Full path for nc output file. If omitted, and -csv_path is provided, output_path will be set to /tmp/temp.nc.')
    parser.add_argument('-csv_path',
                        type=str,
                        help='Path for csv output, if desired. If omitted, no csv files will be created.')
    parser.add_argument('-config_input',
                        type=str,
                        help='Path to wrapper config file. If omitted, defaults to ./wrapper_config.yml')
    parser.add_argument('-np',
                        type=int,
                        help='The number of processes to use when executing the forcing engine. If omitted, will default to one process.')

    return parser.parse_args()


if __name__ == '__main__':
    main()
