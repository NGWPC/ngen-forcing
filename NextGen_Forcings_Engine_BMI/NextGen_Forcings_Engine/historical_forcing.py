"""Module for processing AORC and NWM data."""

import datetime
import logging
from contextlib import contextmanager
from functools import lru_cache
from time import time

import dask
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import s3fs
import xarray as xr
from dotenv import find_dotenv, load_dotenv
from mpi4py.futures import MPICommExecutor
from pyproj import CRS, Transformer
from shapely import box, transform

from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.core.config import (
    ConfigOptions,
)
from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.core.parallel import MpiConfig
from nextgen_forcings_ewts import MODULE_NAME

LOG = logging.getLogger(MODULE_NAME)


class BaseProcessor:
    """Base class for data processors."""

    def __init__(
        self,
        config_options: ConfigOptions,
        mpi_config: MpiConfig,
        wrf_hydro_geo_meta: dict,
    ):
        """Initialize base processor."""
        self.config_options = config_options
        self.mpi_config = mpi_config
        self.wrf_hydro_geo_meta = wrf_hydro_geo_meta
        self.dest_crs = CRS(4326)
        self.buffer = 0.01  # degree buffer around bounding box

    @property
    def box(self):
        """Shapely box for spatial bounds."""
        return box(
            self.xmin - self.buffer,
            self.ymin - self.buffer,
            self.xmax + self.buffer,
            self.ymax + self.buffer,
        )

    @property
    def transformer(self):
        """Transformer for coordinate reference system conversion."""
        return Transformer.from_crs(self.dest_crs, self.src_crs, always_xy=True)

    @property
    @lru_cache
    def reprojected_box(self):
        """Reprojected bounding box to source CRS."""
        return transform(self.box, self.transformer.transform, interleaved=False)

    @property
    def reprojected_xmin(self) -> float:
        """Minimum longitude in source CRS."""
        return self.reprojected_box.bounds[0]

    @property
    def reprojected_ymin(self) -> float:
        """Minimum latitude in source CRS."""
        return self.reprojected_box.bounds[1]

    @property
    def reprojected_xmax(self) -> float:
        """Maximum longitude in source CRS."""
        return self.reprojected_box.bounds[2]

    @property
    def reprojected_ymax(self) -> float:
        """Maximum latitude in source CRS."""
        return self.reprojected_box.bounds[3]

    @property
    def current_time_datetime(self):
        """Datetime object for the current time step."""
        return np.datetime64(self.current_time)

    @property
    def xmax(self) -> float:
        """Maximum longitude from geospatial metadata."""
        return np.max(self.wrf_hydro_geo_meta.lon_bounds)

    @property
    def xmin(self) -> float:
        """Minimum longitude from geospatial metadata."""
        return np.min(self.wrf_hydro_geo_meta.lon_bounds)

    @property
    def ymax(self) -> float:
        """Maximum latitude from geospatial metadata."""
        return np.max(self.wrf_hydro_geo_meta.lat_bounds)

    @property
    def ymin(self) -> float:
        """Minimum latitude from geospatial metadata."""
        return np.min(self.wrf_hydro_geo_meta.lat_bounds)

    @contextmanager
    def timing_block(self, step_str: str):
        """Context manager for timing code execution.

            Args:
                step_str: Description of the step being timed.
        with MPICommExecutor(comm=MpiConfig.comm, root=0) as executor:
        """
        start = time()
        yield
        end = time()
        LOG.debug(f"  Execution time for {step_str}: {round(end - start, 2)} seconds")

    def slice_ds(
        self, ds: xr.Dataset, start_time: np.datetime64, end_time: np.datetime64
    ) -> xr.Dataset:
        """Subset dataset to spatial and temporal bounds.

        :return: Sliced Dataset
        """
        with self.timing_block("slicing dataset"):
            sliced_ds = ds.sel(
                {
                    self.x_label: slice(self.reprojected_xmin, self.reprojected_xmax),
                    self.y_label: slice(self.reprojected_ymin, self.reprojected_ymax),
                    self.time_label: slice(start_time, end_time),
                }
            )
            if sliced_ds[self.x_label].size == 0 or sliced_ds[self.y_label].size == 0:
                raise ValueError(
                    "Unable to find data for the specified input dataset, domain, and catchment locations. Check that the dataset is supported for the given domain"
                )
        return sliced_ds

    @property
    def time_min(self) -> np.datetime64:
        """Calculate minimum time for forecast window.

        :return: Minimum time as np.datetime64
        """
        return np.datetime64(self.config_options.b_date_proc)

    @property
    def dates(self):
        """Date range for the forecast window."""
        return pd.date_range(start=self.time_min, end=self.time_max, freq="h")

    @property
    def years(self):
        """List of years in the date range."""
        return list(set([date.year for date in self.dates]))

    @property
    def year_start_stop_dict(self):
        """Dictionary of start and stop dates for each year in the date range."""
        year_dict = {}
        for year in self.years:
            year_dates = [date for date in self.dates if date.year == year]
            year_dict[year] = (year_dates[0], year_dates[-1])
        return year_dict

    @property
    def time_max(self) -> np.datetime64:
        """Calculate maximum time for forecast window.

        :return: Maximum time as np.datetime64
        """
        return (
            self.time_min
            + np.timedelta64(self.config_options.fcst_input_horizons[0], "m")
            + np.timedelta64(self.config_options.fcst_freq, "m")
        )

    @property
    @lru_cache
    def aws_ds(self) -> xr.Dataset:
        """Materialize lazy dask arrays into memory.

        :return: Computed Dataset
        """
        final_ds = None

        with self.timing_block("computing dataset"):
            with MPICommExecutor(comm=self.mpi_config.comm, root=0) as executor:
                with dask.config.set(scheduler=executor):
                    if self.mpi_config.rank == 0:
                        final_ds = self.sliced_ds.compute().rio.write_crs(self.src_crs)
                        # final_ds= final_ds.rio.clip(self.gdf.geometry.values,all_touched=True)
        self.mpi_config.comm.barrier()
        final_ds = self.mpi_config.comm.bcast(final_ds, root=0)

        return final_ds

    def process(self, current_time: str) -> xr.Dataset:
        """Process forcing data for the given configuration and geospatial metadata."""
        self.current_time = current_time
        final_ds = self.aws_ds.sel(time=self.current_time_datetime)
        # if self.mpi_config.rank == 0:
        # self.plot_precip(final_ds)
        # self.write_sum_tif()
        return final_ds

    @property
    @lru_cache
    def gdf(self):
        """Load and cache the geospatial dataframe."""
        gdf = gpd.read_file(self.config_options.geopackage, layer="divides")
        return gdf.to_crs(self.src_crs)

    def plot_precip(self, ds: xr.Dataset):
        """Plot precipitation field for the current time step."""
        qmesh = ds[self.precip_variable].plot()
        self.gdf.plot(ax=qmesh.axes, facecolor="none", edgecolor="black")

        plt.title(f"Precipitation at {str(ds.time.values)}")
        plt.savefig(
            f"{self.precip_variable}_{str(ds.time.values)}_{self.mpi_config.rank}.png"
        )
        plt.clf()

    def write_sum_tif(self):
        """Write precip sum raster."""
        self.aws_ds[self.precip_variable].sum("time").rio.write_crs(
            self.src_crs
        ).rio.to_raster(f"{self.precip_variable}_sum.tif")


class AORCConusProcessor(BaseProcessor):
    """Processor for AORC data."""

    def __init__(
        self,
        config_options: ConfigOptions,
        mpi_config: MpiConfig,
        wrf_hydro_geo_meta: dict,
    ):
        """Initialize AORC processor."""
        super().__init__(config_options, mpi_config, wrf_hydro_geo_meta)
        self.dataset_name = "AORC"
        self.precip_variable = "APCP_surface"
        self.x_label = "longitude"
        self.y_label = "latitude"
        self.time_label = "time"

    @property
    @lru_cache
    def src_crs(self):
        """Get source CRS from dataset."""
        return xr.open_zarr(
            self.url(self.years[0]), storage_options={"anon": True}
        ).rio.crs

    def url(self, year: str) -> str:
        """Generate AORC S3 zarr URL for current year.

        :return: AORC S3 zarr URL
        """
        url = self.config_options.aorc_conus_year_url.format(
            source=self.config_options.aorc_conus_source, year=year
        )
        LOG.debug(f"AORC S3 URL: {url}\n")

        return url

    @property
    def sliced_ds(self) -> xr.Dataset:
        """Open dataset.

        :return: xarray Dataset
        :raises Exception: If zarr open fails
        """
        datasets = []
        for year, (start_date, end_date) in self.year_start_stop_dict.items():
            try:
                with self.timing_block(f"lazy loading {self.dataset_name} data"):
                    ds = xr.open_zarr(self.url(year), storage_options={"anon": True})
                    datasets.append(self.slice_ds(ds, start_date, end_date))
            except Exception as e:
                LOG.critical(
                    f"Error opening {self.dataset_name} data from {self.url(year)}: {e}\n"
                )
                raise e
        return (
            xr.concat(datasets, dim="time")
            .rename({self.x_label: "x", self.y_label: "y"})
            .rio.write_crs(self.src_crs)
        )


class AORCAlaskaProcessor(AORCConusProcessor):
    """Processor for AORC Alaska data."""

    def __init__(
        self,
        config_options: ConfigOptions,
        mpi_config: MpiConfig,
        wrf_hydro_geo_meta: dict,
    ):
        """Initialize AORC Alaska processor."""
        super().__init__(config_options, mpi_config, wrf_hydro_geo_meta)
        self.dataset_name = "AORC"
        self.precip_variable = "APCP_surface"
        self.x_label = "longitude"
        self.y_label = "latitude"
        self.time_label = "time"

    @property
    @lru_cache
    def src_crs(self):
        """Get source CRS from dataset."""
        return xr.open_zarr(
            self.url(self.years[0]), storage_options={"anon": True}
        ).rio.crs

    def url(self, date: datetime) -> str:
        """Generate AORC S3 zarr URL for current year.

        :return: AORC S3 zarr URL
        """
        url = self.config_options.aorc_alaska_url.format(
            source=self.config_options.aorc_alaska_source,
            year=date.year,
            month=date.month,
            date=date.strftime("%Y%m%d%H"),
        )
        LOG.debug(f"AORC S3 URL: {url}\n")

        return url

    @property
    def sliced_ds(self) -> xr.Dataset:
        """Open dataset.

        :return: xarray Dataset
        :raises Exception: If zarr open fails
        """
        datasets = []
        for date in self.dates:
            try:
                with self.timing_block(f"lazy loading {self.dataset_name} data"):
                    load_dotenv(find_dotenv())
                    s3 = s3fs.S3FileSystem()
                    with s3.open(self.url(date)) as f:
                        ds = xr.open_dataset(f, engine="h5netcdf")
                        print(ds)
                        datasets.append(
                            self.slice_ds(ds, date, date + np.timedelta64(1, "h"))
                        )
            except Exception as e:
                LOG.critical(
                    f"Error opening {self.dataset_name} data from {self.url(date)}: {e}\n"
                )

                raise e
        return xr.concat(datasets, dim="time").rename(
            {self.x_label: "x", self.y_label: "y"}
        )


class NWMV3Processor(BaseProcessor):
    """Processor for NWM data."""

    def __init__(
        self,
        config_options: ConfigOptions,
        mpi_config: MpiConfig,
        wrf_hydro_geo_meta: dict,
    ):
        """Initialize NWM processor."""
        super().__init__(config_options, mpi_config, wrf_hydro_geo_meta)
        self.dataset_name = "NWM"
        self.precip_variable = "RAINRATE"
        self.x_label = "x"
        self.y_label = "y"
        self.time_label = "time"

    @property
    @lru_cache
    def src_crs(self):
        """Get source CRS from dataset."""
        return CRS(
            xr.open_zarr(
                self.url(self.vars[0]), storage_options={"anon": True}
            ).crs.attrs["spatial_ref"]
        )

    @property
    def vars(
        self,
    ) -> list[str]:
        """List of NWM variables to extract."""
        return [
            "lwdown",
            "precip",
            "psfc",
            "q2d",
            "swdown",
            "t2d",
            "u2d",
            "v2d",
        ]


class NWMV3ConusProcessor(NWMV3Processor):
    """Processor for NWM CONUS data."""

    def __init__(
        self,
        config_options: ConfigOptions,
        mpi_config: MpiConfig,
        wrf_hydro_geo_meta: dict,
    ):
        """Initialize NWM CONUS processor."""
        super().__init__(config_options, mpi_config, wrf_hydro_geo_meta)

    def url(self, var: str) -> str:
        """Generate NWM S3 zarr URL for current variable.

        :return: NWM S3 zarr URL
        """
        url = self.config_options.nwm_url.format(
            source=self.config_options.nwm_source,
            domain=self.config_options.nwm_domain,
            var=var,
        )
        LOG.debug(f"NWM S3 URL: {url}\n")

        return url

    @property
    def sliced_ds(self) -> xr.Dataset:
        """Open dataset.

        :return: xarray Dataset
        :raises Exception: If zarr open fails
        """
        datasets = []
        for var in self.vars:
            try:
                with self.timing_block(f"lazy loading {self.dataset_name} data"):
                    ds = xr.open_zarr(self.url(var), storage_options={"anon": True})
                    datasets.append(self.slice_ds(ds, self.time_min, self.time_max))
            except Exception as e:
                LOG.critical(
                    f"Error opening {self.dataset_name} data from {self.url(var)}: {e}\n"
                )
                raise e
        return xr.merge(datasets, compat="override").rename(
            {self.x_label: "x", self.y_label: "y"}
        )


class NWMV3OConusProcessor(NWMV3Processor):
    """Processor for NWM OCONUS data."""

    def __init__(
        self,
        config_options: ConfigOptions,
        mpi_config: MpiConfig,
        wrf_hydro_geo_meta: dict,
    ):
        """Initialize NWM OCONUS processor."""
        super().__init__(config_options, mpi_config, wrf_hydro_geo_meta)

    def url(self, var: str = None) -> str:
        """Generate NWM S3 zarr URL.

        :return: NWM S3 zarr URL
        """
        url = self.config_options.nwm_url.format(
            source=self.config_options.nwm_source, domain=self.config_options.nwm_domain
        )
        LOG.debug(f"NWM S3 URL: {url}\n")

        return url

    @property
    def sliced_ds(self) -> xr.Dataset:
        """Open dataset.

        :return: xarray Dataset
        :raises Exception: If zarr open fails
        """
        try:
            with self.timing_block(f"lazy loading {self.dataset_name} data"):
                ds = xr.open_zarr(self.url(), storage_options={"anon": True})
                return self.slice_ds(ds, self.time_min, self.time_max).rename(
                    {self.x_label: "x", self.y_label: "y"}
                )
        except Exception as e:
            LOG.critical(
                f"Error opening {self.dataset_name} data from {self.url()}: {e}\n"
            )
            raise e
