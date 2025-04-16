import os
from Forcing_Extraction_Scripts.forecast_download_base import ForecastDownloader


class NAMNestHawaiiDownloader(ForecastDownloader):
    """
    Downloader for NAM Nest Hawaii 3-km forecast data.

    - Forecasts available every 6 hours: 00Z, 06Z, 12Z, 18Z
    - Each forecast has 60 hourly files.
    """

    @property
    def base_url(self):
        return "https://ftp.ncep.noaa.gov/data/nccf/com/nam/prod"

    @property
    def lock_name(self):
        return "NAM_Nest_Hawaii"

    def get_download_targets(self, d_current):
        return range(1, 61) if d_current.hour in [0, 6, 12, 18] else []

    def build_output_dir(self, d_current):
        return os.path.join(self.out_dir, f"nam.{d_current.strftime('%Y%m%d')}")

    def build_file_url_and_name(self, d_current, target):
        fhr = str(target).zfill(2)
        filename = f"nam.t{d_current.strftime('%H')}z.hawaiinest.hiresf{fhr}.tm00.grib2"
        url = os.path.join(self.base_url, f"nam.{d_current.strftime('%Y%m%d')}", filename)
        return url, filename


if __name__ == "__main__":
    downloader = NAMNestHawaiiDownloader.from_cli_args()
    downloader.run()
