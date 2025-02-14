# Script Descriptions

run_swe.py: This script acts as a wrapper script, coordinating all other mapping scripts in this directory. It accepts and passes all necessary arguments, and it runs each script in a way that enables shared colorbar scaling.

swe_minmax.py: This is a utility script that is not intended to be used in standalone mode. It stores global vmin/vmax values so that each map has the same scale, facilitating comparison. 

convert_swe.py: This script parses multiple catchment-scale .csv output files from ngen, extracting 06z SWE (snow water equivalent) values for the date(s) specified. It writes these values to a NetCDF output file for ease of use with the simulated_swe_mapper.py script. It can be executed in standalone mode, or via the run_swe.py wrapper (recommended). 

simulated_swe_mapper.py: This script reads from a NetCDF file (it assumes a format identical to that created by convert_swe.py), and then plots SWE values on a map for the date specified. Each catchment polygon is filled with the simulated SWE value for that catchment, since these represent lumped values. It can be executed in standalone mode, or via the run_swe.py wrapper (recommended). 

snodas_mapper.py: A mapping script, which plots basin-scale SNODAS SWE values and writes to .png files. It can be executed in standalone mode, or via the run_swe.py wrapper (recommended). 

# Script Usage

A conda environment.yml file has been including. While using a conda environment is optional, this file lists required packages.

#### run_Swe.py:


#### convert_swe.py: 
python convert_swe.py [-h] csv_directory dates [dates ...] output

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

#### snodas_mapper.py

python snodas_mapper.py [-h] [--gpkg_file GPKG_FILE] [--output_file OUTPUT_FILE] [--plot_type PLOT_TYPE] netcdf_file

-h, --help: prints usage

netcdf_file is mandatory. This can be an s3 location or a local file.

If no plot_type is provided, the script will default to the raw visualization. The "catchment" option plots catchment-averaged values, while "raw" plots raw data. 

If no gpkg_file is provided, the script will map the whole domain, which is not recommended in combination with the catchment plot_type. Otherwise, the geopackage file indicated will be used to subset the domain.

If no output_file is provided, the script will open an image, but not save it.

An environment.yml file has been included, which lists required packages, and can be used to create a conda environment capable of utilizing the script. However, if all required packages are installed locally, this is not required.

# Examples

#### convert_swe.py
python convert_swe.py -h
python convert_swe.py '/data/ngen_out/01123000/' '2015-12-01' '2015-12-02' '/data/sneqv/01123000_swe.nc'

#### simulated_swe_mapper.py
python simulated_swe_mapper.py -h
python simulated_swe_mapper.py '/data/sneqv/01123000_swe.nc' '/data/geopackages/gages-01123000.gpkg' '2015-12-01' --output_file '/data/maps/swe_20151201_01123000.png'

#### snodas_mapper.py
python snodas_mapper.py -h
python snodas_mapper.py --gpkg_file '/data/geopackages/gages-13240000.gpkg' --output_file '/data/snodas/13240000_c.nc' --plot_type 'catchment' 's3://ngwpc-forcing/snodas_nc/zz_ssm11034tS__T0001TTNATS2009123105HP001.nc'
