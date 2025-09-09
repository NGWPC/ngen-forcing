from abc import ABC

from Forcing_Extraction_Scripts.forecast_download_base import FixedFileDownloader


class MRMSRadarConusDownloader(FixedFileDownloader, ABC):
    """
    Downloader for MRMS RadarOnly hourly QPE for CONUS.

    - Files are stored directly in the RadarOnly_QPE_01H directory.
    - No forecast hours are involved; only one file per timestamp.
    - This subclass overrides cleanup and download logic to reflect
      the simpler structure (one file per hour).
    """

    @property
    def base_url(self):
        # Base directory; files are directly in the RadarOnly_QPE_01H directory
        return "https://mrms.ncep.noaa.gov/data/2D/RadarOnly_QPE_01H"

    def build_output_dir(self, _, __):
        return self.out_dir

    def get_file_specs(self, d_start):
        # Construct the filename without subdirectory
        filename = f"MRMS_RadarOnly_QPE_01H_00.00_{d_start.strftime('%Y%m%d')}-{d_start.strftime('%H')}0000.grib2.gz"
        return [("", filename)]


if __name__ == "__main__":
    downloader = MRMSRadarConusDownloader.from_cli_args()
    downloader.run()
