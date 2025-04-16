# Quick and dirty program to pull down operational 
# conus Rapid Refresh data (surface files).

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
    print('get_conus_RAP args:', vars(args))
    outDir = args.outDir
    lookBackHours = args.lookBackHours
    cleanBackHours = args.cleanBackHours
    lagBackHours = args.lagBackHours

    dNowUTC = datetime.now(timezone.utc)
    dNow = datetime(dNowUTC.year, dNowUTC.month, dNowUTC.day, dNowUTC.hour)
    ncepHTTP = "https://nomads.ncep.noaa.gov/pub/data/nccf/com/rap/prod"

    os.makedirs(outDir, exist_ok=True)
    print(f'RAP output directory: {outDir}')

    lockFile = os.path.join(outDir, "GET_Conus_RAP.lock")

    # First check to see if lock file exists, if it does, throw error message as
    # another pull program is running. If lock file not found, create one with PID.
    if os.path.isfile(lockFile):
        fileLock = open(lockFile, 'r')
        pid = fileLock.readline()
        print(
            f"ERROR: Another CONUS RAP Fetch Program running - PID: {pid}.  Please remove lockfile at {lockFile} before attempting to execute another file extraction. Exiting script")
        sys.exit(1)
    else:
        fileLock = open(lockFile, 'w')
        fileLock.write(str(os.getpid()))
        fileLock.close()

    for hour in range(cleanBackHours, lagBackHours, -1):
        # Calculate current hour.
        dCurrent = dNow - timedelta(seconds=3600 * hour)

        # Compose path to directory containing data.
        rapCleanDir = os.path.join(outDir, "rap." + dCurrent.strftime('%Y%m%d'))

        # Check to see if directory exists. If it does, remove it. 
        if os.path.isdir(rapCleanDir):
            print("Removing old CONUS RAP data from: " + rapCleanDir)
            shutil.rmtree(rapCleanDir)

    # Now that cleaning is done, download files within the download window. 
    for hour in range(lookBackHours, lagBackHours, -1):
        print('current hour:', hour)
        # Calculate current hour.
        dCurrent = dNow - timedelta(seconds=3600 * hour)

        rapOutDir = os.path.join(outDir, "rap." + dCurrent.strftime('%Y%m%d'))
        if not os.path.isdir(rapOutDir):
            os.mkdir(rapOutDir)

        if dCurrent.hour == 3 or dCurrent.hour == 9 or dCurrent.hour == 15 or dCurrent.hour == 21:
            # RAP cycles every six hours produce forecasts out to 39 hours.
            nFcstHrs = 39
        else:
            # Otherwise, 21-hour forecasts.
            nFcstHrs = 21

        for hrDownload in range(0, nFcstHrs + 1):
            print('hrDownload:', hrDownload)
            httpDownloadDir = os.path.join(ncepHTTP, "rap." + dCurrent.strftime('%Y%m%d'))
            fileDownload = "rap.t" + dCurrent.strftime('%H') + "z.awp130bgrbf" + str(hrDownload).zfill(2) + ".grib2"
            url = os.path.join(httpDownloadDir, fileDownload)
            outFile = os.path.join(rapOutDir, fileDownload)
            if os.path.isfile(outFile):
                print(f"Skipping download ... File already exists: {outFile}")
                continue
            download_complete = False
            start_time = time.time()
            timer = 0.0
            print("Pulling CONUS RAP file: " + url)
            while not download_complete and timer < 600.0:
                try:
                    request.urlretrieve(url, outFile)
                    download_complete = True
                except Exception:
                    timer = time.time() - start_time

            if not download_complete:
                print("Unable to retrieve: " + url)
                print("Data may not available yet...")

    # Remove the LOCK file.
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
