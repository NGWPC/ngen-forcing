import argparse
import os
from Forcing_Extraction_Scripts.forecast_base import ForecastDownloader


class MRMSMultiSensorDownloader(ForecastDownloader):
    """
    Downloader for MRMS MultiSensor hourly QPE data (Pass1 and Pass2).

    - Pass1 and Pass2 are two versions of the same hourly QPE product.
    - Files are stored in subdirectories by pass number and date:
        MultiSensor_QPE_01H_Pass1/YYYYMMDD/...
        MultiSensor_QPE_01H_Pass2/YYYYMMDD/...

    This downloader overrides cleanup and download logic because:
    - There is no forecast-hour loop.
    - We always download two fixed files per hour: one from each Pass.
    """

    @property
    def base_url(self):
        # Root URL is pass-agnostic; we append /Pass1 or /Pass2 per file.
        return "https://mrms.ncep.noaa.gov/data/2D/MultiSensor_QPE_01H_"

    @property
    def lock_name(self):
        return "MRMS_MultiSensor_CONUS"

    def get_download_targets(self, _):
        return ["Pass1", "Pass2"]

    def build_output_dir(self, d_current):
        # We'll create per-pass directories during download step
        return self.out_dir

    def _download_data(self):
        """
        Downloads both Pass1 and Pass2 files for each target hour.
        Each file is saved to a dated subfolder under its respective pass directory.
        """
        for hour in range(self.lookback_hours, self.lagback_hours, -1):
            d_current = self.d_now - self._hour_delta(hour)
            for pass_num in ["Pass1", "Pass2"]:
                subdir = os.path.join(self.out_dir, f"MultiSensor_QPE_01H_{pass_num}", d_current.strftime('%Y%m%d'))
                os.makedirs(subdir, exist_ok=True)

                filename = f"MRMS_MultiSensor_QPE_01H_{pass_num}_00.00_{d_current.strftime('%Y%m%d')}-{d_current.strftime('%H')}0000.grib2.gz"
                url = os.path.join(self.base_url + pass_num, filename)
                out_path = os.path.join(subdir, filename)

                if not os.path.isfile(out_path):
                    self._download_file(url, out_path)


if __name__ == "__main__":
    downloader = MRMSMultiSensorDownloader.from_cli_args()
    downloader.run()