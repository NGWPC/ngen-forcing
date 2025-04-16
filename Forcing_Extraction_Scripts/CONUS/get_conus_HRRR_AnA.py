import os

from Forcing_Extraction_Scripts.forecast_download_base import ForecastDownloader


class HRRRAnAConusDownloader(ForecastDownloader):
    """
    Downloader for CONUS HRRR Analysis (AnA) surface data.

    - Files are available hourly.
    - No forecast hours – just one analysis file per hour.
    """

    @property
    def base_url(self):
        return "https://nomads.ncep.noaa.gov/pub/data/nccf/com/hrrr/prod"

    @property
    def lock_name(self):
        return "Conus_HRRR_AnA"

    def get_download_target(self, d_current):
        # Only download forecast hours 01 and 02
        return [1, 2]

    def build_output_dir(self, d_current):
        # Output directory format: <out_dir>/hrrr.YYYYMMDD/conus
        return os.path.join(self.out_dir, f"hrrr.{d_current.strftime('%Y%m%d')}", "conus")

    def build_file_url_and_name(self, d_current, forecast_hour):
        """
        Construct both the download URL and filename for f01/f02 forecast hours.

        Example filename: hrrr.t12z.wrfsfcf01.grib2
        URL format: https://.../hrrr.YYYYMMDD/conus/hrrr.tHHz.wrfsfcf01.grib2
        """
        fhr_str = str(forecast_hour).zfill(2)
        filename = f"hrrr.t{d_current.strftime('%H')}z.wrfsfcf{fhr_str}.grib2"
        url = os.path.join(self.base_url, f"hrrr.{d_current.strftime('%Y%m%d')}", "conus", filename)
        return url, filename

if __name__ == "__main__":
    downloader = HRRRAnAConusDownloader.from_cli_args()
    downloader.run()
