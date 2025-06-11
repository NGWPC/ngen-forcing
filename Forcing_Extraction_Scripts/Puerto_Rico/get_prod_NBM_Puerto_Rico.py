import os

from Forcing_Extraction_Scripts.forecast_download_base import ForecastDownloader


class NBMPuertoRicoDownloader(ForecastDownloader):
    """
    Downloader for NBM forecast data over Puerto Rico using predictable filenames.

    - Files are stored in: blend.YYYYMMDD/HH/core/
    - File pattern: blend.t{HH}z.core.f{forecast_hour}.pr.grib2
    - Forecast hours range from f001 to f264.
    """

    @property
    def base_url(self):
        return "https://nomads.ncep.noaa.gov/pub/data/nccf/com/blend/prod"

    def should_process_hour(self, d_current):
        return d_current.hour in [0, 6, 12, 18]

    def get_download_targets(self, d_current):
        return range(1, 265) if d_current.hour in [0, 6, 12, 18] else []

    def build_output_dir(self, d_current):
        return os.path.join(
            self.out_dir,
            f"blend.{d_current.strftime('%Y%m%d')}",
            d_current.strftime('%H'),
            "core"
        )

    def build_file_url_and_name(self, d_current, target):
        fhr_str = f"f{str(target).zfill(3)}"
        filename = f"blend.t{d_current.strftime('%H')}z.core.{fhr_str}.pr.grib2"
        url = os.path.join(
            self.base_url,
            f"blend.{d_current.strftime('%Y%m%d')}",
            d_current.strftime('%H'),
            "core",
            filename
        )
        return url, filename

    @property
    def recursive_cleanup(self) -> bool:
        return True


if __name__ == "__main__":
    downloader = NBMPuertoRicoDownloader.from_cli_args()
    downloader.run()
