import os
import shutil

from Forcing_Extraction_Scripts.forecast_download_base import ForecastDownloader


class GFSDownloader(ForecastDownloader):
    """
    Downloader for GFS operational forecast data.

    - Available at 00Z, 06Z, 12Z, 18Z only.
    - Downloads sfluxgrbfNN.grib2 files out to 18h (expandable).
    - Files are organized by: gfs.YYYYMMDD/HH/atmos/
    """

    @property
    def base_url(self):
        return "https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod"

    @property
    def lock_name(self):
        return "GFS_Full"

    def get_download_targets(self, d_current):
        return range(1, 19) if d_current.hour in [0, 6, 12, 18] else []

    def build_output_dir(self, d_current):
        return os.path.join(
            self.out_dir,
            f"gfs.{d_current.strftime('%Y%m%d')}",
            d_current.strftime('%H'),
            "atmos"
        )

    def build_file_url_and_name(self, d_current, forecast_hour):
        fhr = str(forecast_hour).zfill(3)
        filename = f"gfs.t{d_current.strftime('%H')}z.sfluxgrbf{fhr}.grib2"
        url = os.path.join(
            self.base_url,
            f"gfs.{d_current.strftime('%Y%m%d')}",
            d_current.strftime('%H'),
            "atmos",
            filename
        )
        return url, filename

    def _cleanup_old_data(self):
        """
        Removes .../atmos and cleans up empty hour and day folders if applicable.
        """
        for hour in range(self.cleanback_hours, self.lookback_hours, -1):
            d_current = self.d_now - self._hour_delta(hour)
            target_dir = self.build_output_dir(d_current)

            if os.path.isdir(target_dir):
                print(f"Removing old GFS data from: {target_dir}")
                shutil.rmtree(target_dir)

            # Remove empty parent folders
            hour_dir = os.path.dirname(target_dir)
            if os.path.isdir(hour_dir) and not os.listdir(hour_dir):
                print(f"Removing empty hour directory: {hour_dir}")
                shutil.rmtree(hour_dir)

            day_dir = os.path.dirname(hour_dir)
            if os.path.isdir(day_dir) and not os.listdir(day_dir):
                print(f"Removing empty day directory: {day_dir}")
                shutil.rmtree(day_dir)


if __name__ == "__main__":
    downloader = GFSDownloader.from_cli_args()
    downloader.run()
