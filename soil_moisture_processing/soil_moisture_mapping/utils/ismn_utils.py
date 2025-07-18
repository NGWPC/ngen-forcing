import re
import fsspec
import pandas as pd
import geopandas as gpd
import numpy as np
from datetime import datetime
from shapely.geometry import Point


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

        print(matching_dirs)
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

        for ismn_file in ismn_files:
            print(ismn_file)
        
        return ismn_files

if __name__ == "__main__":
    # Example usage
    ismn_base_dir = "/home/miguel.pena/noaa-owp/ngen-forcing/soil_moisture_processing/sample_data"
    date = "2025-07-17"
    ismn_dirs, fs = ISMNDataLoader.get_ismn_dirs_by_date(ismn_base_dir, date)
    ismn_files: list = []
    
    for ismn_dir in ismn_dirs:
        ismn_files.append(ISMNDataLoader.get_ismn_files(ismn_dir, fs))
