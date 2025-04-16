import os
from Forcing_Extraction_Scripts.forecast_download_base import ForecastDownloader


class MRMSMultiSensorHawaiiDownloader(ForecastDownloader):
    """
    Downloader for MRMS MultiSensor QPE (Pass1 and Pass2) for Hawaii.

    - Two separate files per hour: Pass1 and Pass2.
    - Files are stored under: MultiSensor_QPE_01H_Pass1/YYYYMMDD/...
    """

    @property
    def base_url(self):
        return "https://mrms.ncep.noaa.gov/data/2D/HAWAII/MultiSensor_QPE_01H_"

    def get_download_targets(self, _):
        return ["Pass1", "Pass2"]

    def build_output_dir(self, _):
        return self.out_dir

    def build_file_url_and_name(self, d_current, target):
        raise NotImplementedError("This downloader overrides _download_data directly.")

    def _download_data(self):
        for hour in range(self.lookback_hours, self.lagback_hours, -1):
            d_cycle = self.d_now - self._hour_delta(hour)

            for pass_num in self.get_download_targets(d_cycle):
                subdir = os.path.join(self.out_dir, f"MultiSensor_QPE_01H_{pass_num}", d_cycle.strftime('%Y%m%d'))
                os.makedirs(subdir, exist_ok=True)
                filename = f"MRMS_MultiSensor_QPE_01H_{pass_num}_00.00_{d_cycle.strftime('%Y%m%d')}-{d_cycle.strftime('%H')}0000.grib2.gz"
                url = os.path.join(self.base_url + pass_num, filename)
                out_path = os.path.join(str(subdir), filename)  # Explicit cast to avoid Pycharm warning
                if not os.path.isfile(out_path):
                    self._download_file(url, out_path)


if __name__ == "__main__":
    downloader = MRMSMultiSensorHawaiiDownloader.from_cli_args()
    downloader.run()
