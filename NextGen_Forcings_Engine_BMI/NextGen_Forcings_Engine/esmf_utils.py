import functools
import time
import types

from .core.parallel import MpiConfig
from .core.config import ConfigOptions

### TODO fix circular import raised during `from .bmi_model import ESMF`.
### shapely must be imported before ESMF to avoid segfault with shapely 2+
import shapely
import esmpy as ESMF


def retry_w_mpi_context(abort: bool, num_retries: int, sleep_start: float, sleep_factor: float):
    """
    Decorator intended to retry functions in MPI context, that involve collective / barrier calls.
    For example, ESMF functions like ESMF.Regrid(), which, with default calls to err_handler.check_program_status,
    may result in deadlocks if one rank fails out and the others don't, without calling MPI Abort() or re-raising the exception.

    Causes any/all ranks to call their own MPI Abort(), rather than only rank 0 calling MPI Abort().

    May only wrap functions that include the following parameters as their first three arguments:
            mpi_config: MpiConfig,
            config_options: ConfigOptions,
            err_handler: types.ModuleType,

    :param abort: If True, on fail-out, MPI Abort() (system exit all ranks) without reraising the exeption. If False, on fail-out, reraise the exception of the final attempt.
    :param num_retries: The number of retries to perform. Must be >= 0.
    :param sleep_start: The sleep duration in seconds, between the first and second attempts.
    :param sleep_factor: With each attempt prior to fail-out, the sleep duration is multiplied by this amount.
    :return: On success, the decorated function returns its normally returned value. On fail-out, either an exception is raised, or MPI Abort() is called (system exit).
    """

    def decorator(func):

        @functools.wraps(func)
        def wrapper(
            mpi_config: MpiConfig,
            config_options: ConfigOptions,
            err_handler: types.ModuleType,
            *args,
            **kwargs,
        ):
            if not isinstance(mpi_config, MpiConfig):
                raise TypeError(f"Expected type {MpiConfig} for mpi_config, got: {type(mpi_config)}")
            if not isinstance(config_options, ConfigOptions):
                raise TypeError(f"Expected type {ConfigOptions} for config_options, got: {type(config_options)}")
            if not isinstance(err_handler, types.ModuleType):
                raise TypeError(f"Expected type {types.ModuleType} for err_handler, got: {type(err_handler)}")
            if num_retries < 0:
                raise ValueError(f"Expected num_retries >= 0, got: {num_retries}")

            sleep_sec = sleep_start
            attempt = 0
            while True:
                attempt += 1
                msg = f"Starting attempt {attempt} of {num_retries + 1} for func: {func.__name__}."
                err_handler.log_msg(config_options, mpi_config, debug=True, msg=msg)
                try:
                    # if attempt < 2: raise RuntimeError("Testing one retry")
                    # if True: raise RuntimeError("Testing retry-failout")
                    # if mpi_config.rank == 0:  raise RuntimeError(f"Testing retry-failout on rank 0")
                    # if mpi_config.rank == 1:  raise RuntimeError(f"Testing retry-failout on rank 1")
                    ret = func(mpi_config, config_options, err_handler, *args, **kwargs)
                except Exception as e:
                    # Fail
                    msg = f"Attempt {attempt} of {num_retries + 1} for func: {func.__name__} failed with error: {repr(e)}."
                    if attempt < num_retries + 1:
                        # Retry
                        msg += f" Retrying in {sleep_sec} seconds."
                        err_handler.log_warning(config_options, mpi_config, msg=msg)
                        time.sleep(sleep_sec)
                        sleep_sec *= sleep_factor
                    else:
                        # Fail out
                        msg += f" Attempts exceeded limit."
                        if abort:
                            msg += " Will MPI Abort()."
                            err_handler.log_critical(config_options, mpi_config, msg=msg)
                            # This decorator is intended to be used for functions that make calls to collective / barrier functions,
                            # So the unusual arguments to check_program_status are used to prevent potential deadlocks.
                            err_handler.check_program_status(
                                config_options, mpi_config, rank_0_reduce=False, any_rank_abort=True
                            )
                        else:
                            msg += " Reraising exception."
                            err_handler.log_critical(config_options, mpi_config, msg=msg)
                            e.args = (msg,) + e.args
                            raise e
                        raise RuntimeError("Should not get here.")
                else:
                    msg = f"func {func.__name__} finished after {attempt} attempts."
                    err_handler.log_msg(config_options, mpi_config, debug=True, msg=msg)
                    err_handler.check_program_status(
                        config_options, mpi_config, rank_0_reduce=False, any_rank_abort=True
                    )
                    return ret

        return wrapper

    return decorator


@retry_w_mpi_context(abort=True, num_retries=3, sleep_start=1, sleep_factor=3)
def esmf_field_retry(
    mpi_config: MpiConfig, config_options: ConfigOptions, err_handler: types.ModuleType, *esmf_args, **esmf_kwargs
):
    """ESMF.Field() call, wrapped by MPI-aware retry decorator."""
    return ESMF.Field(*esmf_args, **esmf_kwargs)


@retry_w_mpi_context(abort=True, num_retries=3, sleep_start=1, sleep_factor=3)
def esmf_grid_retry(
    mpi_config: MpiConfig, config_options: ConfigOptions, err_handler: types.ModuleType, *esmf_args, **esmf_kwargs
):
    """ESMF.Grid() call, wrapped by MPI-aware retry decorator."""
    return ESMF.Grid(*esmf_args, **esmf_kwargs)


@retry_w_mpi_context(abort=True, num_retries=3, sleep_start=1, sleep_factor=3)
def esmf_mesh_retry(
    mpi_config: MpiConfig, config_options: ConfigOptions, err_handler: types.ModuleType, *esmf_args, **esmf_kwargs
):
    """ESMF.Mesh() call, wrapped by MPI-aware retry decorator."""
    return ESMF.Mesh(*esmf_args, **esmf_kwargs)


@retry_w_mpi_context(abort=True, num_retries=3, sleep_start=1, sleep_factor=3)
def esmf_regrid_retry(
    mpi_config: MpiConfig, config_options: ConfigOptions, err_handler: types.ModuleType, *esmf_args, **esmf_kwargs
):
    """ESMF.Regrid() call, wrapped by MPI-aware retry decorator."""
    return ESMF.Regrid(*esmf_args, **esmf_kwargs)


@retry_w_mpi_context(abort=True, num_retries=3, sleep_start=1, sleep_factor=3)
def esmf_regridfromfile_retry(
    mpi_config: MpiConfig, config_options: ConfigOptions, err_handler: types.ModuleType, *esmf_args, **esmf_kwargs
):
    """ESMF.RegridFromFile() call, wrapped by MPI-aware retry decorator."""
    return ESMF.RegridFromFile(*esmf_args, **esmf_kwargs)
