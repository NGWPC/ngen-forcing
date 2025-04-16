import os
import shutil

from Forcing_Extraction_Scripts.forecast_download_base import ForecastDownloader


class CFSv2Downloader(ForecastDownloader):
    """
    Downloader for CFSv2 forecast data (6-hour interval outputs for 30 days).

    - Data is issued at 00Z, 06Z, 12Z, 18Z.
    - Each cycle produces 6-hour forecasts out to ~7.5 days (up to 60h shown here).
    - Files live in: cfs.YYYYMMDD/HH/6hrly_grib_01/
    - Filenames follow format: flxf<valid_time>.01.<init_time>.grb2
    """

    @property
    def base_url(self):
        return "https://nomads.ncep.noaa.gov/pub/data/nccf/com/cfs/prod"

    @property
    def lock_name(self):
        return "CFSv2"

    def get_download_targets(self, d_current):
        return range(0, 60, 6) if d_current.hour in [0, 6, 12, 18] else []

    def build_output_dir(self, d_current):
        return os.path.join(
            self.out_dir,
            f"cfs.{d_current.strftime('%Y%m%d')}",
            d_current.strftime('%H'),
            "6hrly_grib_01"
        )

    def build_file_url_and_name(self, d_current, fhr):
        # Target file has valid_time (forecast) and init_time (cycle) in name
        valid_time = d_current + self._hour_delta(fhr)
        init_time = d_current.strftime('%Y%m%d%H')
        valid_time_str = valid_time.strftime('%Y%m%d%H')
        filename = f"flxf{valid_time_str}.01.{init_time}.grb2"
        url = os.path.join(
            self.base_url,
            f"cfs.{d_current.strftime('%Y%m%d')}",
            d_current.strftime('%H'),
            "6hrly_grib_01",
            filename
        )
        return url, filename

    def _cleanup_old_data(self):
        """
        Remove the full path: .../6hrly_grib_01
        Then remove empty hour and day folders if applicable.
        """
        for hour in range(self.cleanback_hours, self.lookback_hours, -1):
            d_current = self.d_now - self._hour_delta(hour)

            # Clean nested structure
            target_dir = self.build_output_dir(d_current)

            if os.path.isdir(target_dir):
                print(f"Removing old CFSv2 data from: {target_dir}")
                shutil.rmtree(target_dir)

            # Clean parent hour directory if empty
            hour_dir = os.path.dirname(target_dir)
            if os.path.isdir(hour_dir) and not os.listdir(hour_dir):
                shutil.rmtree(hour_dir)

            # Clean date directory if empty
            day_dir = os.path.dirname(hour_dir)
            if os.path.isdir(day_dir) and not os.listdir(day_dir):
                shutil.rmtree(day_dir)


if __name__ == "__main__":
    downloader = CFSv2Downloader.from_cli_args()
    downloader.run()
