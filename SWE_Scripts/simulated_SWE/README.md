# Script Descriptions

convert_sneqv.py: This script parses multiple catchment-scale .csv output files from ngen, extracting 06z sneqv (snow water equivalent, or SWE) values for the date(s) specified. It writes these values to a NetCDF output file for ease of use with the simulated_swe_mapper.py script.

simulated_swe_mapper.py: This script reads from a NetCDF file (it assumes a format identical to that created by convert_sneqv.py), and then plots SWE values on a map for the date specified. Each catchment polygon is filled with the simulated SWE value for that catchment, since these represent lumped values. 

# Script Usage

A conda environment.yml file has been including. While using a conda environment is optional, this file lists required packages.

#### convert_sneqv.py: 
python convert_sneqv.py [-h] csv_directory dates [dates ...] output

Arguments:
csv_directory: Required. A string that points to the path that contains the ngen catchment-scale .csv output files to parse.
dates: Required. A string representing a date to parse. For example '2015-12-01'. Multiple dates can be entered, but at least one date is required.
output: Required. A string representing the full absolute or relative path to desired output file, for example './example.nc'

#### simulated_swe_mapper.py:
python simulated_swe_mapper.py [-h] [--output_file OUTPUT_FILE] netcdf_file gpkg_file date

Arguments:
netcdf_file: Required. A string that points to the NetCDF file that contains SWE values. Assumes that the NetCDF file was created by convert_sneqv.py, or has the same format/structure.
gpkg_file: Required. A string that points to the .gpkg file containing basin geographic information. (Hydrofabric file).
date: Required. A string representing the date you wish to map. Ex: '2015-12-01'
output_file: Optional. A string that points to an output file path, ex: './output.png' If no output_file argument is provided, no file will be saved. Instead, the terminal will attempt to display the image using xdg. 

# Examples

#### convert_sneqv.py
python convert_sneqv.py -h
python convert_sneqv.py '/data/ngen_out/01123000/' '2015-12-01' '2015-12-02' '/data/sneqv/01123000_swe.nc'

#### simulated_swe_mapper.py
python simulated_swe_mapper.py -h
python simulated_swe_mapper.py '/data/sneqv/01123000_swe.nc' '/data/geopackages/gages-01123000.gpkg' '2015-12-01' --output_file '/data/maps/swe_20151201_01123000.png'
