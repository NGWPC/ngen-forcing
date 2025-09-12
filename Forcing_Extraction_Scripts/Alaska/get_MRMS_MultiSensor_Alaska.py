from abc import ABC

from Forcing_Extraction_Scripts.forecast_download_base import ForecastDownloader


class MRMSMultiSensorAlaskaDownloader(ForecastDownloader, ABC):
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

    # noinspection PyMethodMayBeStatic
    def get_file_specs(self, d_start):
        specs = []
        for pass_num in ["Pass1", "Pass2"]:
            subdir = f"MultiSensor_QPE_01H_{pass_num}/{d_start.strftime('%Y%m%d')}"
            filename = f"MRMS_MultiSensor_QPE_01H_{pass_num}_00.00_{d_start.strftime('%Y%m%d')}-{d_start.strftime('%H')}0000.grib2.gz"
            specs.append((subdir, filename))
        return specs
