import os

import requests
from bs4 import BeautifulSoup

from Forcing_Extraction_Scripts.forecast_download_base import ForecastDownloader


class NBMAlaskaDownloader(ForecastDownloader):
    """
    Downloader for Alaska NBM forecast data.

    - Files are dynamically discovered by scraping the directory listing.
    - Only files ending with `.ak.grib2` are downloaded.
    - Stored in: blend.YYYYMMDD/HH/core/
    """

    @property
    def base_url(self):
        return "https://nomads.ncep.noaa.gov/pub/data/nccf/com/blend/v4.2"

    def get_download_targets(self, _):
        # Not applicable: file list discovered via HTML scraping
        return [0]

    def build_output_dir(self, d_current):
        # Output: blend.YYYYMMDD/HH/core/
        return os.path.join(
            self.out_dir,
            f"blend.{d_current.strftime('%Y%m%d')}",
            d_current.strftime('%H'),
            "core"
        )

    def pre_download_hook(self, d_current):
        """
        Scrape the target directory and collect all URLs ending with '.ak.grib2'.
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
                if a.get("href", "").endswith(".ak.grib2")
            ]
        except Exception as e:
            print(f"Error scraping {remote_dir_url}: {e}")

    def build_file_url_and_name(self, d_current, target):
        raise NotImplementedError("This downloader overrides _download_data directly.")

    def _download_data(self):
        """
        Scrapes .ak.grib2 files from the remote NBM directory using HTML directory listing.
        """
        for hour in range(self.lookback_hours, self.lagback_hours, -1):
            d_current = self.d_now - self._hour_delta(hour)
            self.pre_download_hook(d_current)

            output_dir = self.build_output_dir(d_current)
            os.makedirs(output_dir, exist_ok=True)

            for url in self._current_file_urls[:18]:
                filename = os.path.basename(url)
                out_path = os.path.join(str(output_dir), filename)  # Explicit cast to avoid Pycharm warning
                if not os.path.isfile(out_path):
                    self._download_file(url, out_path)

    @property
    def recursive_cleanup(self) -> bool:
        return True


if __name__ == "__main__":
    downloader = NBMAlaskaDownloader.from_cli_args()
    downloader.run()
