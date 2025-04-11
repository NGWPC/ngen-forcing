"""
BMI Forcings Engine standalone mode wrapper script.

Provides ability to run the BMI Forcings Engine pipeline in standalone mode using a single command.

example usage: python bmi_wrapper.py short_range Gage_01011000.gpkg
"""

import argparse
from datetime import datetime, timezone, timedelta

import os
import subprocess
import tempfile

import yaml

from git_util import print_git_info_all

ONE_HOUR = timedelta(hours=1)
TWO_HOURS = timedelta(hours=2)
THREE_HOURS = timedelta(hours=3)
SEVEN_HOURS = timedelta(hours=7)
TWELVE_HOURS = timedelta(hours=12)
SIXTEEN_HOURS = timedelta(hours=16)
SEVENTEEN_HOURS = timedelta(hours=17)
TWENTY_TWO_HOURS = timedelta(hours=22)
FORTY_EIGHT_HOURS = timedelta(hours=48)


def execute(args):
    """
    Execute the full forcings engine BMI pipeline in standalone mode.

    Modules executed: ESMF Mesh Conversion, Forcing Extraction, Forcing Engine BMI

    args:
        cycle_name (str): The NWM Forecast cycle to execute (ie: short_range)
        hyfab_name (str): The full path of the hydrofabric domain file to use (ie: /srv/data/Gage_01011000.gpkg)
        -config_input (str): Optional path to the wrapper config file.
        -output_path (str): Optional full path to specify forcing engine output location.
        -np (str): Optional number of processes to use.
    """

    # read in user-provided arguments and initialize variables
    cycle_name = args.cycle_name
    hyfab_name = args.hyfab_name
    config_input = args.config_input
    num_processes = args.np

    output_path = (
        args.output_path or
        tempfile.NamedTemporaryFile(suffix=".nc", delete=False).name if args.csv_path
        else None
    )

    # read in config file
    if config_input:
        config_read = config_input
    else:
        config_read = './wrapper_config.yml'
    with open(config_read, 'r') as config_file:
        config = yaml.safe_load(config_file)

    # use the Gage_######## string to construct ESMF mesh filename
    base_geo_name = os.path.splitext(os.path.basename(hyfab_name))[0]
    mesh_fileName = f"{base_geo_name}_ESMF_Mesh.nc"

    # Reading path variables from config file
    mesh_scriptPath = config['global']['mesh_script_path']
    mesh_inPath = hyfab_name
    mesh_outPath = os.path.join(config['global']['mesh_out_base_path'], mesh_fileName)
    extraction_scriptPath = config['global']['extraction_script_path']
    extraction_outPath = config['global']['extraction_out_path']
    bmi_scriptPath = config['global']['bmi_script_path']
    mesh_env = config['global']['mesh_env']
    extraction_env = config['global']['extract_env']
    engine_env = config['global']['engine_env']

    # Get the current time in UTC
    dNowUTC = datetime.now(timezone.utc)
    dNow = datetime(dNowUTC.year, dNowUTC.month, dNowUTC.day, dNowUTC.hour)

    if not os.path.exists(mesh_outPath):
        # Execute hyfab to ESMF mesh conversion
        cmd0 = [
            "conda", "run", "-n", mesh_env,
            "python", mesh_scriptPath, mesh_inPath, mesh_outPath
        ]
        subprocess.run(cmd0, check=True)
    else:
        print(f"ESMF mesh file already exists at {mesh_outPath}, skipping conversion.")

    # Process based on NWM forecast cycle
    if cycle_name == "short_range":

        # Set cycle-specific path variables
        configPath = config['short_range']['sr_config_path']
        hrrr_extract_scriptPath = os.path.join(extraction_scriptPath, "CONUS", "get_conus_HRRR.py")
        hrrr_extract_outPath = os.path.join(extraction_outPath, config['short_range']['hrrr_out_path'].lstrip('/'))
        rap_extract_scriptPath = os.path.join(extraction_scriptPath, "CONUS", "get_conus_RAP.py")
        rap_extract_outPath = os.path.join(extraction_outPath, config['short_range']['rap_out_path'].lstrip('/'))

        # set cycle-specific time variables
        # TODO: Make timesteps configurable with defaults set in config file?
        b_date_dt = dNow - TWO_HOURS
        start_time_dt = b_date_dt + ONE_HOUR
        end_time_dt = start_time_dt + SEVENTEEN_HOURS
        # create strings from datetime objects for use in commands
        b_date = b_date_dt.strftime("%Y%m%d%H%M")
        start_time = start_time_dt.strftime("%Y-%m-%d %H:%M:%S")
        end_time = end_time_dt.strftime("%Y-%m-%d %H:%M:%S")

        # Run the forcing_extraction script for HRRR
        cmd1 = [
            "conda", "run", "-n", extraction_env,
            "python", hrrr_extract_scriptPath, hrrr_extract_outPath,
            "--lookBackHours=2",
            "--lagBackHours=1"
        ]
        subprocess.run(cmd1, check=True)

        # Run the forcing_extraction script for RAP
        cmd2 = [
            "conda", "run", "-n", extraction_env,
            "python", rap_extract_scriptPath, rap_extract_outPath,
            "--lookBackHours=2",
            "--lagBackONE_HOUR"
        ]
        subprocess.run(cmd2, check=True)

    elif cycle_name == 'medium_range_blend':

        # Set cycle-specific path variables
        configPath = config['medium_range_blend']['mrb_config_path']
        gfs_extract_scriptPath = os.path.join(extraction_scriptPath, "Global", "get_prod_GFS.py")
        gfs_extract_outPath = os.path.join(extraction_outPath, config['medium_range_blend']['gfs_out_path'].lstrip('/'))
        nbm_extract_scriptPath = os.path.join(extraction_scriptPath, "CONUS", "get_prod_NBM.py")
        nbm_extract_outPath = os.path.join(extraction_outPath, config['medium_range_blend']['nbm_out_path'].lstrip('/'))

        # set cycle-specific time variables
        # TODO: Make timesteps configurable with defaults set in config file?
        # TODO: Set end time to actual NWM cycle (10-day)

        b_date_dt = dNow - THREE_HOURS
        print(f"b_date_dt orig: {b_date_dt}")
        b_date_dt = b_date_dt.replace(hour=(b_date_dt.hour // 6) * 6, minute=0, second=0, microsecond=0)
        print(f"b_date_dt new: {b_date_dt}")
        start_time_dt = b_date_dt + ONE_HOUR
        end_time_dt = start_time_dt + SEVENTEEN_HOURS
        # create strings from datetime objects for use in commands
        b_date = b_date_dt.strftime("%Y%m%d%H%M")
        start_time = start_time_dt.strftime("%Y-%m-%d %H:%M:%S")
        end_time = end_time_dt.strftime("%Y-%m-%d %H:%M:%S")

        print(f"start_time: {start_time}")
        print(f"end_time: {end_time}")

        # calculate lookback window since GFS is on a 6-hourly cycle
        hours_difference = (dNow - b_date_dt).total_seconds() / 3600
        lagback = hours_difference - 1
        lookback = hours_difference

        print(f"lookback: {lookback}")
        print(f"lagback: {lagback}")

        # Run the forcing_extraction script for GFS
        cmd1 = [
            "conda", "run", "-n", extraction_env,
            "python", gfs_extract_scriptPath, gfs_extract_outPath,
            f"--lookBackHours={int(lookback)}",
            f"--lagBackHours={int(lagback)}"
        ]
        subprocess.run(cmd1, check=True)

        # Run the forcing_extraction script for NBM

        cmd2 = [
            "conda", "run", "-n", extraction_env,
            "python", nbm_extract_scriptPath, nbm_extract_outPath,
            f"--lookBackHours={int(lookback)}",
            f"--lagBackHours={int(lagback)}"
        ]
        subprocess.run(cmd2, check=True)

    elif cycle_name == 'standard_ana':

        # Set cycle-specific path variables
        configPath = config['standard_ana']['ana_config_path']
        hrrr_extract_scriptPath = os.path.join(extraction_scriptPath, "CONUS", "get_conus_HRRR_AnA.py")
        hrrr_extract_outPath = os.path.join(extraction_outPath, config['standard_ana']['hrrr_out_path'].lstrip('/'))
        rap_extract_scriptPath = os.path.join(extraction_scriptPath, "CONUS", "get_conus_RAP_AnA.py")
        rap_extract_outPath = os.path.join(extraction_outPath, config['standard_ana']['rap_out_path'].lstrip('/'))
        mrms_ms_extract_scriptPath = os.path.join(extraction_scriptPath, "CONUS", "get_conus_MRMS_MultiSensor.py")
        mrms_ms_extract_outPath = os.path.join(extraction_outPath, config['standard_ana']['mrms_ms_out_path'].lstrip('/'))
        mrms_ro_extract_scriptPath = os.path.join(extraction_scriptPath, "CONUS", "get_conus_MRMS_Radar.py")
        mrms_ro_extract_outPath = os.path.join(extraction_outPath, config['standard_ana']['mrms_ro_out_path'].lstrip('/'))

        # set cycle-specific time variables
        # TODO: Make timesteps configurable with defaults set in config file?

        b_date_dt = dNow - ONE_HOUR
        start_time_dt = b_date_dt + THREE_HOURS
        end_time_dt = b_date_dt + ONE_HOUR
        # create strings from datetime objects for use in commands
        b_date = b_date_dt.strftime("%Y%m%d%H%M")
        start_time = start_time_dt.strftime("%Y-%m-%d %H:%M:%S")
        end_time = end_time_dt.strftime("%Y-%m-%d %H:%M:%S")

        # calculate lookback window since this is an AnA run
        hours_difference = (dNow - b_date_dt).total_seconds() / 3600
        lagback = 0
        lookback = hours_difference + 4

        # Run the forcing_extraction script for HRRR
        cmd1a = [
            "conda", "run", "-n", extraction_env,
            "python", hrrr_extract_scriptPath, hrrr_extract_outPath,
            f"--lookBackHours={int(lookback)}",
            f"--lagBackHours={int(lagback)}",
            "--cleanBackHours=0"
        ]
        subprocess.run(cmd1a, check=True)

        # Run the forcing_extraction script for RAP

        cmd1b = [
            "conda", "run", "-n", extraction_env,
            "python", rap_extract_scriptPath, rap_extract_outPath,
            f"--lookBackHours={int(lookback)}",
            f"--lagBackHours={int(lagback)}",
            "--cleanBackHours=0"
        ]
        subprocess.run(cmd1b, check=True)

        # Run the forcing_extraction script for MRMS_MS
        cmd2a = [
            "conda", "run", "-n", extraction_env,
            "python", mrms_ms_extract_scriptPath, mrms_ms_extract_outPath,
            f"--lookBackHours={int(lookback)}",
            f"--lagBackHours={int(lagback)}"
        ]
        subprocess.run(cmd2a, check=True)

        # Run the forcing_extraction script for MRMS_RO

        cmd2b = [
            "conda", "run", "-n", extraction_env,
            "python", mrms_ro_extract_scriptPath, mrms_ro_extract_outPath,
            f"--lookBackHours={int(lookback)}",
            f"--lagBackHours={int(lagback)}"
        ]
        subprocess.run(cmd2b, check=True)

    elif cycle_name == "long_range":

        # TODO: alter for NWM cycle -  ensemble forecasting, 30 day

        # Set cycle-specific path variables
        configPath = config['long_range']['lr_config_path']
        cfs_extract_scriptPath = os.path.join(extraction_scriptPath, "Global", "get_CFSv2.py")
        cfs_extract_outPath = os.path.join(extraction_outPath, config['long_range']['cfs_out_path'].lstrip('/'))

        # set cycle-specific time variables
        # TODO: Make timesteps configurable with defaults set in config file?
        # TODO: Set end time to actual NWM cycle (30-day)

        if dNowUTC.hour in [1, 2, 7, 8, 13, 14, 19, 20]:
            b_date_dt = dNow - THREE_HOURS
        else:
            b_date_dt = dNow - SEVEN_HOURS

        b_date_dt = b_date_dt.replace(hour=(b_date_dt.hour // 6) * 6, minute=0, second=0, microsecond=0)
        start_time_dt = b_date_dt + ONE_HOUR
        end_time_dt = start_time_dt + FORTY_EIGHT_HOURS
        # create strings from datetime objects for use in commands
        b_date = b_date_dt.strftime("%Y%m%d%H%M")
        start_time = start_time_dt.strftime("%Y-%m-%d %H:%M:%S")
        end_time = end_time_dt.strftime("%Y-%m-%d %H:%M:%S")

        # calculate lookback window since CFS is on a 6-hourly cycle
        hours_difference = (dNow - b_date_dt).total_seconds() / 3600
        lagback = hours_difference - 1
        lookback = hours_difference

        # Run the forcing_extraction script for CFS
        cmd1 = [
            "conda", "run", "-n", extraction_env,
            "python", cfs_extract_scriptPath, cfs_extract_outPath,
            f"--lookBackHours={int(lookback)}",
            f"--lagBackHours={int(lagback)}"
        ]
        subprocess.run(cmd1, check=True)

    elif cycle_name == 'extended_ana':

        # Set cycle-specific path variables
        configPath = config['extended_ana']['ana_config_path']
        hrrr_extract_scriptPath = os.path.join(extraction_scriptPath, "CONUS", "get_conus_HRRR_AnA.py")
        hrrr_extract_outPath = os.path.join(extraction_outPath, config['extended_ana']['hrrr_out_path'].lstrip('/'))
        rap_extract_scriptPath = os.path.join(extraction_scriptPath, "CONUS", "get_conus_RAP_AnA.py")
        rap_extract_outPath = os.path.join(extraction_outPath, config['extended_ana']['rap_out_path'].lstrip('/'))
        stage_iv_extract_scriptPath = os.path.join(extraction_scriptPath, "CONUS", "get_conus_StageIV.py")
        stage_iv_extract_outPath = os.path.join(extraction_outPath, config['extended_ana']['stage_iv_out_path'].lstrip('/'))

        # set cycle-specific time variables
        # TODO: Make timesteps configurable with defaults set in config file?

        b_date_dt = dNow - ONE_HOUR
        start_time_dt = b_date_dt - SIXTEEN_HOURS
        print(f"start_time_dt: {start_time_dt}")
        end_time_dt = b_date_dt - ONE_HOUR
        print(f"end_time_dt: {end_time_dt}")
        # create strings from datetime objects for use in commands
        b_date = b_date_dt.strftime("%Y%m%d%H%M")
        start_time = start_time_dt.strftime("%Y-%m-%d %H:%M:%S")
        end_time = end_time_dt.strftime("%Y-%m-%d %H:%M:%S")

        # calculate lookback window since this is an AnA run
        hours_difference = (dNow - b_date_dt).total_seconds() / 3600
        lagback = 0
        lookback = hours_difference + 18
        print(f"lagback = {lagback}")
        print(f"lookback = {lookback}")

        # Run the forcing_extraction script for HRRR
        cmd1a = [
            "conda", "run", "-n", extraction_env,
            "python", hrrr_extract_scriptPath, hrrr_extract_outPath,
            f"--lookBackHours={int(lookback)}",
            f"--lagBackHours={int(lagback)}",
            "--cleanBackHours=0"
        ]
        subprocess.run(cmd1a, check=True)

        # Run the forcing_extraction script for RAP

        cmd1b = [
            "conda", "run", "-n", extraction_env,
            "python", rap_extract_scriptPath, rap_extract_outPath,
            f"--lookBackHours={int(lookback)}",
            f"--lagBackHours={int(lagback)}",
            "--cleanBackHours=0"
        ]
        subprocess.run(cmd1b, check=True)

        # Run the forcing_extraction script for stage_iv
        cmd2 = [
            "conda", "run", "-n", extraction_env,
            "python", stage_iv_extract_scriptPath, stage_iv_extract_outPath,
            f"--lookBackHours={int(lookback)}",
            f"--lagBackHours={int(lagback)}"
        ]
        subprocess.run(cmd2, check=True)

    elif cycle_name == 'pr_short_range':

        # Set cycle-specific path variables
        configPath = config['pr_short_range']['pr_sr_config_path']
        nam_extract_scriptPath = os.path.join(extraction_scriptPath, "Puerto_Rico", "get_prod_NAM_Nest_PuertoRico.py")
        nam_extract_outPath = os.path.join(extraction_outPath, config['pr_short_range']['nam_out_path'].lstrip('/'))
        nbm_extract_scriptPath = os.path.join(extraction_scriptPath, "Puerto_Rico", "get_prod_NBM_Puerto_Rico.py")
        nbm_extract_outPath = os.path.join(extraction_outPath, config['pr_short_range']['nbm_out_path'].lstrip('/'))
        arw_extract_scriptPath = os.path.join(extraction_scriptPath, "Puerto_Rico", "get_ARW_Puerto_Rico.py")
        arw_extract_outPath = os.path.join(extraction_outPath, config['pr_short_range']['arw_out_path'].lstrip('/'))

        def get_nearest_cycle(dt, buffer_hours=3):
            cycles = [6, 18]
            current_hour = dt.hour

            # Find nearest cycle
            nearest_cycle = min(cycles, key=lambda x: min((current_hour - x) % 24, (x - current_hour) % 24))

            # Create datetime for nearest cycle
            cycle_dt = dt.replace(hour=nearest_cycle, minute=0, second=0, microsecond=0)

            # If cycle is in future or too recent, go back one cycle (12 hours)
            if (dt - cycle_dt).total_seconds() / 3600 < buffer_hours:
                cycle_dt -= TWELVE_HOURS

            return cycle_dt

        dNow = datetime.now(timezone.utc)
        b_date_dt = get_nearest_cycle(dNow)
        start_time_dt = b_date_dt + ONE_HOUR
        end_time_dt = start_time_dt + SEVENTEEN_HOURS

        # Rest of your code remains the same
        b_date = b_date_dt.strftime("%Y%m%d%H%M")
        start_time = start_time_dt.strftime("%Y-%m-%d %H:%M:%S")
        end_time = end_time_dt.strftime("%Y-%m-%d %H:%M:%S")
        hours_difference = (dNow - b_date_dt).total_seconds() / 3600

        lagback = hours_difference - 1
        lookback = hours_difference

        # Run the forcing_extraction script for NAM
        cmd1 = [
            "conda", "run", "-n", extraction_env,
            "python", nam_extract_scriptPath, nam_extract_outPath,
            f"--lookBackHours={int(lookback)}",
            f"--lagBackHours={int(lagback)}",
            "--cleanBackHours=0"
        ]
        subprocess.run(cmd1, check=True)

        # Run the forcing_extraction script for NBM
        cmd2a = [
            "conda", "run", "-n", extraction_env,
            "python", nbm_extract_scriptPath, nbm_extract_outPath,
            f"--lookBackHours={int(lookback)}",
            f"--lagBackHours={int(lagback)}",
            "--cleanBackHours=0"
        ]
        subprocess.run(cmd2a, check=True)

        # Run the forcing_extraction script for ARW
        cmd2b = [
            "conda", "run", "-n", extraction_env,
            "python", arw_extract_scriptPath, arw_extract_outPath,
            f"--lookBackHours={int(lookback)}",
            f"--lagBackHours={int(lagback)}",
            "--cleanBackHours=0"
        ]
        subprocess.run(cmd2b, check=True)

    elif cycle_name == 'hi_short_range':

        # Set cycle-specific path variables
        configPath = config['hi_short_range']['hi_sr_config_path']
        nam_extract_scriptPath = os.path.join(extraction_scriptPath, "Hawaii", "get_prod_NAM_Nest_Hawaii.py")
        nam_extract_outPath = os.path.join(extraction_outPath, config['hi_short_range']['nam_out_path'].lstrip('/'))
        arw_extract_scriptPath = os.path.join(extraction_scriptPath, "Hawaii", "get_ARW_Hawaii.py")
        arw_extract_outPath = os.path.join(extraction_outPath, config['hi_short_range']['arw_out_path'].lstrip('/'))

        def get_nearest_cycle(dt, buffer_hours=3):
            cycles = [0, 12]
            current_hour = dt.hour

            # Find nearest cycle
            nearest_cycle = min(cycles, key=lambda x: min((current_hour - x) % 24, (x - current_hour) % 24))

            # Create datetime for nearest cycle
            cycle_dt = dt.replace(hour=nearest_cycle, minute=0, second=0, microsecond=0)

            # If cycle is in future or too recent, go back one cycle (12 hours)
            if (dt - cycle_dt).total_seconds() / 3600 < buffer_hours:
                cycle_dt -= TWELVE_HOURS

            return cycle_dt

        dNow = datetime.now(timezone.utc)
        b_date_dt = get_nearest_cycle(dNow)
        start_time_dt = b_date_dt + ONE_HOUR
        end_time_dt = start_time_dt + SEVENTEEN_HOURS

        # Rest of your code remains the same
        b_date = b_date_dt.strftime("%Y%m%d%H%M")
        start_time = start_time_dt.strftime("%Y-%m-%d %H:%M:%S")
        end_time = end_time_dt.strftime("%Y-%m-%d %H:%M:%S")
        hours_difference = (dNow - b_date_dt).total_seconds() / 3600

        lagback = hours_difference - 1
        lookback = hours_difference

        # Run the forcing_extraction script for NAM
        cmd1 = [
            "conda", "run", "-n", extraction_env,
            "python", nam_extract_scriptPath, nam_extract_outPath,
            f"--lookBackHours={int(lookback)}",
            f"--lagBackHours={int(lagback)}",
            "--cleanBackHours=0"
        ]
        subprocess.run(cmd1, check=True)

        # Run the forcing_extraction script for ARW
        cmd2 = [
            "conda", "run", "-n", extraction_env,
            "python", arw_extract_scriptPath, arw_extract_outPath,
            f"--lookBackHours={int(lookback)}",
            f"--lagBackHours={int(lagback)}",
            "--cleanBackHours=0"
        ]
        subprocess.run(cmd2, check=True)

    elif cycle_name == "ak_short_range":

        # Set cycle-specific path variables
        configPath = config['ak_short_range']['ak_sr_config_path']
        hrrr_extract_scriptPath = os.path.join(extraction_scriptPath, "Alaska", "get_Alaska_HRRR.py")
        hrrr_extract_outPath = os.path.join(extraction_outPath, config['ak_short_range']['hrrr_out_path'].lstrip('/'))
        nbm_extract_scriptPath = os.path.join(extraction_scriptPath, "Alaska", "get_prod_NBM_Alaska.py")
        nbm_extract_outPath = os.path.join(extraction_outPath, config['ak_short_range']['nbm_out_path'].lstrip('/'))

        # set cycle-specific time variables
        def get_nearest_cycle(dt, buffer_hours=3):
            cycles = [0, 3, 6, 9, 12, 15, 18, 21]
            current_hour = dt.hour

            # Find nearest cycle
            nearest_cycle = min(cycles, key=lambda x: min((current_hour - x) % 24, (x - current_hour) % 24))

            # Create datetime for nearest cycle
            cycle_dt = dt.replace(hour=nearest_cycle, minute=0, second=0, microsecond=0)

            # If cycle is in future or too recent, go back one cycle (12 hours)
            if (dt - cycle_dt).total_seconds() / 3600 < buffer_hours:
                cycle_dt -= TWELVE_HOURS

            return cycle_dt

        dNow = datetime.now(timezone.utc)
        b_date_dt = get_nearest_cycle(dNow)
        start_time_dt = b_date_dt + ONE_HOUR
        end_time_dt = start_time_dt + SEVENTEEN_HOURS

        # Rest of your code remains the same
        b_date = b_date_dt.strftime("%Y%m%d%H%M")
        start_time = start_time_dt.strftime("%Y-%m-%d %H:%M:%S")
        end_time = end_time_dt.strftime("%Y-%m-%d %H:%M:%S")
        hours_difference = (dNow - b_date_dt).total_seconds() / 3600

        lagback = hours_difference - 1
        lookback = hours_difference

        # Run the forcing_extraction script for HRRR
        cmd1 = [
            "conda", "run", "-n", extraction_env,
            "python", hrrr_extract_scriptPath, hrrr_extract_outPath,
            f"--lookBackHours={int(lookback)}",
            f"--lagBackHours={int(lagback)}",
            "--cleanBackHours=0"
        ]
        subprocess.run(cmd1, check=True)

        # Run the forcing_extraction script for NBM
        cmd2 = [
            "conda", "run", "-n", extraction_env,
            "python", nbm_extract_scriptPath, nbm_extract_outPath,
            f"--lookBackHours={int(lookback)}",
            f"--lagBackHours={int(lagback)}",
            "--cleanBackHours=0"
        ]
        subprocess.run(cmd2, check=True)

    else:
        print(
            "valid cycle options: short_range, medium_range_blend, standard_ana, long_range, extended_ana, pr_short_range, hi_short_range, ak_short_range")

    # run the forcing engine BMI
    if output_path:
        if num_processes is not None:
            cmd3 = [
                "conda", "run", "-n", engine_env,
                "mpirun", "-np", str(num_processes),
                "python", bmi_scriptPath, f"-config_path={configPath}", f"-b_date={b_date}", f"-geogrid={mesh_outPath}",
                f"-output_path={output_path}", start_time, end_time
            ]

        else:
            cmd3 = [
                "conda", "run", "-n", engine_env,
                "python", bmi_scriptPath, f"-config_path={configPath}", f"-b_date={b_date}", f"-geogrid={mesh_outPath}",
                f"-output_path={output_path}", start_time, end_time
            ]

    else:
        if num_processes is not None:
            cmd3 = [
                "conda", "run", "-n", engine_env,
                "mpirun", "-np", str(num_processes),
                "python", bmi_scriptPath, f"-config_path={configPath}", f"-b_date={b_date}", f"-geogrid={mesh_outPath}",
                start_time, end_time
            ]
        else:
            cmd3 = [
                "conda", "run", "-n", engine_env,
                "python", bmi_scriptPath, f"-config_path={configPath}", f"-b_date={b_date}", f"-geogrid={mesh_outPath}",
                start_time, end_time
            ]

    subprocess.run(cmd3, check=True)

    if args.csv_path:
        # Get the directory of the current Python module
        module_dir = os.path.dirname(os.path.abspath(__file__))
        # Build the full path to the script
        post_process_script = os.path.join(module_dir, "post_process", "netcdf_to_csv.py")

        cmd_0 = ["conda", "run", "-n", engine_env, "python", post_process_script, f"{output_path}", f"{args.csv_path}"]
        subprocess.run(cmd_0, check=True)


def get_options():
    """
    Function to accept and parse arguments.

    Returns an argparse object.
    """
    # TODO keyword arguments should start with --
    parser = argparse.ArgumentParser()
    parser.add_argument('cycle_name',
                        help='Name of NWM cycle. Valid names: short_range, medium_range_blend, standard_ana, long_range, extended_ana, pr_short_range')
    parser.add_argument('hyfab_name', help='Name of hydrofabric file for conversion to ESMF. Ex: Gage_01123000.gpkg')
    parser.add_argument('-output_path',
                        help='Full path for nc output file. If omitted, and -csv_path is provided, output_path will be set to /tmp/temp.nc. If neither is provided, output_path will be read in from the config file.')
    parser.add_argument('-csv_path', help='Path for csv output, if desired. If omitted, no csv files will be created.')
    parser.add_argument('-config_input', help='Path to wrapper config file. If omitted, defaults to ./wrapper_config.yml')

    parser.add_argument('-np', help='The number of processes to use when executing the forcing engine. If omitted, will default to one process.')

    return parser.parse_args()


if __name__ == '__main__':
    print_git_info_all()

    execute(get_options())
