import os
from Forcing_Extraction_Scripts.forecast_download_base import ForecastDownloader


class NAMNestPuertoRicoDownloader(ForecastDownloader):
    """
    Downloader for NAM Nest Puerto Rico 3-km forecasts.

    - Forecasts are issued every 6 hours: 00Z, 06Z, 12Z, 18Z.
    - Files end with `.priconest.hiresfNN.tm00.grib2`.
    """

    @property
    def base_url(self):
        return "https://ftp.ncep.noaa.gov/data/nccf/com/nam/prod"

    def get_download_targets(self, d_current):
        return range(1, 61) if d_current.hour in [0, 6, 12, 18] else []

    def build_output_dir(self, d_current):
        return os.path.join(self.out_dir, f"nam.{d_current.strftime('%Y%m%d')}")

    def build_file_url_and_name(self, d_current, target):
        fhr = str(target).zfill(2)
        filename = f"nam.t{d_current.strftime('%H')}z.priconest.hiresf{fhr}.tm00.grib2"
        url = os.path.join(self.base_url, f"nam.{d_current.strftime('%Y%m%d')}", filename)
        return url, filename


if __name__ == "__main__":
    downloader = NAMNestPuertoRicoDownloader.from_cli_args()
    downloader.run()
