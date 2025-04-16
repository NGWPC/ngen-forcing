import os
from Forcing_Extraction_Scripts.forecast_download_base import ForecastDownloader


class ARWPuertoRicoDownloader(ForecastDownloader):
    """
    Downloader for WRF-ARW 2.5 km Puerto Rico forecasts.

    - Available at 06Z and 18Z cycles only.
    - Forecast extends 48 hours.
    - Files end in `.pr.grib2`.
    """

    @property
    def base_url(self):
        return "https://ftp.ncep.noaa.gov/data/nccf/com/hiresw/prod"

    def get_download_targets(self, d_current):
        return range(1, 49) if d_current.hour in [6, 18] else []

    def build_output_dir(self, d_current):
        return os.path.join(self.out_dir, f"hiresw.{d_current.strftime('%Y%m%d')}")

    def build_file_url_and_name(self, d_current, target):
        fhr = str(target).zfill(2)
        filename = f"hiresw.t{d_current.strftime('%H')}z.arw_2p5km.f{fhr}.pr.grib2"
        url = os.path.join(self.base_url, f"hiresw.{d_current.strftime('%Y%m%d')}", filename)
        return url, filename


if __name__ == "__main__":
    downloader = ARWPuertoRicoDownloader.from_cli_args()
    downloader.run()
