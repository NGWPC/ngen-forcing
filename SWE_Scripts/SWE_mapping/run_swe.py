from swe_minmax import reset_minmax
import snodas_mapper
import simulated_swe_mapper
import convert_swe
import argparse

# Resets global vmin/vmax
reset_minmax()

# Converts ngen csv to netcdf
def run_convert_swe(args):
	convert_swe_args = [
		args.sim_csv_dir,
		args.date,
		args.sim_netcdf
	]
	convert_swe.main(convert_swe_args)

# Gets just vmin/vmax from the simulated SWE
def run_sim_scan(args):
	sim_scan_args = [
    	args.sim_netcdf,
    	args.gpkg_file,
   	 	args.date,
    	'--mode', 'scan'
	]
	simulated_swe_mapper.main(sim_scan_args)

# Generates SNODAS SWE map
# if SNODAS vmin/vmax are higher/lower than ngen swe range, 
# SNODAS vmin and/or vmax values will become global
def run_snodas_mapper(args):
	raw_snodas_args = [
		args.date,
		args.gpkg_file,
		args.snodas_raw_output,
		args.snodas_lumped_output
	]
	snodas_mapper.main(raw_snodas_args)

# Generates the simulated SWE map
def run_sim_swe_mapper(args):
	sim_swe_mapper_args = [
		args.sim_netcdf,
		args.gpkg_file,
		args.date,
		'--output_file', args.sim_map_output
	]
	simulated_swe_mapper.main(sim_swe_mapper_args)

def get_options():
	parser = argparse.ArgumentParser()
	parser.add_argument('date', type=str,
						help="Date to use for all plots.")
	parser.add_argument('sim_csv_dir', type=str, 
						help="Path that contains ngen swe csv files.\
						This is your ngen output directory.")
	parser.add_argument('sim_netcdf', type=str,
						help="Path for simulated swe netcdf file.\
						convert_csv writes to this file, simulated_swe_mapper\
						reads from this file.")
	parser.add_argument('gpkg_file', type=str,
						help="Path to geopackage file.")
	parser.add_argument('sim_map_output', type=str,
						help="Path where simulated swe map output saved.\
						Output will be a .png file.")
	parser.add_argument('snodas_raw_output', type=str,
						help="Path where snodas raw map output saved.\
						Output will be a .png file.")
	parser.add_argument('snodas_lumped_output', type=str,
						help="Path where snodas catchment map output saved.\
						Output will be a .png file.")
	return parser.parse_args()

if __name__ == "__main__":
	args = get_options()
	run_convert_swe(args)
	run_sim_scan(args)
	run_snodas_mapper(args)
	run_sim_swe_mapper(args)

