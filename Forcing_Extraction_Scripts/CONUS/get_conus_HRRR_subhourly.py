import argparse
import os
from Forcing_Extraction_Scripts.forecast_base import ForecastDownloader


class HRRRSubhourlyDownloader(ForecastDownloader):
    """
    Downloader for CONUS HRRR sub-hourly data (15-minute forecasts).

    Sub-hourly files follow a naming convention like:
    hrrr.t00z.wrfsubhf00.grib2, ..., wrfsubhf18.grib2

    Always downloads 0–18 forecast hours regardless of cycle time.
    """

    @property
    def base_url(self):
        return "https://nomads.ncep.noaa.gov/pub/data/nccf/com/hrrr/prod"

    @property
    def lock_name(self):
        return "Conus_HRRR_subhourly"

    def get_download_targets(self, d_current):
        # HRRR subhourly always provides 18 forecast hours (+f00)
        return range(0, 19)

    def build_output_dir(self, d_current):
        # Output directory path includes date (e.g., hrrr.20240414/conus)
        return os.path.join(self.out_dir, f"hrrr.{d_current.strftime('%Y%m%d')}", "conus")

    def build_file_url_and_name(self, d_current, target):
        fhr_str = str(target).zfill(2)
        filename = f"hrrr.t{d_current.strftime('%H')}z.wrfsubhf{fhr_str}.grib2"
        url = os.path.join(self.base_url, f"hrrr.{d_current.strftime('%Y%m%d')}", "conus", filename)
        return url, filename


if __name__ == "__main__":
    downloader = HRRRSubhourlyDownloader.from_cli_args()
    downloader.run()