# Quick and dirty program to pull down operational 
# conus HRRR data (surface files).

# Logan Karsten
# National Center for Atmospheric Research
# Research Applications Laboratory

import argparse
import atexit
import os
import shutil
import sys
import time
from datetime import datetime, timezone, timedelta
from urllib import request, error


def main(args):
    print('get_conus_HRRR args:', vars(args))
    outDir = args.outDir
    lookBackHours = args.lookBackHours
    cleanBackHours = args.cleanBackHours
    lagBackHours = args.lagBackHours

    dNowUTC = datetime.now(timezone.utc)
    dNow = datetime(dNowUTC.year, dNowUTC.month, dNowUTC.day, dNowUTC.hour)
    ncepHTTP = "https://nomads.ncep.noaa.gov/pub/data/nccf/com/hrrr/prod"

    os.makedirs(outDir, exist_ok=True)
    print(f'HRRR output directory: {outDir}')

    lockFile = os.path.join(outDir, "GET_Conus_HRRR.lock")

    # Check for lock file
    if os.path.isfile(lockFile):
        with open(lockFile, 'r') as fileLock:
            pid = fileLock.readline()
        print(f"ERROR: Another CONUS HRRR Fetch Program running - PID: {pid}. "
              f"Please remove lockfile at {lockFile} before attempting to execute another file extraction. Exiting script")
        sys.exit(1)

    with open(lockFile, 'w') as fileLock:
        fileLock.write(str(os.getpid()))

    # Ensure lockfile is removed on exit
    atexit.register(lambda: os.path.isfile(lockFile) and os.remove(lockFile))

    # Clean old data
    for hour in range(cleanBackHours, lagBackHours, -1):
        # Calculate current hour.
        dCurrent = dNow - timedelta(seconds=3600 * hour)

        # Compose path to directory containing data.
        hrrrCleanDir = os.path.join(outDir, "hrrr." + dCurrent.strftime('%Y%m%d'), "conus")

        # Check to see if directory exists. If it does, remove it. 
        if os.path.isdir(hrrrCleanDir):
            print("Removing old HRRR data from: " + hrrrCleanDir)
            shutil.rmtree(hrrrCleanDir)

    # Download new data
    for hour in range(lookBackHours, lagBackHours, -1):
        print('Current hour offset:', hour)
        dCurrent = dNow - timedelta(seconds=3600 * hour)
        hrrrOutDir = os.path.join(outDir, "hrrr." + dCurrent.strftime('%Y%m%d'), "conus")
        os.makedirs(hrrrOutDir, exist_ok=True)

        nFcstHrs = 36 if dCurrent.hour % 6 == 0 else 18

        for hrDownload in range(0, nFcstHrs + 1):
            print('hrDownload:', hrDownload)
            httpDownloadDir = os.path.join(ncepHTTP, "hrrr." + dCurrent.strftime('%Y%m%d'), "conus")
            fileDownload = "hrrr.t" + dCurrent.strftime('%H') + "z.wrfsfcf" + str(hrDownload).zfill(2) + ".grib2"
            url = os.path.join(httpDownloadDir, fileDownload)
            outFile = os.path.join(hrrrOutDir, fileDownload)

            if os.path.isfile(outFile):
                print(f"Skipping download ... File already exists: {outFile}")
                continue

            print(f"Pulling HRRR file: {url}")
            max_retry_seconds = 600
            retry_interval = 30
            max_attempts = max_retry_seconds // retry_interval

            attempt = 0
            download_complete = False

            while not download_complete and attempt < max_attempts:
                try:
                    print(f"Attempt {attempt + 1} of {max_attempts}...")
                    request.urlretrieve(url, outFile)
                    download_complete = True
                    print(f"Download complete: {outFile}")
                except error.HTTPError as e:
                    print(f"HTTPError {e.code} while downloading {url}: {e.reason}")
                except error.URLError as e:
                    print(f"URLError while downloading {url}: {e.reason}")
                except Exception as e:
                    print(f"General error while downloading {url}: {e}")
                if not download_complete:
                    attempt += 1
                    time.sleep(retry_interval)

            if not download_complete:
                print("❌ Unable to retrieve after retries: " + url)
                print("⚠️  Data may not be available yet...")

    print("✅ HRRR data retrieval complete.")


def get_options():
    parser = argparse.ArgumentParser()

    parser.add_argument('outDir', type=str, help="Output directory pathway where the NOMADS data will be downloaded to")
    parser.add_argument('--lookBackHours', type=int, default=30, help="How many hours to look back for forecast data cycles")
    parser.add_argument('--cleanBackHours', type=int, default=240,
                        help="Period between this time and the beginning of the lookback period to clean out old data")
    parser.add_argument('--lagBackHours', type=int, default=1, help="Wait at least this long back before searching for files")

    return parser.parse_args()


if __name__ == "__main__":
    args = get_options()
    main(args)
