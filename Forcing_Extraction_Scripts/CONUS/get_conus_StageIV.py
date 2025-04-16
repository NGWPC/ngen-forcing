from abc import ABC

from Forcing_Extraction_Scripts.forecast_download_base import ForecastDownloader


class StageIVDownloader(ForecastDownloader, ABC):
    """
    Downloader for CONUS Stage IV hourly precipitation analysis.

    - Files are organized by date on the server in folders like: pcpanl.YYYYMMDD
    - Filenames are based on full timestamp: st4_conus.YYYYMMDDHH.01h.grb2
    - We download one file per hour.
    - Local output is flattened (no pcpanl subfolder used locally).
    """

    @property
    def base_url(self):
        return "https://nomads.ncep.noaa.gov/pub/data/nccf/com/pcpanl/v4.1"

    # noinspection PyMethodMayBeStatic
    def get_file_specs(self, d_current):
        subdir = f"CONUS/{d_current.strftime('%Y%m%d')}"
        filename = f"{d_current.strftime('%Y%m%d%H')}.01h"
        return [(subdir, filename)]
