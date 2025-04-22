import os

from Forcing_Extraction_Scripts.forecast_download_base import ForecastDownloader


class NAMNestAlaskaDownloader(ForecastDownloader):
    """
    Downloader for NAM Alaska Nest forecast data (3-km resolution).

    - Forecasts are available every 6 hours: 00Z, 06Z, 12Z, 18Z
    - Output files: nam.t{HH}z.alaskanest.hiresf{fhr}.tm00.grib2
    """

    default_lookback = 36
    default_cleanback = 240
    default_lagback = 1

    @property
    def base_url(self):
        return "https://ftp.ncep.noaa.gov/data/nccf/com/nam/prod"

    def get_download_targets(self, d_current):
        # Only valid at 00z, 06z, 12z, 18z — skip other hours
        return range(1, 61) if d_current.hour in [0, 6, 12, 18] else []

    def build_output_dir(self, d_current):
        return os.path.join(self.out_dir, f"nam.{d_current.strftime('%Y%m%d')}")

    def build_file_url_and_name(self, d_current, fhr):
        """
        Build the download URL and filename for a specific forecast hour.
        Format:
            nam.t{HH}z.alaskanest.hiresf{fhr}.tm00.grib2
        """
        fhr_str = str(fhr).zfill(2)
        filename = f"nam.t{d_current.strftime('%H')}z.alaskanest.hiresf{fhr_str}.tm00.grib2"
        url = os.path.join(self.base_url, f"nam.{d_current.strftime('%Y%m%d')}", filename)
        return url, filename


if __name__ == "__main__":
    downloader = NAMNestAlaskaDownloader.from_cli_args()
    downloader.run()
