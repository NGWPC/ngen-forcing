import argparse
import importlib.util
import yaml
from datetime import datetime, timedelta
from pathlib import Path
from Forcing_Extraction_Scripts.forecast_download_base import ForecastDownloader, FixedFileDownloader, ScrapedFileDownloader


def retrieve_forcing(cfg: dict):
    """
    Download forecast forcing data based on requested sources in the forcing engine configuration file

    :param cfg: dictionary of forcing engine config parameters
    """
    # # TESTING
    fp = '/ngwpc/run_ngen/default/noah_topmodel/01123000/Input/forcing_config/short_range_config.yml'
    with open(fp) as cfg_file:
        cfg = yaml.safe_load(cfg_file)

    # Get parameters from the forcing engine config file
    refcstbdate = datetime.strptime(cfg['RefcstBDateProc'], "%Y%m%d%H%M")
    input_forcings = cfg['InputForcings'] + [f"supp{val}" for val in cfg['SuppPcp']]
    input_forcing_dirs = cfg['InputForcingDirectories'] + cfg['SuppPcpDirectories']
    input_horizons = cfg['ForecastInputHorizons']
    input_horizons = input_horizons + [input_horizons[0]] * len(cfg['SuppPcp'])
    ens_number = cfg['cfsEnsNumber']
    ana_flag = cfg['AnAFlag']
    look_back = cfg['LookBack']
    extraction_scriptPath = "/ngen-app/ngen-forcing/Forcing_Extraction_Scripts"

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

    # Extract forcing data from appropriate sources
    for i in range(len(input_forcings)):

        # Format extraction path
        extract_outPath = input_forcing_dirs[i]

        # Set lookback hours and extraction scripts
        if ana_flag == 0:
            look_back_hours = 1
            forcing_script = forcing_src.get(input_forcings[i])
            forcing_start_time = (refcstbdate + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        elif ana_flag == 1:
            look_back_hours = int(look_back / 60) + 3
            forcing_start_time = (refcstbdate + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
            forcing_script = forcing_ana_src.get(input_forcings[i])

        # Set path to extraction script
        extract_scriptPath = Path(extraction_scriptPath) / forcing_script

        # Dynamically import extraction module
        mod_name = f"forcing_{Path(extract_scriptPath).stem}"
        spec = importlib.util.spec_from_file_location(mod_name, extract_scriptPath)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Retrieve correct ForecastDownloader subclass from extraction script
        base_classes = (ForecastDownloader, FixedFileDownloader, ScrapedFileDownloader)
        downloader_class = next(
            obj for name, obj in vars(module).items()
            if isinstance(obj, type) and issubclass(obj, base_classes) and obj is not base_classes
        )

        # Format forcing extraction command
        downloader = downloader_class(
            out_dir=extract_outPath,
            start_time=forcing_start_time,
            lookback_hours=look_back_hours,
            lagback_hours=0,
            ens_number=int(ens_number) if ens_number != "" else None
        )

        # Run the download
        downloader.run()


def main():
    parser = argparse.ArgumentParser(description="Download forecast forcing data")
    parser.add_argument("cfg", help="Dictionary containing contents of forcing configuration yaml file")
    args = parser.parse_args()

    retrieve_forcing(args.cfg)


if __name__ == "__main__":
    main()
