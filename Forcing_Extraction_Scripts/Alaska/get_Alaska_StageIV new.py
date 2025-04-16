import os
import shutil

from Forcing_Extraction_Scripts.forecast_download_base import ForecastDownloader


class AlaskaStageIVDownloader(ForecastDownloader):
    """
    Downloader for Alaska Stage IV precipitation analysis.

    - Server organizes files in pcpanl.YYYYMMDD/ directories.
    - Filenames follow: st4_ak.YYYYMMDDHH.06h.grb2
    - Files are only available every 6 hours (00z, 06z, 12z, 18z).
    - Output directory is flattened — all files saved directly to outDir.
    """

    @property
    def base_url(self):
        return "https://nomads.ncep.noaa.gov/pub/data/nccf/com/pcpanl/v4.1"

    @property
    def lock_name(self):
        return "Alaska_StageIV"

    def get_download_targets(self, d_current):
        # Only download if the hour is divisible by 6 (i.e., every 6 hours)
        return [0] if d_current.hour % 6 == 0 else []

    def build_output_dir(self, d_current):
        # All files go to the main output directory (flat structure)
        return self.out_dir

    def build_file_url_and_name(self, d_current, _):
        """
        Constructs the URL and filename for Alaska Stage IV files.
        - Located in pcpanl.YYYYMMDD/
        - Named as: st4_ak.YYYYMMDDHH.06h.grb2
        """
        date_folder = f"pcpanl.{d_current.strftime('%Y%m%d')}"
        filename = f"st4_ak.{d_current.strftime('%Y%m%d%H')}.06h.grb2"
        url = os.path.join(self.base_url, date_folder, filename)
        return url, filename

    def _cleanup_old_data(self):
        """
        Cleans the full output directory during each cycle. This is a conservative
        approach since the original script removes the entire directory.
        """
        for hour in range(self.cleanback_hours, self.lagback_hours, -1):
            d_current = self.d_now - self._hour_delta(hour)
            if os.path.isdir(self.out_dir):
                print(f"Removing old StageIV data from: {self.out_dir}")
                shutil.rmtree(self.out_dir)
                break


if __name__ == "__main__":
    downloader = AlaskaStageIVDownloader.from_cli_args()
    downloader.run()
