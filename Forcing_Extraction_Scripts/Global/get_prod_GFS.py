import os

from Forcing_Extraction_Scripts.forecast_download_base import ForecastDownloader

DIAG_LOG = "/ngen-app/data/logs/gfs_diagnostics.log"

class GFSDownloader(ForecastDownloader):
    """
    Downloader for GFS operational forecast data.

    - Available at 00Z, 06Z, 12Z, 18Z only.
    - Downloads sfluxgrbfNN.grib2 files out to 240h (expandable).
    - Files are organized by: gfs.YYYYMMDD/HH/atmos/
    """

    default_lookback = 8
    default_cleanback = 240
    default_lagback = 4

    @property
    def base_url(self):
        return "https://noaa-gfs-bdp-pds.s3.amazonaws.com"

    #def should_process_hour(self, d_start):
    #    with open(DIAG_LOG, "a") as diag_log:
    #        diag_log.write(
    #            f"[GFS should_process_hour check for start time hour: {d_start.hour}\n"
    #        )
    #    return d_start.hour in [0, 6, 12, 18]

    def get_download_targets(self, _):
        hourly = range(1, 121)  # 1 through 120
        every_3h = range(123, 241, 3)  # 123 through 240, step of 3
        return list(hourly) + list(every_3h)

    def build_output_dir(self, d_start, _):

        return os.path.join(
            self.out_dir,
            f"gfs.{d_start.strftime('%Y%m%d')}",
            d_start.strftime('%H'),
            "atmos"
        )

    def build_file_url_and_name(self, d_start, forecast_hour, _):

        with open(DIAG_LOG, "a") as diag_log:
            diag_log.write(
                f"[GFS build_file_url_and_name] Original d_start: {d_start}\n"
            )

        if d_start.hour in [0, 1, 2, 3, 4, 5]:
            d_start = d_start.replace(hour=0)
        elif d_start.hour in [6, 7, 8, 9, 10, 11]:
            d_start = d_start.replace(hour=6)
        elif d_start.hour in [12, 13, 14, 15, 16, 17]:
            d_start = d_start.replace(hour=12)
        elif d_start.hour in [18, 19, 20, 21, 22, 23]:
            d_start = d_start.replace(hour=18)

        with open(DIAG_LOG, "a") as diag_log:
            diag_log.write(
                f"[GFS build_file_url_and_name] Adjusted d_start: {d_start}\n"
            )

        fhr = str(forecast_hour).zfill(3)
        filename = f"gfs.t{d_start.strftime('%H')}z.sfluxgrbf{fhr}.grib2"
        with open(DIAG_LOG, "a") as diag_log:
            diag_log.write(
                f"[GFS build_file_url_and_name] d_start: {d_start}, forecast_hour: {forecast_hour}, filename: {filename}\n"
            )
        url = os.path.join(
            self.base_url,
            f"gfs.{d_start.strftime('%Y%m%d')}",
            d_start.strftime('%H'),
            "atmos",
            filename
        )

        with open(DIAG_LOG, "a") as diag_log:
            diag_log.write(
                f"[GFS build_file_url_and_name] URL: {url}\n"
            )

        return url, filename

    @property
    def recursive_cleanup(self) -> bool:
        return True


if __name__ == "__main__":
    downloader = GFSDownloader.from_cli_args()
    downloader.run()
