import os

from Forcing_Extraction_Scripts.forecast_download_base import ForecastDownloader


class AlaskaHRRRDownloader(ForecastDownloader):
    """
    Downloader for Alaska HRRR surface forecast data.

    - Files are stored under `hrrr.YYYYMMDD/alaska/` on the NOMADS server.
    - File naming pattern: hrrr.t{HH}z.wrfsfcf{fhr}.ak.grib2
    - Forecast range depends on cycle:
        - 00z: 48 hours
        - All others (every 3 hours): 18 hours
    """

    default_lookback = 36
    default_cleanback = 240
    default_lagback = 1

    @property
    def base_url(self):
        return "https://nomads.ncep.noaa.gov/pub/data/nccf/com/hrrr/prod"

    def should_process_hour(self, d_current):
        return d_current.hour % 3 == 0

    def get_download_targets(self, d_current):
        # Forecast hours vary depending on cycle
        if d_current.hour % 3 == 0:
            return range(0, 49) if d_current.hour == 0 else range(0, 19)
        else:
            return []  # Skip non-forecast cycles

    def build_output_dir(self, d_current):
        return os.path.join(self.out_dir, "hrrr." + d_current.strftime('%Y%m%d'), "alaska")

    def build_file_url_and_name(self, d_current, fhr):
        """
        Alaska HRRR files use .ak.grib2 extension and are in the /alaska/ folder.
        """
        fhr_str = str(fhr).zfill(2)
        filename = f"hrrr.t{d_current.strftime('%H')}z.wrfsfcf{fhr_str}.ak.grib2"
        date_path = "hrrr." + d_current.strftime('%Y%m%d')
        url = os.path.join(self.base_url, date_path, "alaska", filename)
        return url, filename


if __name__ == "__main__":
    downloader = AlaskaHRRRDownloader.from_cli_args()
    downloader.run()
