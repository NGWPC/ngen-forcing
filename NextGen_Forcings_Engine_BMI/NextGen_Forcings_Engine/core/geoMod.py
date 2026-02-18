import math

import netCDF4
import numpy as np

# For ESMF + shapely 2.x, shapely must be imported first, to avoid segfault "address not mapped to object" stemming from calls such as:
# /usr/local/esmf/lib/libO/Linux.gfortran.64.openmpi.default/libesmf_fullylinked.so(get_geom+0x36)
import shapely
from scipy import spatial

from .. import esmf_utils, nc_utils
from . import err_handler

try:
    import esmpy as ESMF
except ImportError:
    import ESMF

import logging

from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.core.config import (
    ConfigOptions,
)
from NextGen_Forcings_Engine_BMI.NextGen_Forcings_Engine.core.parallel import MpiConfig
from nextgen_forcings_ewts import MODULE_NAME

LOG = logging.getLogger(MODULE_NAME)


class GeoMeta:
    """Abstract class for handling information about the WRF-Hydro domain we are processing forcings to."""

    def __init__(self, config_options: ConfigOptions, mpi_config: MpiConfig):
        """Initialize GeoMeta class variables."""
        self.config_options = config_options
        self.mpi_config = mpi_config
        self.nx_global = None
        self.ny_global = None
        self.nx_global_elem = None
        self.ny_global_elem = None
        self.dx_meters = None
        self.dy_meters = None
        self.latitude_grid = None
        self.longitude_grid = None
        self.element_ids = None
        self.element_ids_global = None
        self.latitude_grid_elem = None
        self.longitude_grid_elem = None
        self.lat_bounds = None
        self.lon_bounds = None
        self.mesh_inds = None
        self.mesh_inds_elem = None
        self.height = None
        self.height_elem = None
        self.sina_grid = None
        self.cosa_grid = None
        self.nodeCoords = None
        self.centerCoords = None
        self.inds = None
        self.slope = None
        self.slp_azi = None
        self.slope_elem = None
        self.slp_azi_elem = None
        self.esmf_grid = None
        self.esmf_lat = None
        self.esmf_lon = None
        self.crs_atts = None
        self.x_coord_atts = None
        self.x_coords = None
        self.y_coord_atts = None
        self.y_coords = None
        self.spatial_global_atts = None

    def initialize_geospatial_metadata(self):
        """Initialize GeoMetaWrfHydro class variables.

        Function that will read in crs/x/y geospatial metadata and coordinates
        from the optional geospatial metadata file IF it was specified by the user in
        the configuration file.
        :return:
        """
        # We will only read information on processor 0. This data is not necessary for the
        # other processors, and is only used in the output routines.
        if self.mpi_config.rank == 0:
            # Open the geospatial metadata file.
            try:
                esmf_nc = netCDF4.Dataset(self.config_options.spatial_meta, "r")
            except Exception as e:
                self.config_options.errMsg = f"Unable to open spatial metadata file: {self.config_options.spatial_meta}"
                raise e

            # Make sure the expected variables are present in the file.
            if "crs" not in esmf_nc.variables.keys():
                self.config_options.errMsg = f"Unable to locate crs variable in: {self.config_options.spatial_meta}"
                raise Exception
            if "x" not in esmf_nc.variables.keys():
                self.config_options.errMsg = f"Unable to locate x variable in: {self.config_options.spatial_meta}"
                raise Exception
            if "y" not in esmf_nc.variables.keys():
                self.config_options.errMsg = f"Unable to locate y variable in: {self.config_options.spatial_meta}"
                raise Exception
            # Extract names of variable attributes from each of the input geospatial variables. These
            # can change, so we are making this as flexible as possible to accomodate future changes.
            try:
                crs_att_names = esmf_nc.variables["crs"].ncattrs()
            except Exception as e:
                self.config_options.errMsg = f"Unable to extract crs attribute names from: {self.config_options.spatial_meta}"
                raise e
            try:
                x_coord_att_names = esmf_nc.variables["x"].ncattrs()
            except Exception as e:
                self.config_options.errMsg = f"Unable to extract x attribute names from: {self.config_options.spatial_meta}"
                raise e
            try:
                y_coord_att_names = esmf_nc.variables["y"].ncattrs()
            except Exception as e:
                self.config_options.errMsg = f"Unable to extract y attribute names from: {self.config_options.spatial_meta}"
                raise e
            # Extract attribute values
            try:
                self.x_coord_atts = {
                    item: esmf_nc.variables["x"].getncattr(item)
                    for item in x_coord_att_names
                }
            except Exception as e:
                self.config_options.errMsg = f"Unable to extract x coordinate attributes from: {self.config_options.spatial_meta}"
                raise e
            try:
                self.y_coord_atts = {
                    item: esmf_nc.variables["y"].getncattr(item)
                    for item in y_coord_att_names
                }
            except Exception as e:
                self.config_options.errMsg = f"Unable to extract y coordinate attributes from: {self.config_options.spatial_meta}"
                raise e
            try:
                self.crs_atts = {
                    item: esmf_nc.variables["crs"].getncattr(item)
                    for item in crs_att_names
                }
            except Exception as e:
                self.config_options.errMsg = f"Unable to extract crs coordinate attributes from: {self.config_options.spatial_meta}"
                raise e

            # Extract global attributes
            try:
                global_att_names = esmf_nc.ncattrs()
            except Exception as e:
                self.config_options.errMsg = f"Unable to extract global attribute names from: {self.config_options.spatial_meta}"
                raise e
            try:
                self.spatial_global_atts = {
                    item: esmf_nc.getncattr(item) for item in global_att_names
                }
            except Exception as e:
                self.config_options.errMsg = f"Unable to extract global attributes from: {self.config_options.spatial_meta}"
                raise e

            # Extract x/y coordinate values
            if len(esmf_nc.variables["x"].shape) == 1:
                try:
                    self.x_coords = esmf_nc.variables["x"][:].data
                except Exception as e:
                    self.config_options.errMsg = f"Unable to extract x coordinate values from: {self.config_options.spatial_meta}"
                    raise e
                try:
                    self.y_coords = esmf_nc.variables["y"][:].data
                except Exception as e:
                    self.config_options.errMsg = f"Unable to extract y coordinate values from: {self.config_options.spatial_meta}"
                    raise e
                # Check to see if the Y coordinates are North-South. If so, flip them.
                if self.y_coords[1] < self.y_coords[0]:
                    self.y_coords[:] = np.flip(self.y_coords[:], axis=0)

            if len(esmf_nc.variables["x"].shape) == 2:
                try:
                    self.x_coords = esmf_nc.variables["x"][:, :].data
                except Exception as e:
                    self.config_options.errMsg = f"Unable to extract x coordinate values from: {self.config_options.spatial_meta}"
                    raise e
                try:
                    self.y_coords = esmf_nc.variables["y"][:, :].data
                except Exception as e:
                    self.config_options.errMsg = f"Unable to extract y coordinate values from: {self.config_options.spatial_meta}"
                    raise e
                # Check to see if the Y coordinates are North-South. If so, flip them.
                if self.y_coords[1, 0] > self.y_coords[0, 0]:
                    self.y_coords[:, :] = np.flipud(self.y_coords[:, :])

            # Close the geospatial metadata file.
            try:
                esmf_nc.close()
            except Exception as e:
                self.config_options.errMsg = f"Unable to close spatial metadata file: {self.config_options.spatial_meta}"
                raise e

        # mpi_config.comm.barrier()

    def calc_slope(self, esmf_nc: netCDF4.Dataset) -> tuple:
        """Calculate slope grids needed for incoming shortwave radiation downscaling.

        Function to calculate slope grids needed for incoming shortwave radiation downscaling
        later during the program.
        :param esmf_nc: The open netCDF4 dataset for the geogrid file, passed in to avoid having to reopen the file multiple times
        :return: A tuple containing slope and slope azimuth for nodes and elements
        """
        # First extract the sina,cosa, and elevation variables from the geogrid file.
        try:
            sina_grid = esmf_nc.variables[self.config_options.sinalpha_var][0, :, :]
        except Exception as e:
            self.config_options.errMsg = (
                f"Unable to extract SINALPHA from: {self.config_options.geogrid}"
            )
            raise e

        try:
            cosa_grid = esmf_nc.variables[self.config_options.cosalpha_var][0, :, :]
        except Exception as e:
            self.config_options.errMsg = (
                f"Unable to extract COSALPHA from: {self.config_options.geogrid}"
            )
            raise e

        try:
            height_dest = esmf_nc.variables[self.config_options.hgt_var][0, :, :]
        except Exception as e:
            self.config_options.errMsg = (
                f"Unable to extract HGT_M from: {self.config_options.geogrid}"
            )
            raise e

        # Ensure cosa/sina are correct dimensions
        if sina_grid.shape[0] != self.ny_global or sina_grid.shape[1] != self.nx_global:
            self.config_options.errMsg = (
                f"SINALPHA dimensions mismatch in: {self.config_options.geogrid}"
            )
            raise Exception
        if cosa_grid.shape[0] != self.ny_global or cosa_grid.shape[1] != self.nx_global:
            self.config_options.errMsg = (
                f"COSALPHA dimensions mismatch in: {self.config_options.geogrid}"
            )
            raise Exception
        if (
            height_dest.shape[0] != self.ny_global
            or height_dest.shape[1] != self.nx_global
        ):
            self.config_options.errMsg = (
                f"HGT_M dimension mismatch in: {self.config_options.geogrid}"
            )
            raise Exception

        # Establish constants
        rdx = 1.0 / self.dx_meters
        rdy = 1.0 / self.dy_meters
        msftx = 1.0
        msfty = 1.0

        slope_out = np.empty([self.ny_global, self.nx_global], np.float32)
        toposlpx = np.empty([self.ny_global, self.nx_global], np.float32)
        toposlpy = np.empty([self.ny_global, self.nx_global], np.float32)
        slp_azi = np.empty([self.ny_global, self.nx_global], np.float32)
        ip_diff = np.empty([self.ny_global, self.nx_global], np.int32)
        jp_diff = np.empty([self.ny_global, self.nx_global], np.int32)
        hx = np.empty([self.ny_global, self.nx_global], np.float32)
        hy = np.empty([self.ny_global, self.nx_global], np.float32)

        # Create index arrays that will be used to calculate slope.
        x_tmp = np.arange(self.nx_global)
        y_tmp = np.arange(self.ny_global)
        x_grid = np.tile(x_tmp[:], (self.ny_global, 1))
        y_grid = np.repeat(y_tmp[:, np.newaxis], self.nx_global, axis=1)
        ind_orig = np.where(height_dest == height_dest)
        ind_ip1 = ((ind_orig[0]), (ind_orig[1] + 1))
        ind_im1 = ((ind_orig[0]), (ind_orig[1] - 1))
        ind_jp1 = ((ind_orig[0] + 1), (ind_orig[1]))
        ind_jm1 = ((ind_orig[0] - 1), (ind_orig[1]))
        ind_ip1[1][np.where(ind_ip1[1] >= self.nx_global)] = self.nx_global - 1
        ind_jp1[0][np.where(ind_jp1[0] >= self.ny_global)] = self.ny_global - 1
        ind_im1[1][np.where(ind_im1[1] < 0)] = 0
        ind_jm1[0][np.where(ind_jm1[0] < 0)] = 0

        ip_diff[ind_orig] = x_grid[ind_ip1] - x_grid[ind_im1]
        jp_diff[ind_orig] = y_grid[ind_jp1] - y_grid[ind_jm1]

        toposlpx[ind_orig] = (
            (height_dest[ind_ip1] - height_dest[ind_im1]) * msftx * rdx
        ) / ip_diff[ind_orig]
        toposlpy[ind_orig] = (
            (height_dest[ind_jp1] - height_dest[ind_jm1]) * msfty * rdy
        ) / jp_diff[ind_orig]
        hx[ind_orig] = toposlpx[ind_orig]
        hy[ind_orig] = toposlpy[ind_orig]
        slope_out[ind_orig] = np.arctan((hx[ind_orig] ** 2 + hy[ind_orig] ** 2) ** 0.5)
        slope_out[np.where(slope_out < 1e-4)] = 0.0
        slp_azi[np.where(slope_out < 1e-4)] = 0.0
        ind_valesmf_nc = np.where(slope_out >= 1e-4)
        slp_azi[ind_valesmf_nc] = (
            np.arctan2(hx[ind_valesmf_nc], hy[ind_valesmf_nc]) + math.pi
        )
        ind_valesmf_nc = np.where(cosa_grid >= 0.0)
        slp_azi[ind_valesmf_nc] = slp_azi[ind_valesmf_nc] - np.arcsin(
            sina_grid[ind_valesmf_nc]
        )
        ind_valesmf_nc = np.where(cosa_grid < 0.0)
        slp_azi[ind_valesmf_nc] = slp_azi[ind_valesmf_nc] - (
            math.pi - np.arcsin(sina_grid[ind_valesmf_nc])
        )

        # Reset temporary arrays to None to free up memory
        toposlpx = None
        toposlpy = None
        height_dest = None
        sina_grid = None
        cosa_grid = None
        ind_valesmf_nc = None
        x_tmp = None
        y_tmp = None
        x_grid = None
        ip_diff = None
        jp_diff = None
        ind_orig = None
        ind_jm1 = None
        ind_jp1 = None
        ind_im1 = None
        ind_ip1 = None
        hx = None
        hy = None

        return slope_out, slp_azi


class GriddedGeoMeta(GeoMeta):
    """Class for handling information about the gridded domain we are processing forcings to."""

    def __init__(self, config_options: ConfigOptions, mpi_config: MpiConfig):
        """Initialize GeoMetaWrfHydro class variables.

        Initialization function to initialize ESMF through ESMPy,
        calculate the global parameters of the WRF-Hydro grid
        being processed to, along with the local parameters
        for this particular processor.
        :return:
        """
        super().__init__(config_options, mpi_config)
        self.nx_local_elem = None
        self.ny_local_elem = None
        # Open the geogrid file and extract necessary information
        # to create ESMF fields.
        if mpi_config.rank == 0:
            try:
                esmf_nc = netCDF4.Dataset(self.config_options.geogrid, "r")
            except Exception as e:
                self.config_options.errMsg = f"Unable to open the WRF-Hydro geogrid file: {self.config_options.geogrid}"
                raise e
            if esmf_nc.variables[self.config_options.lat_var].ndim == 3:
                try:
                    self.nx_global = esmf_nc.variables[
                        self.config_options.lat_var
                    ].shape[2]
                except Exception as e:
                    self.config_options.errMsg = f"Unable to extract X dimension size from latitude variable in: {self.config_options.geogrid}"
                    raise e

                try:
                    self.ny_global = esmf_nc.variables[
                        self.config_options.lat_var
                    ].shape[1]
                except Exception as e:
                    self.config_options.errMsg = f"Unable to extract Y dimension size from latitude in: {self.config_options.geogrid}"
                    raise e

                try:
                    self.dx_meters = esmf_nc.DX
                except Exception as e:
                    self.config_options.errMsg = f"Unable to extract DX global attribute in: {self.config_options.geogrid}"
                    raise e

                try:
                    self.dy_meters = esmf_nc.DY
                except Exception as e:
                    self.config_options.errMsg = f"Unable to extract DY global attribute in: {self.config_options.geogrid}"
                    raise e
            elif esmf_nc.variables[self.config_options.lat_var].ndim == 2:
                try:
                    self.nx_global = esmf_nc.variables[
                        self.config_options.lat_var
                    ].shape[1]
                except Exception as e:
                    self.config_options.errMsg = f"Unable to extract X dimension size from latitude variable in: {self.config_options.geogrid}"
                    raise e

                try:
                    self.ny_global = esmf_nc.variables[
                        self.config_options.lat_var
                    ].shape[0]
                except Exception as e:
                    self.config_options.errMsg = f"Unable to extract Y dimension size from latitude in: {self.config_options.geogrid}"
                    raise e

                try:
                    self.dx_meters = esmf_nc.variables[self.config_options.lon_var].dx
                except Exception as e:
                    self.config_options.errMsg = f"Unable to extract DX global attribute in: {self.config_options.geogrid}"
                    raise e

                try:
                    self.dy_meters = esmf_nc.variables[self.config_options.lat_var].dy
                except Exception as e:
                    self.config_options.errMsg = f"Unable to extract DY global attribute in: {self.config_options.geogrid}"
                    raise e

            else:
                try:
                    self.nx_global = esmf_nc.variables[
                        self.config_options.lon_var
                    ].shape[0]
                except Exception as e:
                    self.config_options.errMsg = f"Unable to extract X dimension size from longitude variable in: {self.config_options.geogrid}"
                    raise e

                try:
                    self.ny_global = esmf_nc.variables[
                        self.config_options.lat_var
                    ].shape[0]
                except Exception as e:
                    self.config_options.errMsg = f"Unable to extract Y dimension size from latitude in: {self.config_options.geogrid}"
                    raise e
                if self.config_options.input_forcings[0] != 23:
                    try:
                        self.dx_meters = esmf_nc.variables[
                            self.config_options.lon_var
                        ].dx
                    except Exception as e:
                        self.config_options.errMsg = f"Unable to extract dx metadata attribute in: {self.config_options.geogrid}"
                        raise e

                    try:
                        self.dy_meters = esmf_nc.variables[
                            self.config_options.lat_var
                        ].dy
                    except Exception as e:
                        self.config_options.errMsg = f"Unable to extract dy metadata attribute in: {self.config_options.geogrid}"
                        raise e
                else:
                    # Manually input the grid spacing since ERA5-Interim does not
                    # internally have this geospatial information within the netcdf file
                    self.dx_meters = 31000
                    self.dy_meters = 31000

        # mpi_config.comm.barrier()

        # Broadcast global dimensions to the other processors.
        self.nx_global = mpi_config.broadcast_parameter(
            self.nx_global, self.config_options, param_type=int
        )
        self.ny_global = mpi_config.broadcast_parameter(
            self.ny_global, self.config_options, param_type=int
        )
        self.dx_meters = mpi_config.broadcast_parameter(
            self.dx_meters, self.config_options, param_type=float
        )
        self.dy_meters = mpi_config.broadcast_parameter(
            self.dy_meters, self.config_options, param_type=float
        )

        # mpi_config.comm.barrier()

        try:
            self.esmf_grid = ESMF.Grid(
                np.array([self.ny_global, self.nx_global]),
                staggerloc=ESMF.StaggerLoc.CENTER,
                coord_sys=ESMF.CoordSys.SPH_DEG,
            )
        except Exception as e:
            self.config_options.errMsg = f"Unable to create ESMF grid for WRF-Hydro geogrid: {self.config_options.geogrid}"
            raise e

        # mpi_config.comm.barrier()

        self.esmf_lat = self.esmf_grid.get_coords(1)
        self.esmf_lon = self.esmf_grid.get_coords(0)

        # mpi_config.comm.barrier()

        # Scatter global XLAT_M grid to processors..
        if mpi_config.rank == 0:
            if esmf_nc.variables[self.config_options.lat_var].ndim == 3:
                var_tmp = esmf_nc.variables[self.config_options.lat_var][0, :, :]
            elif esmf_nc.variables[self.config_options.lat_var].ndim == 2:
                var_tmp = esmf_nc.variables[self.config_options.lat_var][:, :]
            elif esmf_nc.variables[self.config_options.lat_var].ndim == 1:
                lat = esmf_nc.variables[self.config_options.lat_var][:]
                lon = esmf_nc.variables[self.config_options.lon_var][:]
                var_tmp = np.meshgrid(lon, lat)[1]
                lat = None
                lon = None
            # Flag to grab entire array for AWS slicing
            if self.config_options.aws:
                self.lat_bounds = var_tmp
        else:
            var_tmp = None

        # mpi_config.comm.barrier()

        var_sub_tmp = mpi_config.scatter_array(self, var_tmp, self.config_options)

        # mpi_config.comm.barrier()

        # Place the local lat/lon grid slices from the parent geogrid file into
        # the ESMF lat/lon grids.
        try:
            self.esmf_lat[:, :] = var_sub_tmp
            self.latitude_grid = var_sub_tmp
            var_sub_tmp = None
            var_tmp = None
        except Exception as e:
            self.config_options.errMsg = (
                "Unable to subset latitude from geogrid file into ESMF object"
            )
            raise e

        # mpi_config.comm.barrier()

        # Scatter global XLONG_M grid to processors..
        if mpi_config.rank == 0:
            if esmf_nc.variables[self.config_options.lat_var].ndim == 3:
                var_tmp = esmf_nc.variables[self.config_options.lon_var][0, :, :]
            elif esmf_nc.variables[self.config_options.lon_var].ndim == 2:
                var_tmp = esmf_nc.variables[self.config_options.lon_var][:, :]
            elif esmf_nc.variables[self.config_options.lon_var].ndim == 1:
                lat = esmf_nc.variables[self.config_options.lat_var][:]
                lon = esmf_nc.variables[self.config_options.lon_var][:]
                var_tmp = np.meshgrid(lon, lat)[0]
                lat = None
                lon = None
            # Flag to grab entire array for AWS slicing
            if self.config_options.aws:
                self.lon_bounds = var_tmp
        else:
            var_tmp = None

        # mpi_config.comm.barrier()

        var_sub_tmp = mpi_config.scatter_array(self, var_tmp, self.config_options)

        # mpi_config.comm.barrier()

        try:
            self.esmf_lon[:, :] = var_sub_tmp
            self.longitude_grid = var_sub_tmp
            var_sub_tmp = None
            var_tmp = None
        except Exception as e:
            self.config_options.errMsg = (
                "Unable to subset longitude from geogrid file into ESMF object"
            )
            raise e

        # mpi_config.comm.barrier()

        if (
            self.config_options.cosalpha_var is not None
            and self.config_options.sinalpha_var is not None
        ):
            # Scatter the COSALPHA,SINALPHA grids to the processors.
            if mpi_config.rank == 0:
                if esmf_nc.variables[self.config_options.cosalpha_var].ndim == 3:
                    var_tmp = esmf_nc.variables[self.config_options.cosalpha_var][
                        0, :, :
                    ]
                else:
                    var_tmp = esmf_nc.variables[self.config_options.cosalpha_var][:, :]

            else:
                var_tmp = None
            # mpi_config.comm.barrier()

            var_sub_tmp = mpi_config.scatter_array(self, var_tmp, self.config_options)
            # mpi_config.comm.barrier()

            self.cosa_grid = var_sub_tmp[:, :]
            var_sub_tmp = None
            var_tmp = None

            if mpi_config.rank == 0:
                if esmf_nc.variables[self.config_options.sinalpha_var].ndim == 3:
                    var_tmp = esmf_nc.variables[self.config_options.sinalpha_var][
                        0, :, :
                    ]
                else:
                    var_tmp = esmf_nc.variables[self.config_options.sinalpha_var][:, :]
            else:
                var_tmp = None
            # mpi_config.comm.barrier()

            var_sub_tmp = mpi_config.scatter_array(self, var_tmp, self.config_options)
            # mpi_config.comm.barrier()
            self.sina_grid = var_sub_tmp[:, :]
            var_sub_tmp = None
            var_tmp = None

        if self.config_options.hgt_var is not None:
            # Read in a scatter the WRF-Hydro elevation, which is used for downscaling
            # purposes.
            if mpi_config.rank == 0:
                if esmf_nc.variables[self.config_options.hgt_var].ndim == 3:
                    var_tmp = esmf_nc.variables[self.config_options.hgt_var][0, :, :]
                else:
                    var_tmp = esmf_nc.variables[self.config_options.hgt_var][:, :]
            else:
                var_tmp = None
            # mpi_config.comm.barrier()

            var_sub_tmp = mpi_config.scatter_array(self, var_tmp, self.config_options)
            # mpi_config.comm.barrier()
            self.height = var_sub_tmp
            var_sub_tmp = None
            var_tmp = None

        if (
            self.config_options.cosalpha_var is not None
            and self.config_options.sinalpha_var is not None
        ):
            # Calculate the slope from the domain using elevation on the WRF-Hydro domain. This will
            # be used for downscaling purposes.
            if mpi_config.rank == 0:
                try:
                    slope_tmp, slp_azi_tmp = self.calc_slope(esmf_nc)
                except Exception:
                    raise Exception
            else:
                slope_tmp = None
                slp_azi_tmp = None
            # mpi_config.comm.barrier()

            slope_sub_tmp = mpi_config.scatter_array(
                self, slope_tmp, self.config_options
            )
            self.slope = slope_sub_tmp[:, :]
            slope_sub_tmp = None

            slp_azi_sub = mpi_config.scatter_array(
                self, slp_azi_tmp, self.config_options
            )
            self.slp_azi = slp_azi_sub[:, :]
            slp_azi_tmp = None

        elif (
            self.config_options.slope_var is not None
            and self.config_options.slope_azimuth_var is not None
        ):
            if mpi_config.rank == 0:
                if esmf_nc.variables[self.config_options.slope_var].ndim == 3:
                    var_tmp = esmf_nc.variables[self.config_options.slope_var][0, :, :]
                else:
                    var_tmp = esmf_nc.variables[self.config_options.slope_var][:, :]
            else:
                var_tmp = None

            slope_sub_tmp = mpi_config.scatter_array(self, var_tmp, self.config_options)
            self.slope = slope_sub_tmp
            var_tmp = None

            if mpi_config.rank == 0:
                if esmf_nc.variables[self.config_options.slope_azimuth_var].ndim == 3:
                    var_tmp = esmf_nc.variables[self.config_options.slope_azimuth_var][
                        0, :, :
                    ]
                else:
                    var_tmp = esmf_nc.variables[self.config_options.slope_azimuth_var][
                        :, :
                    ]
            else:
                var_tmp = None

            slp_azi_sub = mpi_config.scatter_array(self, var_tmp, self.config_options)
            self.slp_azi = slp_azi_sub[:, :]
            var_tmp = None

        elif self.config_options.hgt_var is not None:
            # Calculate the slope from the domain using elevation of the gridded model and other approximations
            if mpi_config.rank == 0:
                try:
                    slope_tmp, slp_azi_tmp = self.calc_slope_gridded(esmf_nc)
                except Exception:
                    raise Exception
            else:
                slope_tmp = None
                slp_azi_tmp = None
            # mpi_config.comm.barrier()

            slope_sub_tmp = mpi_config.scatter_array(
                self, slope_tmp, self.config_options
            )
            self.slope = slope_sub_tmp[:, :]
            slope_sub_tmp = None

            slp_azi_sub = mpi_config.scatter_array(
                self, slp_azi_tmp, self.config_options
            )
            self.slp_azi = slp_azi_sub[:, :]
            slp_azi_tmp = None

        if mpi_config.rank == 0:
            # Close the geogrid file
            try:
                esmf_nc.close()
            except Exception as e:
                self.config_options.errMsg = (
                    f"Unable to close geogrid file: {self.config_options.geogrid}"
                )
                raise e

        # Reset temporary variables to free up memory
        slope_tmp = None
        slp_azi_tmp = None
        var_tmp = None

    def calc_slope_gridded(self, esmf_nc: netCDF4.Dataset) -> tuple:
        """Calculate slope grids needed for incoming shortwave radiation downscaling.

        Function to calculate slope grids needed for incoming shortwave radiation downscaling
        later during the program. This calculates the slopes for grid cells
        :param esmf_nc: The open netCDF4 dataset for the geogrid file, passed in to avoid having to reopen the file multiple times
        :return: A tuple containing slope and slope azimuth for grid cells
        """
        esmf_nc = netCDF4.Dataset(self.config_options.geogrid, "r")

        try:
            lons = esmf_nc.variables[self.config_options.lon_var][:]
            lats = esmf_nc.variables[self.config_options.lat_var][:]
        except Exception as e:
            self.config_options.errMsg = f"Unable to extract gridded coordinates in {self.config_options.geogrid}"
            raise e
        try:
            dx = np.empty(
                (
                    esmf_nc.variables[self.config_options.lat_var].shape[0],
                    esmf_nc.variables[self.config_options.lon_var].shape[0],
                ),
                dtype=float,
            )
            dy = np.empty(
                (
                    esmf_nc.variables[self.config_options.lat_var].shape[0],
                    esmf_nc.variables[self.config_options.lon_var].shape[0],
                ),
                dtype=float,
            )
            dx[:] = esmf_nc.variables[self.config_options.lon_var].dx
            dy[:] = esmf_nc.variables[self.config_options.lat_var].dy
        except Exception as e:
            self.config_options.errMsg = f"Unable to extract dx and dy distances in {self.config_options.geogrid}"
            raise e
        try:
            heights = esmf_nc.variables[self.config_options.hgt_var][:]
        except Exception as e:
            self.config_options.errMsg = f"Unable to extract heights of grid cells in {self.config_options.geogrid}"
            raise e

        esmf_nc.close()

        # calculate grid coordinates dx distances in meters
        # based on general geospatial formula approximations
        # on a spherical grid
        dz_init = np.diff(heights, axis=0)
        dz = np.empty(dx.shape, dtype=float)
        dz[0 : dz_init.shape[0], 0 : dz_init.shape[1]] = dz_init
        dz[dz_init.shape[0] :, :] = dz_init[-1, :]

        slope = dz / np.sqrt((dx**2) + (dy**2))
        slp_azi = (180 / np.pi) * np.arctan(dx / dy)

        # Reset temporary arrays to None to free up memory
        lons = None
        lats = None
        heights = None
        dx = None
        dy = None
        dz = None

        return slope, slp_azi

    @property
    def x_lower_bound(self) -> float:
        """Get the local x lower bound for this processor."""
        return self.esmf_grid.lower_bounds[ESMF.StaggerLoc.CENTER][1]

    @property
    def x_upper_bound(self) -> float:
        """Get the local x upper bound for this processor."""
        return self.esmf_grid.upper_bounds[ESMF.StaggerLoc.CENTER][1]

    @property
    def y_lower_bound(self) -> float:
        """Get the local y lower bound for this processor."""
        return self.esmf_grid.lower_bounds[ESMF.StaggerLoc.CENTER][0]

    @property
    def y_upper_bound(self) -> float:
        """Get the local y upper bound for this processor."""
        return self.esmf_grid.upper_bounds[ESMF.StaggerLoc.CENTER][0]

    @property
    def nx_local(self) -> int:
        """Get the local x dimension size for this processor."""
        return self.x_upper_bound - self.x_lower_bound

    @property
    def ny_local(self) -> int:
        """Get the local y dimension size for this processor."""
        return self.y_upper_bound - self.y_lower_bound


class HydrofabricGeoMeta(GeoMeta):
    """Class for handling information about the unstructured hydrofabric domain we are processing forcings to."""

    def __init__(self, config_options: ConfigOptions, mpi_config: MpiConfig):
        """Initialize GeoMetaWrfHydro class variables.

        Initialization function to initialize ESMF through ESMPy,
        calculate the global parameters of the WRF-Hydro grid
        being processed to, along with the local parameters
        for this particular processor.
        :return:
        """
        super().__init__(config_options, mpi_config)
        self.nx_local_elem = None
        self.ny_local_elem = None
        self.x_lower_bound = None
        self.x_upper_bound = None
        self.y_lower_bound = None
        self.y_upper_bound = None
        if self.config_options.geogrid is not None:
            # Phase 1: Rank 0 extracts all needed global data
            if self.mpi_config.rank == 0:
                try:
                    esmf_nc = nc_utils.nc_Dataset_retry(
                        self.mpi_config,
                        self.config_options,
                        err_handler,
                        self.config_options.geogrid,
                        "r",
                    )

                    # Extract everything we need with retries
                    tmp_vars = esmf_nc.variables

                    if self.config_options.aws:
                        nodecoords_data = nc_utils.nc_read_var_retry(
                            self.mpi_config,
                            self.config_options,
                            err_handler,
                            tmp_vars[self.config_options.nodecoords_var],
                        )
                        self.lat_bounds = nodecoords_data[:, 1]
                        self.lon_bounds = nodecoords_data[:, 0]

                    # Store these for later broadcast/scatter
                    elementcoords_global = nc_utils.nc_read_var_retry(
                        self.mpi_config,
                        self.config_options,
                        err_handler,
                        tmp_vars[self.config_options.elemcoords_var],
                    )

                    self.nx_global = elementcoords_global.shape[0]
                    self.ny_global = self.nx_global

                    element_ids_global = nc_utils.nc_read_var_retry(
                        self.mpi_config,
                        self.config_options,
                        err_handler,
                        tmp_vars[self.config_options.element_id_var],
                    )

                    heights_global = None
                    if self.config_options.hgt_var is not None:
                        heights_global = nc_utils.nc_read_var_retry(
                            self.mpi_config,
                            self.config_options,
                            err_handler,
                            tmp_vars[self.config_options.hgt_var],
                        )
                    slopes_global = None
                    slp_azi_global = None
                    if self.config_options.slope_var is not None:
                        slopes_global = nc_utils.nc_read_var_retry(
                            self.mpi_config,
                            self.config_options,
                            err_handler,
                            tmp_vars[self.config_options.slope_var],
                        )
                    if self.config_options.slope_azimuth_var is not None:
                        slp_azi_global = nc_utils.nc_read_var_retry(
                            self.mpi_config,
                            self.config_options,
                            err_handler,
                            tmp_vars[self.config_options.slope_azimuth_var],
                        )

                except Exception as e:
                    LOG.critical(
                        f"Failed to open mesh file: {self.config_options.geogrid} "
                        f"due to {str(e)}"
                    )
                    raise
                finally:
                    esmf_nc.close()
            else:
                elementcoords_global = None
                element_ids_global = None
                heights_global = None
                slopes_global = None
                slp_azi_global = None

            # Broadcast dimensions
            self.nx_global = self.mpi_config.broadcast_parameter(
                self.nx_global, self.config_options, param_type=int
            )
            self.ny_global = self.mpi_config.broadcast_parameter(
                self.ny_global, self.config_options, param_type=int
            )

            self.mpi_config.comm.barrier()

            # Phase 2: Create ESMF Mesh (collective operation with retry)
            try:
                self.esmf_grid = esmf_utils.esmf_mesh_retry(
                    self.mpi_config,
                    self.config_options,
                    err_handler,
                    filename=self.config_options.geogrid,
                    filetype=ESMF.FileFormat.ESMFMESH,
                )
            except Exception as e:
                LOG.critical(
                    f"Unable to create ESMF Mesh: {self.config_options.geogrid} "
                    f"due to {str(e)}"
                )
                raise e

            # Extract local coordinates from ESMF mesh
            self.latitude_grid = self.esmf_grid.coords[1][1]
            self.longitude_grid = self.esmf_grid.coords[1][0]

            # Phase 3: Broadcast global arrays and compute local indices
            elementcoords_global = self.mpi_config.comm.bcast(
                elementcoords_global, root=0
            )
            element_ids_global = self.mpi_config.comm.bcast(element_ids_global, root=0)

            # Each rank computes its own local indices
            pet_elementcoords = np.column_stack(
                [self.longitude_grid, self.latitude_grid]
            )
            tree = spatial.KDTree(elementcoords_global)
            _, pet_element_inds = tree.query(pet_elementcoords)

            self.element_ids = element_ids_global[pet_element_inds]
            self.element_ids_global = element_ids_global

            # Broadcast and extract height/slope data
            if self.config_options.hgt_var is not None:
                heights_global = self.mpi_config.comm.bcast(heights_global, root=0)
                self.height = heights_global[pet_element_inds]

            if self.config_options.slope_var is not None:
                slopes_global = self.mpi_config.comm.bcast(slopes_global, root=0)
                slp_azi_global = self.mpi_config.comm.bcast(slp_azi_global, root=0)
                self.slope = slopes_global[pet_element_inds]
                self.slp_azi = slp_azi_global[pet_element_inds]

            self.mesh_inds = pet_element_inds

    @property
    def nx_local(self) -> int:
        """Get the local x dimension size for this processor."""
        return len(self.esmf_grid.coords[1][1])

    @property
    def ny_local(self) -> int:
        """Get the local y dimension size for this processor."""
        return len(self.esmf_grid.coords[1][1])


class UnstructuredGeoMeta(GeoMeta):
    """Class for handling information about the unstructured domain we are processing forcings to."""

    def __init__(self, config_options: ConfigOptions, mpi_config: MpiConfig):
        """Initialize GeoMetaWrfHydro class variables.

        Initialization function to initialize ESMF through ESMPy,
        calculate the global parameters of the WRF-Hydro grid
        being processed to, along with the local parameters
        for this particular processor.
        :return:
        """
        super().__init__(config_options, mpi_config)

        self.x_lower_bound = None
        self.x_upper_bound = None
        self.y_lower_bound = None
        self.y_upper_bound = None
        # Open the geogrid file and extract necessary information
        # to create ESMF fields.
        if mpi_config.rank == 0:
            try:
                esmf_nc = netCDF4.Dataset(self.config_options.geogrid, "r")
            except Exception as e:
                self.config_options.errMsg = f"Unable to open the unstructured mesh file: {self.config_options.geogrid}"
                raise e

            try:
                self.nx_global = esmf_nc.variables[
                    self.config_options.nodecoords_var
                ].shape[0]
            except Exception as e:
                self.config_options.errMsg = f"Unable to extract X dimension size in {self.config_options.geogrid}"
                raise e

            try:
                self.ny_global = esmf_nc.variables[
                    self.config_options.nodecoords_var
                ].shape[0]
            except Exception as e:
                self.config_options.errMsg = f"Unable to extract Y dimension size in {self.config_options.geogrid}"
                raise e

            try:
                self.nx_global_elem = esmf_nc.variables[
                    self.config_options.elemcoords_var
                ].shape[0]
            except Exception as e:
                self.config_options.errMsg = f"Unable to extract X dimension size in {self.config_options.geogrid}"
                raise e

            try:
                self.ny_global_elem = esmf_nc.variables[
                    self.config_options.elemcoords_var
                ].shape[0]
            except Exception as e:
                self.config_options.errMsg = f"Unable to extract Y dimension size in {self.config_options.geogrid}"
                raise e

            # Flag to grab entire array for AWS slicing
            if self.config_options.aws:
                self.lat_bounds = esmf_nc.variables[self.config_options.nodecoords_var][
                    :
                ][:, 1]
                self.lon_bounds = esmf_nc.variables[self.config_options.nodecoords_var][
                    :
                ][:, 0]

        # mpi_config.comm.barrier()

        # Broadcast global dimensions to the other processors.
        self.nx_global = mpi_config.broadcast_parameter(
            self.nx_global, self.config_options, param_type=int
        )
        self.ny_global = mpi_config.broadcast_parameter(
            self.ny_global, self.config_options, param_type=int
        )
        self.nx_global_elem = mpi_config.broadcast_parameter(
            self.nx_global_elem, self.config_options, param_type=int
        )
        self.ny_global_elem = mpi_config.broadcast_parameter(
            self.ny_global_elem, self.config_options, param_type=int
        )

        # mpi_config.comm.barrier()

        if mpi_config.rank == 0:
            # Close the geogrid file
            try:
                esmf_nc.close()
            except Exception as e:
                self.config_options.errMsg = (
                    f"Unable to close geogrid Mesh file: {self.config_options.geogrid}"
                )
                raise e

        try:
            # Removed argument coord_sys=ESMF.CoordSys.SPH_DEG since we are always reading from a file
            # From ESMF documentation
            # If you create a mesh from a file (like NetCDF/ESMF-Mesh), coord_sys is ignored. The mesh’s coordinate system should be embedded in the file or inferred.
            self.esmf_grid = ESMF.Mesh(
                filename=self.config_options.geogrid, filetype=ESMF.FileFormat.ESMFMESH
            )
        except Exception as e:
            self.config_options.errMsg = f"Unable to create ESMF Mesh from geogrid file: {self.config_options.geogrid}"
            raise e

        # mpi_config.comm.barrier()

        # Place the local lat/lon grid slices from the parent geogrid file into
        # the ESMF lat/lon grids that have already been seperated by processors.
        try:
            self.latitude_grid = self.esmf_grid.coords[0][1]
            self.latitude_grid_elem = self.esmf_grid.coords[1][1]
            var_sub_tmp = None
            var_tmp = None
        except Exception as e:
            self.config_options.errMsg = (
                "Unable to subset node latitudes from ESMF Mesh object"
            )
            raise e
        try:
            self.longitude_grid = self.esmf_grid.coords[0][0]
            self.longitude_grid_elem = self.esmf_grid.coords[1][0]
            var_sub_tmp = None
            var_tmp = None
        except Exception as e:
            self.config_options.errMsg = (
                "Unable to subset XLONG_M from geogrid file into ESMF Mesh object"
            )
            raise e

        esmf_nc = netCDF4.Dataset(self.config_options.geogrid, "r")

        # Get lat and lon global variables for pet extraction of indices
        nodecoords_global = esmf_nc.variables[self.config_options.nodecoords_var][
            :
        ].data
        elementcoords_global = esmf_nc.variables[self.config_options.elemcoords_var][
            :
        ].data

        # Find the corresponding local indices to slice global heights and slope
        # variables that are based on the partitioning on the unstructured mesh
        pet_nodecoords = np.empty((len(self.latitude_grid), 2), dtype=float)
        pet_elementcoords = np.empty((len(self.latitude_grid_elem), 2), dtype=float)
        pet_nodecoords[:, 0] = self.longitude_grid
        pet_nodecoords[:, 1] = self.latitude_grid
        pet_elementcoords[:, 0] = self.longitude_grid_elem
        pet_elementcoords[:, 1] = self.latitude_grid_elem

        distance, pet_node_inds = spatial.KDTree(nodecoords_global).query(
            pet_nodecoords
        )
        distance, pet_element_inds = spatial.KDTree(elementcoords_global).query(
            pet_elementcoords
        )

        # reset variables to free up memory
        nodecoords_global = None
        elementcoords_global = None
        pet_nodecoords = None
        pet_elementcoords = None
        distance = None

        # Not accepting cosalpha and sinalpha at this time for unstructured meshes, only
        # accepting the pre-calculated slope and slope azmiuth variables if available,
        # otherwise calculate slope from height estimates
        # if(config_options.cosalpha_var != None and config_options.sinalpha_var != None):
        # self.cosa_grid = esmf_nc.variables[config_options.cosalpha_var][:].data[pet_node_inds]
        # self.sina_grid = esmf_nc.variables[config_options.sinalpha_var][:].data[pet_node_inds]
        # slope_tmp, slp_azi_tmp = self.calc_slope(esmf_nc,config_options)
        # self.slope = slope_node_tmp[pet_node_inds]
        # self.slp_azi = slp_azi_node_tmp[pet_node_inds]
        if (
            self.config_options.slope_var is not None
            and self.config_options.slp_azi_var is not None
        ):
            self.slope = esmf_nc.variables[self.config_options.slope_var][:].data[
                pet_node_inds
            ]
            self.slp_azi = esmf_nc.variables[self.config_options.slope_azimuth_var][
                :
            ].data[pet_node_inds]
            self.slope_elem = esmf_nc.variables[self.config_options.slope_var_elem][
                :
            ].data[pet_element_inds]
            self.slp_azi_elem = esmf_nc.variables[
                self.config_options.slope_azimuth_var_elem
            ][:].data[pet_element_inds]

            # Read in a scatter the mesh node elevation, which is used for downscaling purposes
            self.height = esmf_nc.variables[self.config_options.hgt_var][:].data[
                pet_node_inds
            ]
            # Read in a scatter the mesh element elevation, which is used for downscaling purposes.
            self.height_elem = esmf_nc.variables[self.config_options.hgt_elem_var][
                :
            ].data[pet_element_inds]

        elif self.config_options.hgt_var is not None:
            # Read in a scatter the mesh node elevation, which is used for downscaling purposes
            self.height = esmf_nc.variables[self.config_options.hgt_var][:].data[
                pet_node_inds
            ]

            # Read in a scatter the mesh element elevation, which is used for downscaling purposes.
            self.height_elem = esmf_nc.variables[self.config_options.hgt_elem_var][
                :
            ].data[pet_element_inds]

            # Calculate the slope from the domain using elevation on the WRF-Hydro domain. This will
            # be used for downscaling purposes.
            slope_node_tmp, slp_azi_node_tmp, slope_elem_tmp, slp_azi_elem_tmp = (
                self.calc_slope_unstructured(esmf_nc)
            )

            self.slope = slope_node_tmp[pet_node_inds]
            slope_node_tmp = None

            self.slp_azi = slp_azi_node_tmp[pet_node_inds]
            slp_azi_node_tmp = None

            self.slope_elem = slope_elem_tmp[pet_element_inds]
            slope_elem_tmp = None

            self.slp_azi_elem = slp_azi_elem_tmp[pet_element_inds]
            slp_azi_elem_tmp = None

        # save indices where mesh was partition for future scatter functions
        self.mesh_inds = pet_node_inds
        self.mesh_inds_elem = pet_element_inds

        # reset variables to free up memory
        pet_node_inds = None
        pet_element_inds = None

    @property
    def nx_local(self) -> int:
        """Get the local x dimension size for this processor."""
        return len(self.esmf_grid.coords[0][1])

    @property
    def ny_local(self) -> int:
        """Get the local y dimension size for this processor."""
        return len(self.esmf_grid.coords[0][1])

    @property
    def nx_local_elem(self) -> int:
        """Get the local x dimension size for this processor."""
        return len(self.esmf_grid.coords[1][1])

    @property
    def ny_local_elem(self) -> int:
        """Get the local y dimension size for this processor."""
        return len(self.esmf_grid.coords[1][1])

    def calc_slope_unstructured(self, esmf_nc: netCDF4.Dataset) -> tuple:
        """Calculate slope grids needed for incoming shortwave radiation downscaling.

        Function to calculate slope grids needed for incoming shortwave radiation downscaling
        later during the program. This calculates the slopes for both nodes and elements
        :param esmf_nc: The open netCDF4 dataset for the geogrid file, passed in to avoid having to reopen the file multiple times
        :return: A tuple containing slope and slope azimuth for nodes and elements
        """
        esmf_nc = netCDF4.Dataset(self.config_options.geogrid, "r")

        try:
            node_lons = esmf_nc.variables[self.config_options.nodecoords_var][:][:, 0]
            node_lats = esmf_nc.variables[self.config_options.nodecoords_var][:][:, 1]
        except Exception as e:
            self.config_options.errMsg = (
                f"Unable to extract node coordinates in {self.config_options.geogrid}"
            )
            raise e
        try:
            elem_lons = esmf_nc.variables[self.config_options.elemcoords_var][:][:, 0]
            elem_lats = esmf_nc.variables[self.config_options.elemcoords_var][:][:, 1]
        except Exception as e:
            self.config_options.errMsg = f"Unable to extract element coordinates in {self.config_options.geogrid}"
            raise e
        try:
            elem_conn = esmf_nc.variables[self.config_options.elemconn_var][:][:, 0]
        except Exception as e:
            self.config_options.errMsg = f"Unable to extract element connectivity in {self.config_options.geogrid}"
            raise e
        try:
            node_heights = esmf_nc.variables[self.config_options.hgt_var][:]
        except Exception as e:
            self.config_options.errMsg = (
                f"Unable to extract HGT_M from: {self.config_options.geogrid}"
            )
            raise e

        if node_heights.shape[0] != self.ny_global:
            self.config_options.errMsg = (
                f"HGT_M dimension mismatch in: {self.config_options.geogrid}"
            )
            raise Exception

        try:
            elem_heights = esmf_nc.variables[self.config_options.hgt_elem_var][:]
        except Exception as e:
            self.config_options.errMsg = (
                f"Unable to extract HGT_M_ELEM from: {self.config_options.geogrid}"
            )
            raise e

        if elem_heights.shape[0] != len(elem_lons):
            self.config_options.errMsg = (
                f"HGT_M_ELEM dimension mismatch in: {self.config_options.geogrid}"
            )
            raise Exception

        esmf_nc.close()

        # calculate node coordinate distances in meters
        # based on general geospatial formula approximations
        # on a spherical grid
        dx = np.diff(node_lons) * 40075160 * np.cos(node_lats[0:-1] * np.pi / 180) / 360
        dx = np.append(dx, dx[-1])
        dy = np.diff(node_lats) * 40008000 / 360
        dy = np.append(dy, dy[-1])
        dz = np.diff(node_heights)
        dz = np.append(dz, dz[-1])

        slope_nodes = dz / np.sqrt((dx**2) + (dy**2))
        slp_azi_nodes = (180 / np.pi) * np.arctan(dx / dy)

        # calculate element coordinate distances in meters
        # based on general geospatial formula approximations
        # on a spherical grid
        dx = np.diff(elem_lons) * 40075160 * np.cos(elem_lats[0:-1] * np.pi / 180) / 360
        dx = np.append(dx, dx[-1])
        dy = np.diff(elem_lats) * 40008000 / 360
        dy = np.append(dy, dy[-1])
        dz = np.diff(elem_heights)
        dz = np.append(dz, dz[-1])

        slope_elem = dz / np.sqrt((dx**2) + (dy**2))
        slp_azi_elem = (180 / np.pi) * np.arctan(dx / dy)

        # Reset temporary arrays to None to free up memory
        node_lons = None
        node_lats = None
        elem_lons = None
        elem_lats = None
        node_heights = None
        elem_heights = None
        dx = None
        dy = None
        dz = None

        return slope_nodes, slp_azi_nodes, slope_elem, slp_azi_elem
