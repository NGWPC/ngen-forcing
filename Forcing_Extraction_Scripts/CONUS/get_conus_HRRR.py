import os

from forecast_base import ForecastDownloader


class HRRRDownloader(ForecastDownloader):
    """
    Downloader for CONUS HRRR forecast data.
    Downloads full surface forecast files (wrfsfcfXX.grib2) for each cycle.
    Forecast length depends on the cycle hour (18 or 36 hours).
    """

    @property
    def base_url(self):
        # HRRR data base URL from NOMADS
        return "https://nomads.ncep.noaa.gov/pub/data/nccf/com/hrrr/prod"

    @property
    def lock_name(self):
        # Used to create a unique lockfile
        return "Conus_HRRR"

    def get_download_targets(self, d_current):
        # HRRR cycles at 00, 06, 12, 18 UTC produce 36-hour forecasts; others produce 18-hour forecasts
        return range(0, 37) if d_current.hour % 6 == 0 else range(0, 19)

    def build_output_dir(self, d_current):
        # Output directory format: <out_dir>/hrrr.YYYYMMDD/conus
        return os.path.join(self.out_dir, f"hrrr.{d_current.strftime('%Y%m%d')}", "conus")

    def build_file_url_and_name(self, d_current, forecast_hour):
        """
        Construct both the download URL and the filename for a given forecast hour.

        Example filename: hrrr.t00z.wrfsfcf01.grib2
        URL format: https://.../hrrr.YYYYMMDD/conus/hrrr.tHHz.wrfsfcfXX.grib2
        """
        fhr_str = str(forecast_hour).zfill(2)
        filename = f"hrrr.t{d_current.strftime('%H')}z.wrfsfcf{fhr_str}.grib2"
        date_dir = f"hrrr.{d_current.strftime('%Y%m%d')}"
        url = os.path.join(self.base_url, date_dir, "conus", filename)
        return url, filename


if __name__ == "__main__":
    downloader = HRRRDownloader.from_cli_args()
    downloader.run()
