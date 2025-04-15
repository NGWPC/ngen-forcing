# conus Rapid Refresh data (surface files) - modified to download only f01, f02 files


import datetime
import urllib
from urllib import request
import http
from http import cookiejar
import os
import sys
import shutil
import time
import argparse

def main(args):
    outDir = args.outDir
    lookBackHours = args.lookBackHours
    cleanBackHours = args.cleanBackHours
    lagBackHours = args.lagBackHours

    dNowUTC = datetime.datetime.utcnow()
    dNow = datetime.datetime(dNowUTC.year,dNowUTC.month,dNowUTC.day,dNowUTC.hour)
    ncepHTTP = "https://nomads.ncep.noaa.gov/pub/data/nccf/com/rap/prod"

    os.makedirs(outDir, exist_ok=True)
    print(f'RAP AnA output directory: {outDir}')

    pid = os.getpid()
    lockFile = os.path.join(outDir, "GET_Conus_RAP.lock")

    # Check for lock file
    if os.path.isfile(lockFile):
        fileLock = open(lockFile,'r')
        pid = fileLock.readline()
        print("ERROR: Another CONUS RAP Fetch Program Running. PID: " + pid + ". Please remove lockfile before attempting to execute another file extraction. Exiting script")
        sys.exit(1)
    else:
        fileLock = open(lockFile,'w')
        fileLock.write(str(os.getpid()))
        fileLock.close()

    # Clean old directories if needed
    for hour in range(cleanBackHours,lagBackHours,-1):
        dCurrent = dNow - datetime.timedelta(seconds=3600*hour)
        rapCleanDir = outDir + "/rap." + dCurrent.strftime('%Y%m%d')
        if os.path.isdir(rapCleanDir):
            print("Removing old CONUS RAP data from: " + rapCleanDir)
            shutil.rmtree(rapCleanDir)

    # Download only the first file (f00) from each forecast cycle
    for hour in range(lookBackHours,lagBackHours,-1):
        dCurrent = dNow - datetime.timedelta(seconds=3600*hour)
        
        rapOutDir = outDir + "/rap." + dCurrent.strftime('%Y%m%d')
        if not os.path.isdir(rapOutDir):
            os.mkdir(rapOutDir)

        # Construct URL for f00 and f01
        for fhr in ['01','02']:
            httpDownloadDir = ncepHTTP + "/rap." + dCurrent.strftime('%Y%m%d')
            fileDownload = "rap.t" + dCurrent.strftime('%H') + "z.awp130bgrbf" + fhr + ".grib2"
            #str(int(fhr) + 1).zfill(2)
            url = httpDownloadDir + "/" + fileDownload
            outFile = rapOutDir + "/" + fileDownload

            if os.path.isfile(outFile):
                print(f"Skipping download ... File exists: {outFile}")
                continue
                
            download_complete = False
            start_time = time.time()
            timer = 0.0
            print("Pulling CONUS RAP file: " + url)
            while(download_complete == False and timer < 600.0):
                try:
                    request.urlretrieve(url,outFile)
                    download_complete = True
                except:
                    timer = time.time() - start_time

            if(download_complete == False):
                print("Unable to retrieve: " + url)
                print("Data may not be available yet...")

    # Remove the LOCK file
    os.remove(lockFile)

def get_options():
    parser = argparse.ArgumentParser()

    parser.add_argument('outDir', type=str, help="Output directory pathway where the NOMADS data will be downloaded to")
    parser.add_argument('--lookBackHours', type=int, default=30, help="How many hours to look back for forecast data cycles")
    parser.add_argument('--cleanBackHours', type=int, default=240, help="Period between this time and the beginning of the lookback period to cleanout old data")
    parser.add_argument('--lagBackHours', type=int, default=1, help="Wait at least this long back before searching for files")

    return parser.parse_args()

if __name__ == "__main__":
    args = get_options()
    main(args)
