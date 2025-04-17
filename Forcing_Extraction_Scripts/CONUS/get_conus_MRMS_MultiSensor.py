from abc import ABC

from Forcing_Extraction_Scripts.forecast_download_base import FixedFileDownloader


class MRMSMultiSensorConusDownloader(FixedFileDownloader, ABC):
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
        return "https://mrms.ncep.noaa.gov/data/2D/"

    def build_output_dir(self, d_current):
        return self.out_dir

    def get_file_specs(self, d_current):
        specs = []
        for pass_num in ["Pass1", "Pass2"]:
            subdir = f"MultiSensor_QPE_01H_{pass_num}"
            filename = f"MRMS_MultiSensor_QPE_01H_{pass_num}_00.00_{d_current.strftime('%Y%m%d')}-{d_current.strftime('%H')}0000.grib2.gz"
            specs.append((subdir, filename))
        return specs


if __name__ == "__main__":
    downloader = MRMSMultiSensorConusDownloader.from_cli_args()
    downloader.run()
