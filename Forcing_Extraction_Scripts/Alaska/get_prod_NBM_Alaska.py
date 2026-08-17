import os

from Forcing_Extraction_Scripts.forecast_download_base import ForecastDownloader


class NBMAlaskaDownloader(ForecastDownloader):
    """
    Downloader for Alaska NBM forecast data.

    - Files are located under: blend.YYYYMMDD/HH/core/
    - Files of interest end with .ak.grib2
    """

    @property
    def base_url(self):
        return "https://noaa-nbm-grib2-pds.s3.amazonaws.com"

    def get_download_targets(self, d_start):
        if self.input_horizon == 15:
            # Short range Alaska: cycles at 00/06/12/18Z, hourly f001-f018
            if d_start.hour not in (0, 6, 12, 18):
                return []
            return list(range(1, 19))

        elif self.input_horizon == 45:
            # Short range extended Alaska: cycles at 03/09/15/21Z, hourly f001-f048
            if d_start.hour not in (3, 9, 15, 21):
                return []
            hourly = range(1, 37)  # 1 through 36
            every_3h = range(39, 49, 3)  # 39 through 49, step of 3
            return list(hourly) + list(every_3h)

        elif self.input_horizon == 240:
            # Medium Range Alaska: cycles at 00/06/12/18Z, tiered hourly/3h/6h to f264
            if d_start.hour not in (0, 6, 12, 18):
                return []
            hourly = range(1, 37)  # 1 through 36
            every_3h = range(39, 193, 3)  # 123 through 240, step of 3
            every_6h = range(198, 265, 6)  # 198 through 264, step of 6
            return list(hourly) + list(every_3h) + list(every_6h)

        else:
            # Unexpected AK forecast length
            return []

    def build_output_dir(self, d_start, _):
        return os.path.join(
            self.out_dir,
            f"blend.{d_start.strftime('%Y%m%d')}",
            d_start.strftime('%H'),
            "core"
        )

    def build_file_url_and_name(self, d_start, target, _):
        fhr_str = f"f{str(target).zfill(3)}"
        filename = f"blend.t{d_start.strftime('%H')}z.core.{fhr_str}.ak.grib2"
        url = os.path.join(
            self.base_url,
            f"blend.{d_start.strftime('%Y%m%d')}",
            d_start.strftime('%H'),
            "core",
            filename,
        )
        return url, filename

    @property
    def recursive_cleanup(self) -> bool:
        return True


if __name__ == "__main__":
    downloader = NBMAlaskaDownloader.from_cli_args()
    downloader.run()