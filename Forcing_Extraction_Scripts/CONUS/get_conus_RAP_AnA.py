import os

from Forcing_Extraction_Scripts.forecast_base import ForecastDownloader


class RAPAnADownloader(ForecastDownloader):
    """
    Downloader for CONUS RAP AnA (Analysis) data.

    - Only forecast hours f01 and f02 are downloaded.
    - Files: rap.t{HH}z.awp130bgrbf{01|02}.grib2
    """

    @property
    def base_url(self):
        return "https://nomads.ncep.noaa.gov/pub/data/nccf/com/rap/prod"

    @property
    def lock_name(self):
        return "Conus_RAP_AnA"

    def get_download_targets(self, _):
        # Download only forecast hours 01 and 02
        return [1, 2]

    def build_output_dir(self, d_current):
        # Example: output/rap.20250415/
        return os.path.join(self.out_dir, f"rap.{d_current.strftime('%Y%m%d')}")

    def build_file_url_and_name(self, d_current, forecast_hour):
        """
        Build both the URL and the filename for RAP forecast hour files.
        Ex: rap.t00z.awp130bgrbf01.grib2
        """
        fhr_str = str(forecast_hour).zfill(2)
        filename = f"rap.t{d_current.strftime('%H')}z.awp130bgrbf{fhr_str}.grib2"
        url = os.path.join(self.base_url, f"rap.{d_current.strftime('%Y%m%d')}", filename)
        return url, filename


if __name__ == "__main__":
    downloader = RAPAnADownloader.from_cli_args()
    downloader.run()
