import os
import requests
from bs4 import BeautifulSoup
from Forcing_Extraction_Scripts.forecast_download_base import ForecastDownloader


class NBMHawaiiDownloader(ForecastDownloader):
    """
    Downloader for NBM forecast data over Hawaii.

    - Files live in: blend.YYYYMMDD/HH/core/
    - File discovery is dynamic via HTML scraping.
    - Files have the .hi.grib2 extension.
    """

    @property
    def base_url(self):
        return "https://nomads.ncep.noaa.gov/pub/data/nccf/com/blend/v4.1"

    @property
    def lock_name(self):
        return "NBM_Hawaii"

    def get_download_targets(self, _):
        return [0]  # not used

    def build_output_dir(self, d_current):
        return os.path.join(
            self.out_dir,
            f"blend.{d_current.strftime('%Y%m%d')}",
            d_current.strftime('%H'),
            "core"
        )

    def pre_download_hook(self, d_current):
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
                if a.get("href", "").endswith(".hi.grib2")
            ]
        except Exception as e:
            print(f"Error scraping {remote_dir_url}: {e}")

    def _download_data(self):
        for hour in range(self.lookback_hours, self.lagback_hours, -1):
            d_current = self.d_now - self._hour_delta(hour)
            self.pre_download_hook(d_current)

            output_dir = self.build_output_dir(d_current)
            os.makedirs(output_dir, exist_ok=True)

            for url in getattr(self, "_current_file_urls", []):
                filename = os.path.basename(url)
                out_path = os.path.join(output_dir, filename)
                if not os.path.isfile(out_path):
                    self._download_file(url, out_path)


if __name__ == "__main__":
    downloader = NBMHawaiiDownloader.from_cli_args()
    downloader.run()
