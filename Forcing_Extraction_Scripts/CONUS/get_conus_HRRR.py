# Quick and dirty program to pull down operational 
# conus HRRR data (surface files).

# Logan Karsten
# National Center for Atmospheric Research
# Research Applications Laboratory

import argparse
import os
import shutil
import sys
import time
from datetime import datetime, timezone, timedelta
from urllib import request


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
        fileLock = open(lockFile, 'r')
        pid = fileLock.readline()
        print(f"ERROR: Another CONUS HRRR Fetch Program running - PID: {pid}.  Please remove lockfile at {lockFile} before attempting to execute another file extraction. Exiting script")
        sys.exit(1)
    else:
        fileLock = open(lockFile, 'w')
        fileLock.write(str(os.getpid()))
        fileLock.close()

    for hour in range(cleanBackHours, lagBackHours, -1):
        # Calculate current hour.
        dCurrent = dNow - timedelta(seconds=3600 * hour)

        # Compose path to directory containing data.
        hrrrCleanDir = os.path.join(outDir, "hrrr." + dCurrent.strftime('%Y%m%d'), "conus")

        # Check to see if directory exists. If it does, remove it. 
        if os.path.isdir(hrrrCleanDir):
            print("Removing old HRRR data from: " + hrrrCleanDir)
            shutil.rmtree(hrrrCleanDir)

    # Now that cleaning is done, download files within the download window. 
    for hour in range(lookBackHours, lagBackHours, -1):
        print('current hour:', hour)
        # Calculate current hour.
        dCurrent = dNow - timedelta(seconds=3600 * hour)

        hrrrOutDir = os.path.join(outDir, "hrrr." + dCurrent.strftime('%Y%m%d'), "conus")
        if not os.path.isdir(hrrrOutDir):
            os.makedirs(hrrrOutDir)

        if dCurrent.hour % 6 == 0:
            # HRRR cycles every six hours produce to forecasts out to 36 hours.
            nFcstHrs = 36
        else:
            # Otherwise, 18-hour forecasts.
            nFcstHrs = 18

        for hrDownload in range(0, nFcstHrs + 1):
            print('hrDownload:', hrDownload)
            httpDownloadDir = os.path.join(ncepHTTP, "hrrr." + dCurrent.strftime('%Y%m%d'), "conus")
            fileDownload = "hrrr.t" + dCurrent.strftime('%H') + "z.wrfsfcf" + str(hrDownload).zfill(2) + ".grib2"
            url = os.path.join(httpDownloadDir, fileDownload)
            outFile = os.path.join(hrrrOutDir, fileDownload)

            if os.path.isfile(outFile):
                print(f"Skipping download ... File already exists: {outFile}")
                continue

            download_complete = False
            start_time = time.time()
            timer = 0.0
            print("Pulling HRRR file: " + url)
            while not download_complete and timer < 600.0:
                try:
                    print('downloading', url)
                    request.urlretrieve(url, outFile)
                    download_complete = True
                except Exception:
                    timer = time.time() - start_time

            if not download_complete:
                print("Unable to retrieve: " + url)
                print("Data may not be available yet...")

    # Remove the LOCK file
    os.remove(lockFile)


def get_options():
    parser = argparse.ArgumentParser()

    parser.add_argument('outDir', type=str, help="Output directory pathway where the NOMADS data will be downloaded to")
    parser.add_argument('--lookBackHours', type=int, default=30, help="How many hours to look back for forecast data cycles")
    parser.add_argument('--cleanBackHours', type=int, default=240,
                        help="Period between this time and the beginning of the lookback period to cleanout old data")
    parser.add_argument('--lagBackHours', type=int, default=1, help="Wait at least this long back before searching for files")

    return parser.parse_args()


if __name__ == "__main__":
    args = get_options()
    main(args)
