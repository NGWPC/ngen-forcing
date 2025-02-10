import pandas as pd
import glob
import os
import re
from datetime import datetime
import numpy as np
import xarray as xr
import argparse

def read_sneqv_values_from_dir(directory, dates):
   """
   Extract 06Z sneqv values for specified dates from all catchments
   
   Args:
       directory (str): Path to directory containing CSV files
       dates (list): List of dates in 'YYYY-MM-DD' format
       
   Returns:
           - catchment_ids: numpy array of catchment IDs
           - times: numpy array of datetime objects
           - data: 2D numpy array (time x catchment) of sneqv values
   """
   
   # Convert dates to datetime and add 06z timestep
   times = np.array([datetime.strptime(f"{date} 06:00:00", "%Y-%m-%d %H:%M:%S")
                    for date in dates])
   
   # Get all catchment files
   pattern = os.path.join(directory, "cat-*.csv")
   csv_files = glob.glob(pattern)
   
   # Extract catchment IDs from filenames
   catchment_ids = np.array([
       int(re.search(r'cat-(\d+)\.csv', os.path.basename(f)).group(1))
       for f in csv_files if re.search(r'cat-(\d+)\.csv', os.path.basename(f))
   ])
   
   # Initialize data array - 2d (times, ids)
   data = np.full((len(times), len(catchment_ids)), np.nan)
   
   # Parse SWE values from each file
   for idx, file_path in enumerate(csv_files):
       try:
           df = pd.read_csv(file_path)
           # Use lower() to make headers case-independent
           df.columns = df.columns.str.lower()
           if 'sneqv' not in df.columns:
               continue
           
           # Use only selected date/times    
           df['time'] = pd.to_datetime(df['time'])
           mask = df['time'].isin(times)
           if not mask.any():
               continue
           
           # Extract and store specified values    
           values = df.loc[mask, 'sneqv'].values
           data[:, idx] = values
           
       except Exception as e:
           print(f"Error processing {file_path}: {e}")
           continue

   return catchment_ids, times, data

def write_to_netcdf(catchment_ids, times, data, output_file):
   """
   Write the extracted sneqv values to a NetCDF file with dates as strings
   """
   
   # Use xarray to construct the dataset for writing
   ds = xr.Dataset(
       data_vars={
           "sneqv": (["date", "catchment"], data)
       },
       coords={
           "date": [t.strftime('%Y-%m-%d') for t in times],
           "catchment": catchment_ids
       }
   )
   
   # write to netcdf output file
   ds.to_netcdf(output_file)

def get_options():
    """Read and pass in command-line arguments"""
    parser = argparse.ArgumentParser()
    parser.add_argument('csv_directory', type=str, 
                        help="Path that contains csv output files.")
    parser.add_argument('dates', nargs='+',
                        help="Dates to process ex: '2015-12-01' '2015-12-02'")
    parser.add_argument('output', type=str,
                        help="Desired path for output file.")
    return parser.parse_args()

if __name__ == "__main__":
   args = get_options()
   directory = args.csv_directory
   dates = args.dates
   output = args.output
   
   catchment_ids, times, data = read_sneqv_values_from_dir(directory, dates)
   print(f"Processed {len(catchment_ids)} catchments")
   #print(f"Time steps: {times}")
   #print(f"Data shape: {data.shape}")
   
   write_to_netcdf(catchment_ids, times, data, output)
