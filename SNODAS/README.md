# Overview
This directory contains scripts for downloading and processing SNODAS data from the National Snow and Ice Data Center (NSIDC).

# Script Description
snodas_downloader.sh: This script downloads unmasked SNODAS data from the NSIDC server. Only the Snow Water Equivalent files are saved.
snodas_convert.py: A rough but portable utility script for converting binary SNODAS files to NetCDF. Assumes use with snodas_downloader.sh. 
snodas_mapper.py: A mapping script, which plots basin-scale SNODAS SWE values and writes to .png files.

# Script Usage
#### snodas_downloader.sh
snodas_downloader.sh [-h|--help] [YEAR as yyyy] [MONTH as mm] [DAY as dd]

Providing no options will download SNODAS data for all years.
Providing YEAR, or YEAR and MONTH, or YEAR and MONTH and DAY, will download SNODAS data for the specified year or year/day or year/month/day.
-h, --help: Prints usage 

#### snodas_convert.py

python snodas_convert.py

This script needs to be run from the unmasked/ directory (used by snodas_downloader.sh). Either move or copy this script to that directory. It also assumes the directory strcture matches that used by the snodas_downloader.sh script. 

Ensure that Docker is available/active, and that you have the correct permissions to use it. The script will use a GDAL image, pulling it if necessary. Using a container image is intended to help with portability, and isolate GDAL to limit potential conflicts.

This script is configured only for use with SNODAS data from 01OCT2013 or later. Older data has already been archived, but requires different GDAL settings.

#### snodas_mapper.py

python snodas_mapper.py [-h] [--gpkg_file GPKG_FILE] [--output_file OUTPUT_FILE] [--plot_type PLOT_TYPE] netcdf_file

-h, --help: prints usage

netcdf_file is mandatory. This can be an s3 location or a local file.

If no plot_type is provided, the script will default to the raw visualization. The "catchment" option plots catchment-averaged values, while "raw" plots raw data. 

If no gpkg_file is provided, the script will map the whole domain, which is not recommended in combination with the catchment plot_type. Otherwise, the geopackage file indicated will be used to subset the domain.

If no output_file is provided, the script will open an image, but not save it.

An environment.yml file has been included, which lists required packages, and can be used to create a conda environment capable of utilizing the script. However, if all required packages are installed locally, this is not required.

# Examples
#### snodas_downloader.sh
snodas_downloader.sh --help
snodas_downloader.sh
snodas_downloader.sh 2024
snodas_downloader.sh 2024 01
snodas_downloader.sh 2024 01 20
#### snodas_convert.py
python snodas_convert.py
#### snodas_mapper.py
python snodas_mapper.py -h
python snodas_mapper.py --gpkg_file '/data/geopackages/gages-13240000.gpkg' --output_file '/data/snodas/13240000_c.nc' --plot_type 'catchment' 's3://ngwpc-forcing/snodas_nc/zz_ssm11034tS__T0001TTNATS2009123105HP001.nc'
