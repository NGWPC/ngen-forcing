import argparse
import atexit
import os
import shutil
import sys
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from urllib import request, error

import requests
from bs4 import BeautifulSoup


class ForecastDownloader(ABC):
    """
    Abstract base class for structured forecast data downloads.

    Supports:
    - Lock file safety
    - Download retry with exponential backoff
    - Cleanup of old data
    - CLI support via from_cli_args()
    - Optional forecast-per-cycle or single-file-per-hour strategies

    Subclasses override methods to define behavior for:
    - URL structure
    - File naming
    - Forecast cycle filtering
    """

    def __init__(self, out_dir, lookback_hours, cleanback_hours, lagback_hours):
        """
        Initialize downloader with common configuration.

        :param out_dir: Root output directory where files are saved
        :param lookback_hours: How many hours back to fetch forecasts
        :param cleanback_hours: How far back to clean old files
        :param lagback_hours: How many hours to lag before starting to fetch
        """
        self.out_dir = out_dir
        self.lookback_hours = lookback_hours
        self.cleanback_hours = cleanback_hours
        self.lagback_hours = lagback_hours

        # Current hour, rounded to the top of the hour in UTC
        self.d_now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

        # Ensure output directory exists
        os.makedirs(self.out_dir, exist_ok=True)

        # Lockfile used to prevent concurrent runs
        self.lockfile = os.path.join(self.out_dir, f"{self.__class__.__name__}.lck")

    #
    # --- Public Interface ---
    #

    @classmethod
    def from_cli_args(cls):
        """
        Create an instance of the subclass using command-line arguments.
        Also prints the parsed arguments for logging/debugging.
        """
        parser = argparse.ArgumentParser()
        parser.add_argument('outDir', type=str, help="Output directory path")
        parser.add_argument('--lookBackHours', type=int, default=30)
        parser.add_argument('--cleanBackHours', type=int, default=240)
        parser.add_argument('--lagBackHours', type=int, default=1)
        args = parser.parse_args()

        print(f"{cls.__name__} args:", vars(args))

        return cls(
            out_dir=args.outDir,
            lookback_hours=args.lookBackHours,
            cleanback_hours=args.cleanBackHours,
            lagback_hours=args.lagBackHours,
        )

    def run(self):
        """
        Main method that orchestrates lock acquisition, cleanup, and downloading.
        """
        self._acquire_lock()
        try:
            self._cleanup_old_data()
            self._download_data()
        finally:
            self._release_lock()

    #
    # --- Abstract methods to override in subclass ---
    #

    @property
    @abstractmethod
    def base_url(self):
        """Return the base URL for downloading forecast files."""
        pass

    @abstractmethod
    def get_download_targets(self, d_current):
        """
        Return a list of forecast targets (e.g., forecast hours, 'Pass1', etc.)
        to be used for a given forecast cycle time.
        """
        pass

    @abstractmethod
    def build_output_dir(self, d_current):
        """
        Return the output directory for the given forecast cycle datetime.
        """
        pass

    @abstractmethod
    def build_file_url_and_name(self, d_current, target):
        pass

    #
    # --- Optional subclass overrides ---
    #

    @property
    def per_target_download(self):
        """
        If True, iterate over the list returned by get_download_targets().
        If False, call build_file_url_and_name once with target=None.
        """
        return True

    @property
    def recursive_cleanup(self) -> bool:
        """
        If True, recursively delete leaf directories and prune empty parent directories.
        If False, use default build_output_dir() cleanup per timestamp.
        """
        return False

    def pre_download_hook(self, d_current):
        """
        Optional hook called before downloading begins for a specific cycle.
        Use this to scrape directories or cache target lists.
        """
        pass

    def post_download_hook(self, d_current):
        """
        Optional hook called after downloading completes for a specific cycle.
        Use this for logging or post-processing.
        """
        pass

    @staticmethod
    def _hour_delta(hours):
        """
        Utility to return a timedelta offset of N hours.
        Used for computing relative timestamps from d_now.
        """
        return timedelta(hours=hours)

    #
    # --- Internal workflow methods ---
    #

    def _acquire_lock(self):
        """
        Prevent multiple concurrent runs by creating a lockfile.
        Register atexit cleanup to ensure the lock is removed when the process exits.
        """
        if os.path.isfile(self.lockfile):
            with open(self.lockfile, 'r') as f:
                pid = f.readline().strip()
            print(f"ERROR: Lock file {self.lockfile} exists. PID: {pid}")
            sys.exit(1)

        with open(self.lockfile, 'w') as f:
            f.write(str(os.getpid()))

        # Automatically clean up the lock file on exit
        atexit.register(self._release_lock)

    def _release_lock(self):
        """
        Safely remove the lock file if it still exists.
        """
        if os.path.exists(self.lockfile):
            try:
                os.remove(self.lockfile)
            except Exception as e:
                print(f"Warning: Failed to remove lockfile: {e}")

    def _cleanup_old_data(self):
        """
        Cleans up old data using either:
        - default timestamp-based cleanup (subdirectory per forecast cycle)
        - recursive directory cleanup with pruning
        """
        for hour in range(self.cleanback_hours, self.lagback_hours, -1):
            d_current = self.d_now - self._hour_delta(hour)

            if self.recursive_cleanup:
                # Recursively remove subdir, parent hour dir, then date dir if empty
                leaf_dir = self.build_output_dir(d_current)
                self._remove_dir_and_empty_parents(leaf_dir, levels=2)
            else:
                # Default behavior: remove build_output_dir if it exists
                dir_path = self.build_output_dir(d_current)
                if os.path.isdir(dir_path):
                    print(f"Removing old data: {dir_path}")
                    shutil.rmtree(dir_path)

    @staticmethod
    def _remove_dir_and_empty_parents(path, levels=2):
        """
        Removes a directory and prunes up to `levels` empty parent directories.

        :param path: Path to the target directory to remove.
        :param levels: Max number of parent levels to prune if empty.
        """
        if os.path.isdir(path):
            print(f"Removing directory: {path}")
            shutil.rmtree(path)

            # Prune up to `levels` empty parent directories
            for _ in range(levels):
                path = os.path.dirname(path)
                if os.path.isdir(path) and not os.listdir(path):
                    print(f"Removing empty parent directory: {path}")
                    os.rmdir(path)
                else:
                    break

    def _download_data(self):
        """
        Download forecast files by iterating over the desired time range and download targets.
        Can optionally download just one file per cycle if per_target_download is False.
        """
        for hour in range(self.lookback_hours, self.lagback_hours, -1):
            d_current = self.d_now - self._hour_delta(hour)
            output_dir = self.build_output_dir(d_current)
            os.makedirs(output_dir, exist_ok=True)

            self.pre_download_hook(d_current)

            targets = self.get_download_targets(d_current)
            if not self.per_target_download:
                targets = [None]

            for target in targets:
                url, filename = self.build_file_url_and_name(d_current, target)
                out_path = os.path.join(output_dir, filename)

                if os.path.isfile(out_path):
                    print(f"Skipping existing: {out_path}")
                    continue

                self._download_file(url, out_path)

            self.post_download_hook(d_current)

    # noinspection PyMethodMayBeStatic
    def _download_file(self, url, out_path):
        """
        Attempt to download a file from the URL with retry logic.
        Retries up to 20 times with a 30-second interval between attempts.
        """
        max_attempts = 20
        interval = 30  # seconds
        attempt = 0

        while attempt < max_attempts:
            try:
                print(f"Attempt {attempt + 1}: Downloading {url}")
                request.urlretrieve(url, out_path)
                print(f"Download complete: {out_path}")
                return
            except error.HTTPError as e:
                print(f"HTTPError {e.code} while downloading {url}: {e.reason}")
            except error.URLError as e:
                print(f"URLError while downloading {url}: {e.reason}")
            except Exception as e:
                print(f"Unexpected error while downloading {url}: {e}")

            attempt += 1
            time.sleep(interval)

        print(f"❌ Failed to download after {max_attempts} attempts: {url}")


class FixedFileDownloader(ForecastDownloader, ABC):
    """
    Subclass for forecast datasets that consist of one or more fixed files per cycle.

    Intended for sources like MRMS and StageIV that have predefined filenames and subdirectories,
    without forecast-hour-based iteration.

    Subclasses must implement:
    - get_file_specs(d_current): returns list of (subdir, filename) for a given timestamp
    """

    def build_file_url_and_name(self, d_current, target):
        raise NotImplementedError("FixedFileDownloader uses get_file_specs() instead.")

    @abstractmethod
    def get_file_specs(self, d_current) -> list[tuple[str, str]]:
        """
        Return a list of (subdir, filename) tuples for files to be downloaded
        """
        pass

    def _download_data(self):
        for hour in range(self.lookback_hours, self.lagback_hours, -1):
            d_current = self.d_now - self._hour_delta(hour)
            for subdir, filename in self.get_file_specs(d_current):
                full_dir = os.path.join(self.out_dir, subdir)
                os.makedirs(full_dir, exist_ok=True)
                url = self.base_url + filename
                out_path = os.path.join(full_dir, filename)
                if not os.path.isfile(out_path):
                    self._download_file(url, out_path)


class ScrapedFileDownloader(ForecastDownloader, ABC):
    """
    Subclass for forecast datasets that must scrape an HTML directory to discover files.

    Intended for sources like NBM, where forecast files are published dynamically and filenames
    may vary by cycle.

    Subclasses must implement:
    - get_scrape_url(d_current): returns the remote URL to scrape for a specific timestamp
    - filter_url(url): returns True for valid files to download (e.g., endswith ".hi.grib2")
    """

    @abstractmethod
    def get_scrape_url(self, d_current):
        pass

    @abstractmethod
    def filter_url(self, url: str) -> bool:
        pass

    def build_file_url_and_name(self, d_current, target):
        raise NotImplementedError("ScrapedFileDownloader uses scraping logic instead of build_file_url_and_name().")

    def _download_data(self):
        for hour in range(self.lookback_hours, self.lagback_hours, -1):
            d_current = self.d_now - self._hour_delta(hour)
            url = self.get_scrape_url(d_current)
            output_dir = self.build_output_dir(d_current)
            os.makedirs(output_dir, exist_ok=True)

            html = requests.get(url).text
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.find_all("a"):
                href = a.get("href", "")
                full_url = os.path.join(url, href)
                if self.filter_url(full_url):
                    out_path = os.path.join(output_dir, os.path.basename(full_url))
                    if not os.path.isfile(out_path):
                        self._download_file(full_url, out_path)
