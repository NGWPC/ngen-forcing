from abc import ABC

from Forcing_Extraction_Scripts.forecast_download_base import FixedFileDownloader


class MRMSRadarConusDownloader(FixedFileDownloader, ABC):
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

    def get_file_specs(self, d_current):
        subdir = f"RadarOnly_QPE/{d_current.strftime('%Y%m%d')}"
        filename = f"MRMS_RadarOnly_QPE_01H_00.00_{d_current.strftime('%Y%m%d')}-{d_current.strftime('%H')}0000.grib2.gz"
        return [(subdir, filename)]
