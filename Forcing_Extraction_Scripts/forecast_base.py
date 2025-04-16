import argparse
import atexit
import os
import shutil
import sys
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from urllib import request, error


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
        self.lockfile = os.path.join(self.out_dir, f"GET_{self.lock_name}.lock")

    #
    # --- Public Interface ---
    #

    @classmethod
    def from_cli_args(cls):
        """
        Create an instance of the subclass using command-line arguments.
        """
        parser = argparse.ArgumentParser()
        parser.add_argument('outDir', type=str, help="Output directory path")
        parser.add_argument('--lookBackHours', type=int, default=30)
        parser.add_argument('--cleanBackHours', type=int, default=240)
        parser.add_argument('--lagBackHours', type=int, default=1)
        args = parser.parse_args()

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

    @property
    @abstractmethod
    def lock_name(self):
        """Return a unique string used in naming the lockfile."""
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
        """
        Return a tuple (url, filename) for the forecast file corresponding to the cycle and target.
        """
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

    def _hour_delta(self, hours):
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
            print(f"ERROR: Lock file exists. PID: {pid}")
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
        Delete old forecast output directories from 'cleanBackHours' ago up to 'lagBackHours' ago.
        """
        for hour in range(self.cleanback_hours, self.lagback_hours, -1):
            d_current = self.d_now - self._hour_delta(hour)
            dir_path = self.build_output_dir(d_current)
            if os.path.isdir(dir_path):
                print(f"Removing old data: {dir_path}")
                shutil.rmtree(dir_path)

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
