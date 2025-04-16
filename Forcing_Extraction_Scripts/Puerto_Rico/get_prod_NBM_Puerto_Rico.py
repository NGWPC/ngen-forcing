import os
import shutil

import requests
from bs4 import BeautifulSoup
from Forcing_Extraction_Scripts.forecast_base import ForecastDownloader


class NBMPuertoRicoDownloader(ForecastDownloader):
    """
    Downloader for NBM forecast data over Puerto Rico.

    - Files are located under: blend.YYYYMMDD/HH/core/
    - Files of interest end with .pr.grib2
    - Scraping is performed using HTML parsing of the directory listing
    """

    @property
    def base_url(self):
        return "https://nomads.ncep.noaa.gov/pub/data/nccf/com/blend/v4.2"

    @property
    def lock_name(self):
        return "NBM_PuertoRico"

    def get_download_targets(self, _):
        return [0]  # unused in this implementation

    def build_output_dir(self, d_current):
        return os.path.join(
            self.out_dir,
            f"blend.{d_current.strftime('%Y%m%d')}",
            d_current.strftime('%H'),
            "core"
        )

    def pre_download_hook(self, d_current):
        """
        Scrape the forecast directory for Puerto Rico NBM files ending in '.pr.grib2'
        """
        self._current_file_urls = []

        remote_dir_url = os.path.join(
            self.base_url,
            f"blend.{d_current.strftime('%Y%m%d')}",
            d_current.strftime('%H'),
            "core"
        )

        try:
            response = requests.get(remote_dir_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            self._current_file_urls = [
                os.path.join(remote_dir_url, a["href"])
                for a in soup.find_all("a")
                if a.get("href", "").endswith(".pr.grib2")
            ]
        except Exception as e:
            print(f"Error scraping {remote_dir_url}: {e}")

    def _download_data(self):
        """
        Download NBM Puerto Rico forecast files by scraping each directory
        """
        for hour in range(self.lookback_hours, self.lagback_hours, -1):
            d_current = self.d_now - self._hour_delta(hour)
            self.pre_download_hook(d_current)

            output_dir = self.build_output_dir(d_current)
            os.makedirs(output_dir, exist_ok=True)

            for url in self._current_file_urls[:18]:
                filename = os.path.basename(url)
                out_path = os.path.join(output_dir, filename)
                if not os.path.isfile(out_path):
                    self._download_file(url, out_path)

    def _cleanup_old_data(self):
        """
        Remove old data from 'core' subdirectory and clean up empty parent folders
        """
        for hour in range(self.cleanback_hours, self.lookback_hours, -1):
            d_current = self.d_now - self._hour_delta(hour)

            core_dir = self.build_output_dir(d_current)
            if os.path.isdir(core_dir):
                print(f"Removing old NBM data from: {core_dir}")
                shutil.rmtree(core_dir)

            # If blend.YYYYMMDD/HH/ is empty, remove it
            hour_dir = os.path.dirname(core_dir)
            if os.path.isdir(hour_dir) and not os.listdir(hour_dir):
                print(f"Removing empty hour directory: {hour_dir}")
                shutil.rmtree(hour_dir)

            # If blend.YYYYMMDD/ is now empty, remove it too
            day_dir = os.path.dirname(hour_dir)
            if os.path.isdir(day_dir) and not os.listdir(day_dir):
                print(f"Removing empty day directory: {day_dir}")
                shutil.rmtree(day_dir)


if __name__ == "__main__":
    downloader = NBMPuertoRicoDownloader.from_cli_args()
    downloader.run()
