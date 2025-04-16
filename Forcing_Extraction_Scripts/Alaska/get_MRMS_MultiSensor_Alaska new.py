import os

from Forcing_Extraction_Scripts.forecast_base import ForecastDownloader


class MRMSMultiSensorAlaskaDownloader(ForecastDownloader):
    """
    Downloader for MRMS MultiSensor QPE files for Alaska (Pass1 and Pass2).

    - Files are stored under:
        /MultiSensor_QPE_01H_Pass1/YYYYMMDD/
        /MultiSensor_QPE_01H_Pass2/YYYYMMDD/
    - Each hour has one file per pass:
        MRMS_MultiSensor_QPE_01H_PassX_00.00_YYYYMMDD-HH0000.grib2.gz
    """

    @property
    def base_url(self):
        return "https://mrms.ncep.noaa.gov/data/2D/ALASKA/MultiSensor_QPE_01H_"

    @property
    def lock_name(self):
        return "Alaska_MRMS_MultiSensor"

    def get_download_targets(self, _):
        # Two passes available per hour
        return ['Pass1', 'Pass2']

    def build_output_dir(self, d_current):
        # Not used directly — subdirectories are created dynamically during download
        return self.out_dir

    def _cleanup_old_data(self):
        """
        Remove Pass1 and Pass2 files from output directory that are older than
        the cleanBackHours threshold.
        """
        for hour in range(self.cleanback_hours, self.lookback_hours, -1):
            d_current = self.d_now - self._hour_delta(hour)
            date_str = d_current.strftime('%Y%m%d')
            hour_str = d_current.strftime('%H')

            for pass_type in ['Pass1', 'Pass2']:
                filename = f"MRMS_MultiSensor_QPE_01H_{pass_type}_00.00_{date_str}-{hour_str}0000.grib2.gz"
                file_path = os.path.join(self.out_dir, f"MultiSensor_QPE_01H_{pass_type}", filename)
                if os.path.isfile(file_path):
                    print(f"Removing old file: {file_path}")
                    os.remove(file_path)

    def _download_data(self):
        """
        Downloads both Pass1 and Pass2 files for each hour in the lookback window.
        Files are saved to dated subfolders within the respective Pass directories.
        """
        for hour in range(self.lookback_hours, self.lagback_hours, -1):
            d_current = self.d_now - self._hour_delta(hour)
            date_str = d_current.strftime('%Y%m%d')
            hour_str = d_current.strftime('%H')

            for pass_type in ['Pass1', 'Pass2']:
                subdir = os.path.join(self.out_dir, f"MultiSensor_QPE_01H_{pass_type}", date_str)
                os.makedirs(subdir, exist_ok=True)

                filename = f"MRMS_MultiSensor_QPE_01H_{pass_type}_00.00_{date_str}-{hour_str}0000.grib2.gz"
                url = os.path.join(self.base_url + pass_type, filename)
                out_path = os.path.join(subdir, filename)

                if os.path.isfile(out_path):
                    print(f"{out_path} already exists. Skipping.")
                    continue

                self._download_file(url, out_path)


if __name__ == "__main__":
    downloader = MRMSMultiSensorAlaskaDownloader.from_cli_args()
    downloader.run()
