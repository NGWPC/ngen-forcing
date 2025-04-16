import os
from abc import ABC

from Forcing_Extraction_Scripts.forecast_download_base import ScrapedFileDownloader


class NBMHawaiiDownloader(ScrapedFileDownloader, ABC):
    """
    Downloader for NBM forecast data over Hawaii.

    - Files live in: blend.YYYYMMDD/HH/core/
    - File discovery is dynamic via HTML scraping.
    - Files have the .hi.grib2 extension.
    """

    @property
    def base_url(self):
        return "https://nomads.ncep.noaa.gov/pub/data/nccf/com/blend/v4.1"

    def get_scrape_url(self, d_current):
        return os.path.join(
            self.base_url,
            f"blend.{d_current.strftime('%Y%m%d')}",
            d_current.strftime('%H'),
            "core"
        )

    def build_output_dir(self, d_current):
        return os.path.join(
            self.out_dir,
            f"blend.{d_current.strftime('%Y%m%d')}",
            d_current.strftime('%H'),
            "core"
        )

    def filter_url(self, url: str) -> bool:
        return url.endswith(".hi.grib2")

    @property
    def recursive_cleanup(self) -> bool:
        return True
