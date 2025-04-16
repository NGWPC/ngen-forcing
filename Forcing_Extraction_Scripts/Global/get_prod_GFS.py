import os

from Forcing_Extraction_Scripts.forecast_download_base import ForecastDownloader


class GFSDownloader(ForecastDownloader):
    """
    Downloader for GFS operational forecast data.

    - Available at 00Z, 06Z, 12Z, 18Z only.
    - Downloads sfluxgrbfNN.grib2 files out to 18h (expandable).
    - Files are organized by: gfs.YYYYMMDD/HH/atmos/
    """

    @property
    def base_url(self):
        return "https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod"

    def get_download_targets(self, d_current):
        return range(1, 19) if d_current.hour in [0, 6, 12, 18] else []

    def build_output_dir(self, d_current):
        return os.path.join(
            self.out_dir,
            f"gfs.{d_current.strftime('%Y%m%d')}",
            d_current.strftime('%H'),
            "atmos"
        )

    def build_file_url_and_name(self, d_current, forecast_hour):
        fhr = str(forecast_hour).zfill(3)
        filename = f"gfs.t{d_current.strftime('%H')}z.sfluxgrbf{fhr}.grib2"
        url = os.path.join(
            self.base_url,
            f"gfs.{d_current.strftime('%Y%m%d')}",
            d_current.strftime('%H'),
            "atmos",
            filename
        )
        return url, filename

    @property
    def recursive_cleanup(self) -> bool:
        return True


if __name__ == "__main__":
    downloader = GFSDownloader.from_cli_args()
    downloader.run()
