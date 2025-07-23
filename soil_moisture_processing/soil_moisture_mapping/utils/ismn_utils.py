import re
import csv
import fsspec
import pandas as pd
import geopandas as gpd

from typing import IO
from datetime import datetime
from shapely.geometry import Point
from io import BytesIO, TextIOWrapper


class ISMNDataLoader:
    @staticmethod
    def get_ismn_dirs_by_date(ismn_base_dir: str, target_date: str, direct_s3: bool = False) -> tuple:
        """
        Filter ISMN directories that contain the target date between their start and end date.

        Parameters
        ----------
        ismn_base_dir : str
            Base directory containing ISMN data (can be local path or S3 prefix).
        target_date : str
            Date in the format 'YYYY-MM-DD'.
        direct_s3 : bool
            If True, use S3 filesystem. If False, use local filesystem.

        Returns
        -------
        tuple
        -------
        matching_dirs : list[str]
            List of directories that match the target date.
        fs : fsspec.filesystem
            Filesystem object for the specified base directory.
        """
        fs = fsspec.filesystem('s3') if direct_s3 else fsspec.filesystem('file')
        pattern = re.compile(r".*_(\d{8})_(\d{8})_.*")

        try:
            target = datetime.strptime(target_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"Invalid date format: {target_date}. Expected 'YYYY-MM-DD'.")

        matching_dirs = []
        for entry in fs.ls(ismn_base_dir, detail=True):
            if entry['type'] == 'directory':
                dir_path = entry['name']
                dir_name = dir_path.rstrip('/').split('/')[-1]
                match = pattern.match(dir_name)
                if match:
                    start_str, end_str = match.groups()
                    try:
                        start_date = datetime.strptime(start_str, "%Y%m%d")
                        end_date = datetime.strptime(end_str, "%Y%m%d")
                    except ValueError:
                        continue  # skip invalid dates

                    if start_date <= target <= end_date:
                        matching_dirs.append(dir_path)

        # print(matching_dirs)
        return matching_dirs, fs

    @staticmethod
    def get_ismn_files(ismn_dir: str, fs: fsspec.filesystem) -> list:
        """
        Get all ISMN files in a given directory recursively.

        Parameters
        ----------
        ismn_dir : str
            Directory containing ISMN files.
        fs : fsspec.filesystem
            Filesystem object for the specified directory.

        Returns
        -------
        list
            List of ISMN file paths.
        """
        ismn_files = []
        for entry in fs.ls(ismn_dir, detail=True):
            if entry['type'] == 'file' and entry['name'].endswith('.stm'):
                ismn_files.append(entry['name'])
            elif entry['type'] == 'directory':
                ismn_files.extend(ISMNDataLoader.get_ismn_files(entry['name'], fs))

        # for ismn_file in ismn_files:
        #     print(ismn_file)

        return ismn_files

    @staticmethod
    def preprocess_ismn_file_to_fs_buffer(file: IO, target_date: str) -> BytesIO:
        """
        Preprocess a raw ISMN file and filter data by target_date.

        Parameters
        ----------
        file : IO
            A file-like object containing the raw ISMN data
        target_date : str
            The target date for filtering data (format: 'YYYY-MM-DD')

        Returns
        -------
        BytesIO
            A binary buffer containing the preprocessed CSV data
        """
        # compile regex to capture two datetime stamps and the rest of the line
        ts_pattern = re.compile(
            # start timestamp: yyyy/mm/dd hh:mm
            r'^(?P<start>\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2})\s+'
            # end timestamp: yyyy/mm/dd hh:mm
            r'(?P<end>\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2})\s+'
            # everything else on the line
            r'(?P<rest>.*)$'
        )

        # create a binary buffer for output
        output = BytesIO()

        # wrap the binary buffer with text mode for csv.writer
        text_buf = TextIOWrapper(output, encoding='utf-8', newline='')

        # create a csv writer that writes to the text buffer
        writer = csv.writer(text_buf)

        # track empty file
        empty_file = True

        # iterate over each raw line in the input file
        for raw in file:
            # decode bytes to string and strip trailing whitespace/newline
            line = raw.decode('utf-8').strip()

            # attempt to match the line against the timestamp regex
            m = ts_pattern.match(line)

            # skip this line if not regex match
            if not m:
                continue

            # extract start timestamp
            start_time = m.group('start')

            # extract end timestamp
            end_time = m.group('end')

            # check if target_date is between start and end dates. ignore times
            try:
                start_dt = datetime.strptime(start_time, "%Y/%m/%d %H:%M")
                end_dt = datetime.strptime(end_time, "%Y/%m/%d %H:%M")
                target_dt = datetime.strptime(target_date, "%Y-%m-%d")

                if not (start_dt.date() <= target_dt.date() <= end_dt.date()):
                    # skip this line if target_date is not in range
                    continue

            except ValueError:
                # if date parsing fails, skip the line
                continue

            # if we reach here, we have a valid line for the target date and file is not empty
            empty_file = False

            # extract rest of line
            rest_str = m.group('rest')

            # split the remainder on whitespace into exactly 11 items
            rest = rest_str.split()

            # if splitting did not yield 11 fields, skip the line
            if len(rest) != 11:
                continue
            # write the row to the csv buffer (automatically adds newline)
            writer.writerow([start_time, end_time] + rest)

        # flush the text buffer to ensure all data is written to the binary buffer
        text_buf.flush()

        # detach the text buffer from the binary buffer but keep the binary buffer open
        text_buf.detach()

        # if file had no matching lines, return None
        if empty_file:
            print(f"No data found for date {target_date} in file.")
            return None

        # rewind the binary buffer to the beginning for reading
        output.seek(0)
        # return the prepared buffer
        return output

    @staticmethod
    def get_ismn_data(ismn_files: list, target_date: str, fs: fsspec.filesystem) -> gpd.GeoDataFrame:
        """
        Load ISMN data from a list of ISMN files into a GeoDataFrame.

        Parameters
        ----------
        ismn_files : list
            List of ISMN file paths.
        fs : fsspec.filesystem
            Filesystem object for the specified files.

        Returns
        -------
        gpd.GeoDataFrame
            GeoDataFrame containing ISMN data.
        """
        column_names = [
            'utc_nominal', 'utc_actual', 'cse_id', 'network', 'station',
            'lat', 'lon', 'elevation', 'depth_from', 'depth_to',
            'value', 'ismn_flag', 'provider_flag'

        ]
        print(f"number of columns: {len(column_names)}")

        usecols = [
            'utc_nominal', 'network', 'station', 'lat', 'lon',
            'depth_from', 'depth_to', 'value', 'ismn_flag', 'provider_flag'
        ]

        all_ismn_dfs = []
        for ismn_file in ismn_files:
            with fs.open(ismn_file, 'rb') as file:
                # preprocess the file to handle whitespace and commas within fields
                processed_file = ISMNDataLoader.preprocess_ismn_file_to_fs_buffer(file, target_date)

                if processed_file is None:
                    print(f"Skipping file {ismn_file} as it has no data for date {target_date}.")
                    continue

                ismn_file_df = pd.read_csv(
                    processed_file,
                    sep=',',
                    header=None,
                    names=column_names,
                    usecols=usecols
                )
                ismn_file_df['geometry'] = ismn_file_df.apply(
                    lambda row: Point(row['lon'], row['lat']), axis=1
                )

                print(f"Processing file: {ismn_file}")
                n = min(10, len(ismn_file_df))
                print(ismn_file_df.sample(n).to_string(index=False))

                all_ismn_dfs.append(ismn_file_df)

        print(f"Total ISMN files processed: {len(all_ismn_dfs)}")
        n = min(25, len(all_ismn_dfs))
        print(all_ismn_dfs[:n])

        combined_ismn_df = pd.concat(all_ismn_dfs, ignore_index=True)
        print(f"Combined ISMN DataFrame shape: {combined_ismn_df.shape}")

        # print 10 random rows from the combined_ismn_df
        n = min(10, len(combined_ismn_df))
        print(combined_ismn_df.sample(n).to_string(index=False))

        ismn_data_gdf = gpd.GeoDataFrame(combined_ismn_df, geometry='geometry', crs='EPSG:4326')
        return ismn_data_gdf


class ISMNCalculator:
    @staticmethod
    def find_stations_basin(ismn_data_gdf, basin_geometry):
        """
        Find ISMN stations within a given basin geometry.

        Parameters
        ----------
        ismn_data_gdf : geopandas.GeoDataFrame
            GeoDataFrame containing ISMN data
        basin_geometry : shapely.geometry
            Basin geometry of the basin to filter ISMN stations

        Returns
        -------
        geopandas.GeoDataFrame
            Filtered GeoDataFrame containing ISMN stations within the basin.
        """
        pass

    @staticmethod
    def calculate_depth_weighted_average(ismn_data_gdf):
        """
        Calculate depth-weighted average of ISMN soil moisture data.

        Parameters
        ----------
        ismn_data_gdf : geopandas.GeoDataFrame
            GeoDataFrame containing ISMN data

        Returns
        -------
        pd.DataFrame
            DataFrame with station information and ISMN soil moisture depth-weighted average values.
        """
        pass


class ISMNPlotter:
    @staticmethod
    def add_ismn_overlay(ax, ismn_data_df, proj):
        """
        Add ISMN data overlay to a given plot axis.

        Parameters
        ----------
        ax : matplotlib.axes.Axes
            Axes object to add overlay to
        ismn_data_df : pd.DataFrame
            DataFrame with station information and ISMN soil moisture depth-weighted average values
        proj : cartopy.crs
            The projection to use for the overlay
        """
        pass


if __name__ == "__main__":
    ismn_base_dir = "/home/miguel.pena/noaa-owp/ngen-forcing/soil_moisture_processing/sample_data"
    date = "2025-07-16"
    ismn_dirs, fs = ISMNDataLoader.get_ismn_dirs_by_date(ismn_base_dir, date)
    print(f"Total ISMN directories found: {len(ismn_dirs)}\n")

    # print sample dirs
    n = min(5, len(ismn_dirs))
    print("Sample ISMN directories:")
    for i in range(n):
        print(ismn_dirs[i])

    ismn_files = []

    for ismn_dir in ismn_dirs:
        ismn_files.extend(ISMNDataLoader.get_ismn_files(ismn_dir, fs))

    print(f"Total ISMN files found: {len(ismn_files)}")

    # print("Sample ISMN files:")
    # for i in range(5):
    #     ismn_file = ismn_files[i]
    #     print(ismn_file)

    ismn_data_gdf = ISMNDataLoader.get_ismn_data(ismn_files, date, fs)
