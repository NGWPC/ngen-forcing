from . import retry_utils
import types
from .core.parallel import MpiConfig
from .core.config import ConfigOptions

import netCDF4


@retry_utils.retry_w_mpi_context(
    abort=True, num_retries=3, sleep_start=1, sleep_factor=3
)
def nc_Dataset_retry(
    mpi_config: MpiConfig,
    config_options: ConfigOptions,
    err_handler: types.ModuleType,
    *args,
    **kwargs,
):
    """netCDF4 Dataset open with MPI retry logic."""
    return netCDF4.Dataset(*args, **kwargs)
