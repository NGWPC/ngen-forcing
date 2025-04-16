# Quick and dirty program to pull down operational 
# CFSv2 forecast data for each ensemble member, for
# each six-hour forecast going out to 30 days.

# Logan Karsten
# National Center for Atmospheric Research
# Research Applications Laboratory

import argparse
from datetime import datetime, timezone, timedelta
import os
import shutil
import sys
import time
from urllib import request


def run_cfsv2_download(outDir: str, lookBackHours: int = 24, cleanBackHours: int = 720, lagBackHours: int = 6):
    lockFile = os.path.join(outDir, "GET_CFSV2.lock")

    # First check to see if lock file exists, if it does, throw error message as
    # another pull program is running. If lock file not found, create one with PID.
    if os.path.isfile(lockFile):
        with open(lockFile, 'r') as fileLock:
            pid = fileLock.readline()
        print(f"ERROR: Another CFSv2 Fetch Program running - PID: {pid}. Please remove lockfile at {lockFile} before executing again.")
        sys.exit(1)
    else:
        with open(lockFile, 'w') as fileLock:
            fileLock.write(str(os.getpid()))

    try:
        dNowUTC = datetime.now(timezone.utc)
        dNow = dNowUTC.replace(minute=0, second=0, microsecond=0)
        fcstHrsDownload = 60
        ensNum = "01"
        ncepHTTP = "https://nomads.ncep.noaa.gov/pub/data/nccf/com/cfs/prod"

        for hour in range(cleanBackHours, lookBackHours, -1):
            # Calculate current hour.
            dCurrent = dNow - timedelta(hours=hour)
            # Go back in time and clean out any old data to conserve disk space.
            if dCurrent.hour not in {0, 6, 12, 18}:
                continue  # This is not a CFS cycle hour.

            date_str = dCurrent.strftime('%Y%m%d')
            hour_str = dCurrent.strftime('%H')

            # Try to remove deepest directory (where GRIB files go)
            cfsCleanDir = f"{outDir}/cfs.{date_str}/{hour_str}/6hrly_grib_{ensNum}"
            if os.path.isdir(cfsCleanDir):
                # print("Removing old CFS data from: " + cfsCleanDir)
                shutil.rmtree(cfsCleanDir)
                print(f"Deleted: {cfsCleanDir}")

            # If hour-level directory is empty, remove it
            cfsCleanDir = f"{outDir}/cfs.{date_str}/{hour_str}"
            if os.path.isdir(cfsCleanDir) and not os.listdir(cfsCleanDir):
                # print("Removing empty directory: " + cfsCleanDir)
                shutil.rmtree(cfsCleanDir)
                print(f"Deleted: {cfsCleanDir}")

            # If date-level directory is empty, remove it
            cfsCleanDir = f"{outDir}/cfs.{date_str}"
            if os.path.isdir(cfsCleanDir) and not os.listdir(cfsCleanDir):
                # print("Removing empty directory: " + cfsCleanDir)
                shutil.rmtree(cfsCleanDir)
                print(f"Deleted: {cfsCleanDir}")

        # Now that cleaning is done, download files within the download window.
        for hour in range(lookBackHours, lagBackHours, -1):
            dCurrent = dNow - timedelta(hours=hour)
            if dCurrent.hour not in {0, 6, 12, 18}:
                continue

            date_str = dCurrent.strftime('%Y%m%d')
            hour_str = dCurrent.strftime('%H')

            cfsOutDir = os.path.join(outDir, f"cfs.{date_str}/{hour_str}/6hrly_grib_{ensNum}")
            os.makedirs(cfsOutDir, exist_ok=True)

            httpDownloadDir = f"{ncepHTTP}/cfs.{date_str}/{hour_str}/6hrly_grib_01"

            # Download hourly files from NCEP to hour 120.
            for hrDownload in range(0, fcstHrsDownload, 6):
                dCurrent2 = dCurrent + timedelta(hours=hrDownload)
                fileDownload = f"flxf{dCurrent2.strftime('%Y%m%d%H')}.{ensNum}.{dCurrent.strftime('%Y%m%d%H')}.grb2"
                url = f"{httpDownloadDir}/{fileDownload}"
                outFile = os.path.join(cfsOutDir, fileDownload)

                if not os.path.isfile(outFile):
                    print(f"Pulling CFSv2 file: {url}")
                    download_complete = False
                    start_time = time.time()
                    timer = 0.0

                    while not download_complete and timer < 600.0:
                        try:
                            request.urlretrieve(url, outFile)
                            download_complete = True
                        except Exception:
                            timer = time.time() - start_time
                            time.sleep(2)  # Avoid hammering the server

                    if not download_complete:
                        print(f"Unable to retrieve: {url}")
                        print("Data may not be available yet...")

    finally:
        if os.path.exists(lockFile):
            os.remove(lockFile)


def get_options():
    parser = argparse.ArgumentParser()
    parser.add_argument('outDir',
                        type=str,
                        help="Output directory pathway where the NOMADS data will be downloaded to")
    parser.add_argument('--lookBackHours',
                        type=int,
                        default=24,
                        help="How many hours to look back for forecast data cycles")
    parser.add_argument('--cleanBackHours',
                        type=int,
                        default=720,
                        help="How many hours back to clean up old data")
    parser.add_argument('--lagBackHours',
                        type=int,
                        default=6,
                        help="Wait at least this long back before downloading")
    return parser.parse_args()


def main():
    args = get_options()
    run_cfsv2_download(args.outDir, args.lookBackHours, args.cleanBackHours, args.lagBackHours)


if __name__ == "__main__":
    main()
