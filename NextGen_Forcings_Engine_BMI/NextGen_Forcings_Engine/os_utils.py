from . import retry_utils
import types
from .core.parallel import MpiConfig
from .core.config import ConfigOptions
import os


@retry_utils.retry_w_mpi_context(
    abort=True, num_retries=3, sleep_start=1, sleep_factor=3
)
def assert_path_exists_retry(
    mpi_config: MpiConfig,
    config_options: ConfigOptions,
    err_handler: types.ModuleType,
    path: str,
):
    """Raise FileNotFoundError if the path does not exist. Wrapped by MPI-aware retry decorator."""
    if not os.path.exists(path):
        raise FileNotFoundError(path)


@retry_utils.retry_simple(num_retries=3, sleep_start=1, sleep_factor=3)
def os_remove_retry(
    path: str,
    ignore_filenotfound: bool = False,
):
    """os.remove() call, wrapped by simple retry decorator."""
    try:
        os.remove(path)
    except FileNotFoundError as e:
        if not ignore_filenotfound:
            raise e


def os_remove_rank_0(
    mpi_config: MpiConfig,
    config_options: ConfigOptions,
    err_handler: types.ModuleType,
    file_path: str,
    msg_prefix: str = "",
) -> None:
    if mpi_config.rank == 0:
        if os.path.exists(file_path):
            err_handler.log_warning(
                config_options,
                mpi_config,
                msg=f"{msg_prefix}Removing file: {file_path}",
            )
            os_remove_retry(file_path, ignore_filenotfound=True)
    err_handler.check_program_status(config_options, mpi_config)
