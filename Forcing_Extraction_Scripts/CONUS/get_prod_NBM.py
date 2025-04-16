import argparse
import os
import shutil
import requests
from bs4 import BeautifulSoup
from Forcing_Extraction_Scripts.forecast_download_base import ForecastDownloader


class NBMDownloader(ForecastDownloader):
    """
    Downloader for NBM data on the Gaussian grid in GRIB2 format.

    - Files live in: blend.YYYYMMDD/HH/core/
    - Scraped from HTML directory listing (non-predictable file names).
    - Filters to only download files ending in `.co.grib2`.
    """

    @property
    def base_url(self):
        return "https://nomads.ncep.noaa.gov/pub/data/nccf/com/blend/v4.2"

    @property
    def lock_name(self):
        return "NBM_Full"

    def get_download_targets(self, _):
        # Not applicable — actual files are scraped from a directory listing
        return [0]

    def build_output_dir(self, d_current):
        return os.path.join(
            self.out_dir,
            f"blend.{d_current.strftime('%Y%m%d')}",
            d_current.strftime('%H'),
            "core"
        )

    def _download_data(self):
        """
        Overrides the base method to dynamically scrape the list of available .grib2 files
        from the directory listing (served as HTML). Downloads the first 18 files only.
        """
        for hour in range(self.lookback_hours, self.lagback_hours, -1):
            d_current = self.d_now - self._hour_delta(hour)

            out_dir = self.build_output_dir(d_current)
            os.makedirs(out_dir, exist_ok=True)

            dir_url = os.path.join(
                self.base_url,
                f"blend.{d_current.strftime('%Y%m%d')}",
                d_current.strftime('%H'),
                "core"
            )

            try:
                # Retrieve list of file URLs ending in .co.grib2
                urls = self._get_url_paths(dir_url, ext=".co.grib2")
            except Exception as e:
                print(f"Error scraping {dir_url}: {e}")
                continue

            for file_url in urls[:18]:
                filename = os.path.basename(file_url)
                out_path = os.path.join(out_dir, filename)
                if not os.path.isfile(out_path):
                    self._download_file(file_url, out_path)

    def _get_url_paths(self, url, ext=""):
        """
        Helper function to scrape all hrefs from an HTML directory page that end in the given extension.
        """
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        return [
            os.path.join(url, a["href"])
            for a in soup.find_all("a")
            if a.get("href", "").endswith(ext)
        ]

    def _cleanup_old_data(self):
        for hour in range(self.cleanback_hours, self.lookback_hours, -1):
            d_current = self.d_now - self._hour_delta(hour)

            core_path = os.path.join(
                self.out_dir,
                f"blend.{d_current.strftime('%Y%m%d')}",
                d_current.strftime('%H'),
                "core"
            )
            if os.path.isdir(core_path):
                print(f"Removing old NBM data from: {core_path}")
                shutil.rmtree(core_path)

            parent_dir = os.path.dirname(os.path.dirname(core_path))
            if os.path.isdir(parent_dir) and not os.listdir(parent_dir):
                print(f"Removing empty directory: {parent_dir}")
                shutil.rmtree(parent_dir)


if __name__ == "__main__":
    downloader = NBMDownloader.from_cli_args()
    downloader.run()
