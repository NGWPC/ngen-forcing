import os

from Forcing_Extraction_Scripts.forecast_download_base import ForecastDownloader


class MRMSRadarDownloader(ForecastDownloader):
    """
    Downloader for MRMS RadarOnly hourly QPE for CONUS.

    - Each file is named based on the hour and stored in a directory
      like RadarOnly_QPE/YYYYMMDD/
    - No forecast hours are involved; only one file per timestamp.
    - This subclass overrides cleanup and download logic to reflect
      the simpler structure (one file per hour).
    """

    @property
    def base_url(self):
        # All files live in this flat directory on the server
        return "https://mrms.ncep.noaa.gov/data/2D/RadarOnly_QPE_01H"

    @property
    def lock_name(self):
        return "MRMS_Radar_CONUS"

    def get_download_targets(self, _):
        # Not used — only one file per hour
        return [0]

    def build_output_dir(self, d_current):
        # Directory is organized by date (e.g., RadarOnly_QPE/20240414)
        return os.path.join(self.out_dir, "RadarOnly_QPE", d_current.strftime('%Y%m%d'))

    def build_file_url_and_name(self, d_current, _):
        # File pattern: MRMS_RadarOnly_QPE_01H_00.00_YYYYMMDD-HH0000.grib2.gz
        filename = f"MRMS_RadarOnly_QPE_01H_00.00_{d_current.strftime('%Y%m%d')}-{d_current.strftime('%H')}0000.grib2.gz"
        url = os.path.join(self.base_url, filename)
        return url, filename


if __name__ == "__main__":
    downloader = MRMSRadarDownloader.from_cli_args()
    downloader.run()
