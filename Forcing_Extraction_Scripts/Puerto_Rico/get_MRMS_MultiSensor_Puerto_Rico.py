from abc import ABC

from Forcing_Extraction_Scripts.forecast_download_base import FixedFileDownloader


class MRMSMultiSensorPuertoRicoDownloader(FixedFileDownloader, ABC):
    """
    Downloader for MRMS MultiSensor QPE over Puerto Rico.

    - Pass1 and Pass2 are downloaded separately.
    - Files organized by date in respective folders.
    """

    @property
    def base_url(self):
        return "https://mrms.ncep.noaa.gov/data/2D/CARIB/MultiSensor_QPE_01H_"

    def get_file_specs(self, d_current):
        specs = []
        for pass_num in ["Pass1", "Pass2"]:
            subdir = f"MultiSensor_QPE_01H_{pass_num}/{d_current.strftime('%Y%m%d')}"
            filename = f"MRMS_MultiSensor_QPE_01H_{pass_num}_00.00_{d_current.strftime('%Y%m%d')}-{d_current.strftime('%H')}0000.grib2.gz"
            specs.append((subdir, filename))
        return specs
