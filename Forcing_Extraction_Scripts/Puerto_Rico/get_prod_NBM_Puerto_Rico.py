import os

import requests
from bs4 import BeautifulSoup

from Forcing_Extraction_Scripts.forecast_download_base import ForecastDownloader


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

    def build_file_url_and_name(self, d_current, target):
        raise NotImplementedError("This downloader overrides _download_data directly.")

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
                out_path = os.path.join(str(output_dir), filename)  # Explicit cast to avoid Pycharm warning
                if not os.path.isfile(out_path):
                    self._download_file(url, out_path)

    @property
    def recursive_cleanup(self) -> bool:
        return True


if __name__ == "__main__":
    downloader = NBMPuertoRicoDownloader.from_cli_args()
    downloader.run()
