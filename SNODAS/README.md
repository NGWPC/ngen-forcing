# Overview
This directory contains scripts for downloading and processing SNODAS data from the National Snow and Ice Data Center (NSIDC).

# Script Description
snodas_downloader.sh: This script downloads unmasked SNODAS data from the NSIDC server. Only the Snow Water Equivalent files are saved.

# Script Usage
snodas_downloader.sh [-h|--help] [YEAR as yyyy] [MONTH as mm] [DAY as dd]

Providing no options will download SNODAS data for all years.
Providing YEAR, or YEAR and MONTH, or YEAR and MONTH and DAY, will download SNODAS data for the specified year or year/day or year/month/day.
-h, --help: Prints usage 

#### Examples
snodas_downloader.sh --help
snodas_downloader.sh
snodas_downloader.sh 2024
snodas_downloader.sh 2024 01
snodas_downloader.sh 2024 01 20
