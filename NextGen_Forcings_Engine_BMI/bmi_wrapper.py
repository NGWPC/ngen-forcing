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
    forcing_src = {3: "Global/get_prod_GFS.py",
                   5: "CONUS/get_conus_HRRR.py",
                   6: "CONUS/get_conus_RAP.py",
                   7: "Global/get_CFSv2.py",
                   13: "Hawaii/get_prod_NAM_Nest_Hawaii.py",
                   14: "Puerto_Rico/get_prod_NAM_Nest_Puerto_Rico.py",
                   19: "Alaska/get_Alaska_HRRR.py",
                   24: "CONUS/get_prod_NBM_Conus.py",
                   "supp8": "CONUS/get_prod_NBM_Conus.py",
                   "supp9": "Alaska/get_prod_NBM_Alaska.py",
                   "supp11": "Alaska/get_Alaska_StageIV.py",
                   "supp12": "CONUS/get_conus_StageIV.py",
                   "supp15": "Puerto_Rico/get_prod_NBM_Puerto_Rico.py"
                   }

    # Set mapping between InputForcings codes and forcing extraction scripts
    forcing_ana_src = {5: "CONUS/get_conus_HRRR_AnA.py",
                       6: "CONUS/get_conus_RAP_AnA.py",
                       13: "Hawaii/get_prod_NAM_Nest_Hawaii.py",
                       14: "Puerto_Rico/get_prod_NAM_Nest_Puerto_Rico.py",
                       19: "Alaska/get_Alaska_HRRR.py",
                       20: "Alaska/get_Alaska_HRRR_AnA.py",
                       "supp1": "CONUS/get_conus_MRMS_Radar.py",
                       "supp2": "CONUS/get_conus_MRMS_MultiSensor.py",
                       "supp6": "Hawaii/get_MRMS_MultiSensor_Hawaii.py",
                       "supp10": "Alaska/get_MRMS_MultiSensor_Alaska.py",
                       "supp11": "Alaska/get_Alaska_StageIV.py",
                       "supp12": "CONUS/get_conus_StageIV.py"}

    # Set time variables for forcing engine
    b_date_dt = refcstbdate
    b_date = b_date_dt.strftime("%Y%m%d%H%M")

    if ana_flag == 0:
        start_time_dt = b_date_dt + ONE_HOUR
        end_time_dt = b_date_dt + timedelta(minutes=input_horizons[0])
    if ana_flag == 1:
        end_time_dt = b_date_dt - ONE_HOUR
        start_time_dt = b_date_dt - timedelta(minutes=(look_back))

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
            forcing_start_time = (b_date_dt + ONE_HOUR).strftime("%Y-%m-%d %H:%M:%S")
        elif ana_flag == 1:
            look_back_hours = int(look_back / 60) + 3
            forcing_start_time = (b_date_dt + TWO_HOURS).strftime("%Y-%m-%d %H:%M:%S")
            forcing_script = forcing_ana_src.get(input_forcings[i])

        # Set path to extraction script
        extract_scriptPath = os.path.join(extraction_scriptPath, forcing_script)

        # Format forcing extraction command
        command_list = list(["python", extract_scriptPath, extract_outPath,
                            forcing_start_time, f"--lookBackHours={look_back_hours}", "--lagBackHours=0"])

        if ens_number != '':
            command_list.append(f"--ensNumber={ens_number}")

        # Run forcing extraction script
        run_conda_command(
            env_name=extraction_env,
            command=command_list
        )

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
