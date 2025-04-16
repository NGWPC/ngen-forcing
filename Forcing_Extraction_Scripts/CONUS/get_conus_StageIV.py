import os
import shutil

from Forcing_Extraction_Scripts.forecast_download_base import ForecastDownloader


class StageIVDownloader(ForecastDownloader):
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

    @property
    def lock_name(self):
        return "Conus_StageIV"

    def get_download_targets(self, _):
        # Only one file per hour; no forecast range
        return [0]

    def build_output_dir(self, _):
        # All files go directly to self.out_dir (flattened structure)
        return self.out_dir

    def build_file_url_and_name(self, d_current, _):
        """
        Compose the full URL and filename for the hourly Stage IV file.
        Server path: /pcpanl.YYYYMMDD/st4_conus.YYYYMMDDHH.01h.grb2
        """
        date_folder = "pcpanl." + d_current.strftime('%Y%m%d')
        filename = f"st4_conus.{d_current.strftime('%Y%m%d%H')}.01h.grb2"
        url = os.path.join(self.base_url, date_folder, filename)
        return url, filename

    def _cleanup_old_data(self):
        """
        Remove daily directories if present (e.g., pcpanl.20240414),
        since the base logic expects hourly data but Stage IV uses daily folders.
        """
        for hour in range(self.cleanback_hours, self.lagback_hours, -1):
            d_current = self.d_now - self._hour_delta(hour)
            dir_path = os.path.join(self.out_dir, "pcpanl." + d_current.strftime('%Y%m%d'))
            if os.path.isdir(dir_path):
                print(f"Removing old CONUS StageIV data from: {dir_path}")
                shutil.rmtree(dir_path)


if __name__ == "__main__":
    downloader = StageIVDownloader.from_cli_args()
    downloader.run()
