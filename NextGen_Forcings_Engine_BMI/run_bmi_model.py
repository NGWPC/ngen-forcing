import argparse
import datetime
import pathlib
from pathlib import Path

import numpy as np
import pandas as pd

# This is the NextGen Forcings Engine BMI instance to execute
from NextGen_Forcings_Engine.bmi_model import NWMv3_Forcing_Engine_BMI_model


def run_bmi(start_time: str, end_time: str, config_path: pathlib.Path = None, b_date: str = None, geogrid: str = None,
            output_path: pathlib.Path = None):
    """
    Wrapper script to execute the forcing engine BMI code. Requires user to pass start_time and end_time as arguments.
    Additional configurations are parsed from config.yml - User can provide a config_path to point to a specific config file.

    example: python run_bmi_model.py '2024-11-19 20:00:00' '2024-11-20 07:00:00'
    """

    print('args', locals())
    start_time = datetime.datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
    end_time = datetime.datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
    ngen_datetimes = pd.date_range(start=start_time, end=end_time, freq='h')

    print('creating an instance of an BMI_MODEL model object')
    model = NWMv3_Forcing_Engine_BMI_model()

    print('Initializing the BMI')
    cfg_path = str(config_path) if config_path is not None else str(Path(__file__).parent.resolve() / 'config.yml')

    model.initialize(
        bmi_cfg_file_name=cfg_path,
        b_date=b_date,
        geogrid=geogrid,
        output_path=str(output_path) if output_path is not None else None
    )

    # Initialize to None to avoid Pycharm error
    U2D = V2D = LWDOWN = SWDOWN = T2D = Q2D = PSFC = RAINRATE = LQFRAC = CAT_IDS = None
    U2D_NODE = V2D_NODE = LWDOWN_NODE = SWDOWN_NODE = T2D_NODE = Q2D_NODE = PSFC_NODE = RAINRATE_NODE = None
    U2D_ELEMENT = V2D_ELEMENT = LWDOWN_ELEMENT = SWDOWN_ELEMENT = T2D_ELEMENT = Q2D_ELEMENT = PSFC_ELEMENT = RAINRATE_ELEMENT = LQFRAC_NODE = LQFRAC_ELEMENT = None

    # ===============================
    # Initialize arrays based on grid type
    # ===============================
    if model._grid_type in {"gridded", "hydrofabric"}:
        # Shared initialization
        U2D = np.zeros(model._varsize, dtype=float)
        V2D = np.zeros(model._varsize, dtype=float)
        LWDOWN = np.zeros(model._varsize, dtype=float)
        SWDOWN = np.zeros(model._varsize, dtype=float)
        T2D = np.zeros(model._varsize, dtype=float)
        Q2D = np.zeros(model._varsize, dtype=float)
        PSFC = np.zeros(model._varsize, dtype=float)
        RAINRATE = np.zeros(model._varsize, dtype=float)
        if model._job_meta.include_lqfrac == 1:
            LQFRAC = np.zeros(model._varsize, dtype=float)
        if model._grid_type == "hydrofabric":
            CAT_IDS = np.zeros(model._varsize, dtype=int)

    elif model._grid_type == "unstructured":
        # Unstructured grid (element + node)
        U2D_NODE = np.zeros(model._varsize, dtype=float)
        V2D_NODE = np.zeros(model._varsize, dtype=float)
        LWDOWN_NODE = np.zeros(model._varsize, dtype=float)
        SWDOWN_NODE = np.zeros(model._varsize, dtype=float)
        T2D_NODE = np.zeros(model._varsize, dtype=float)
        Q2D_NODE = np.zeros(model._varsize, dtype=float)
        PSFC_NODE = np.zeros(model._varsize, dtype=float)
        RAINRATE_NODE = np.zeros(model._varsize, dtype=float)

        U2D_ELEMENT = np.zeros(model._varsize_elem, dtype=float)
        V2D_ELEMENT = np.zeros(model._varsize_elem, dtype=float)
        LWDOWN_ELEMENT = np.zeros(model._varsize_elem, dtype=float)
        SWDOWN_ELEMENT = np.zeros(model._varsize_elem, dtype=float)
        T2D_ELEMENT = np.zeros(model._varsize_elem, dtype=float)
        Q2D_ELEMENT = np.zeros(model._varsize_elem, dtype=float)
        PSFC_ELEMENT = np.zeros(model._varsize_elem, dtype=float)
        RAINRATE_ELEMENT = np.zeros(model._varsize_elem, dtype=float)
        if model._job_meta.include_lqfrac == 1:
            LQFRAC_NODE = np.zeros(model._varsize, dtype=float)
            LQFRAC_ELEMENT = np.zeros(model._varsize_elem, dtype=float)
    else:
        raise ValueError(f"Unsupported grid type: {model._grid_type}")

    # ===============================
    # Run through each timestep
    # ===============================
    model_start_time = start_time  # store for datetime reconstruction
    print(f'Now loop through {len(ngen_datetimes)} ngen_datetimes, updating the model, and extracting forcing data\n')
    print(f'rank: {model._mpi_meta.rank}')
    print(f'grid_type: {model._grid_type}')
    for timestamp in ngen_datetimes:
        print('\n---------------------------------------------------')
        print(f'Iteration for {timestamp}')
        model.update()

        include_lqfrac = model._job_meta.include_lqfrac == 1
        is_unstructured = model._grid_type == "unstructured"
        bmi_seconds = model.get_current_time()
        model_time = model_start_time + datetime.timedelta(seconds=bmi_seconds)

        if model._grid_type in {"gridded", "hydrofabric"}:
            if model._grid_type == "hydrofabric":
                CAT_IDS = model.get_value('CAT-ID', CAT_IDS)

            U2D = model.get_value('U2D_ELEMENT', U2D)
            V2D = model.get_value('V2D_ELEMENT', V2D)
            T2D = model.get_value('T2D_ELEMENT', T2D)
            Q2D = model.get_value('Q2D_ELEMENT', Q2D)
            SWDOWN = model.get_value('SWDOWN_ELEMENT', SWDOWN)
            LWDOWN = model.get_value('LWDOWN_ELEMENT', LWDOWN)
            PSFC = model.get_value('PSFC_ELEMENT', PSFC)
            RAINRATE = model.get_value('RAINRATE_ELEMENT', RAINRATE)
            if include_lqfrac:
                LQFRAC = model.get_value('LQFRAC_ELEMENT', LQFRAC)

            values_max = [arr.max() for arr in [U2D, V2D, LWDOWN, SWDOWN, T2D, Q2D, PSFC, RAINRATE]]
            values_min = [arr.min() for arr in [U2D, V2D, LWDOWN, SWDOWN, T2D, Q2D, PSFC, RAINRATE]]
            if include_lqfrac:
                values_max.append(LQFRAC.max())
                values_min.append(LQFRAC.min())

        else:
            U2D_NODE = model.get_value('U2D_NODE', U2D_NODE)
            V2D_NODE = model.get_value('V2D_NODE', V2D_NODE)
            T2D_NODE = model.get_value('T2D_NODE', T2D_NODE)
            Q2D_NODE = model.get_value('Q2D_NODE', Q2D_NODE)
            SWDOWN_NODE = model.get_value('SWDOWN_NODE', SWDOWN_NODE)
            LWDOWN_NODE = model.get_value('LWDOWN_NODE', LWDOWN_NODE)
            PSFC_NODE = model.get_value('PSFC_NODE', PSFC_NODE)
            RAINRATE_NODE = model.get_value('RAINRATE_NODE', RAINRATE_NODE)

            U2D_ELEMENT = model.get_value('U2D_ELEMENT', U2D_ELEMENT)
            V2D_ELEMENT = model.get_value('V2D_ELEMENT', V2D_ELEMENT)
            T2D_ELEMENT = model.get_value('T2D_ELEMENT', T2D_ELEMENT)
            Q2D_ELEMENT = model.get_value('Q2D_ELEMENT', Q2D_ELEMENT)
            SWDOWN_ELEMENT = model.get_value('SWDOWN_ELEMENT', SWDOWN_ELEMENT)
            LWDOWN_ELEMENT = model.get_value('LWDOWN_ELEMENT', LWDOWN_ELEMENT)
            PSFC_ELEMENT = model.get_value('PSFC_ELEMENT', PSFC_ELEMENT)
            RAINRATE_ELEMENT = model.get_value('RAINRATE_ELEMENT', RAINRATE_ELEMENT)

            if include_lqfrac:
                LQFRAC_NODE = model.get_value('LQFRAC_NODE', LQFRAC_NODE)
                LQFRAC_ELEMENT = model.get_value('LQFRAC_ELEMENT', LQFRAC_ELEMENT)

            values_max = [
                U2D_NODE.max(), V2D_NODE.max(), LWDOWN_NODE.max(), SWDOWN_NODE.max(), T2D_NODE.max(),
                Q2D_NODE.max(), PSFC_NODE.max(), RAINRATE_NODE.max(),
                U2D_ELEMENT.max(), V2D_ELEMENT.max(), LWDOWN_ELEMENT.max(), SWDOWN_ELEMENT.max(), T2D_ELEMENT.max(),
                Q2D_ELEMENT.max(), PSFC_ELEMENT.max(), RAINRATE_ELEMENT.max()
            ]
            values_min = [
                U2D_NODE.min(), V2D_NODE.min(), LWDOWN_NODE.min(), SWDOWN_NODE.min(), T2D_NODE.min(),
                Q2D_NODE.min(), PSFC_NODE.min(), RAINRATE_NODE.min(),
                U2D_ELEMENT.min(), V2D_ELEMENT.min(), LWDOWN_ELEMENT.min(), SWDOWN_ELEMENT.min(), T2D_ELEMENT.min(),
                Q2D_ELEMENT.min(), PSFC_ELEMENT.min(), RAINRATE_ELEMENT.min()
            ]
            if include_lqfrac:
                values_max.extend([LQFRAC_NODE.max(), LQFRAC_ELEMENT.max()])
                values_min.extend([LQFRAC_NODE.min(), LQFRAC_ELEMENT.min()])

        print_forcing_summary('max', values_max, include_lqfrac, is_unstructured, model_time)
        print_forcing_summary('min', values_min, include_lqfrac, is_unstructured, model_time)

    print('\nFinalizing the BMI')
    model.finalize()


def print_forcing_summary(label: str, values: list[float], include_lqfrac: bool, is_unstructured: bool, model_time: datetime.datetime):
    print(f"\n==== {label.upper()} VALUES ====")

    model_time_str = model_time.strftime("%Y-%m-%d %H:%M:%S")
    model_time_header = "model time"

    if is_unstructured:
        base_labels = [
            'U2D_NODE', 'V2D_NODE', 'LWDOWN_NODE', 'SWDOWN_NODE', 'T2D_NODE', 'Q2D_NODE',
            'PSFC_NODE', 'RAINRATE_NODE', 'U2D_ELEMENT', 'V2D_ELEMENT', 'LWDOWN_ELEMENT',
            'SWDOWN_ELEMENT', 'T2D_ELEMENT', 'Q2D_ELEMENT', 'PSFC_ELEMENT', 'RAINRATE_ELEMENT'
        ]
        if include_lqfrac:
            base_labels += ['LQFRAC_NODE', 'LQFRAC_ELEMENT']
    else:
        base_labels = [
            'U2D_ELEMENT', 'V2D_ELEMENT', 'LWDOWN_ELEMENT', 'SWDOWN_ELEMENT',
            'T2D_ELEMENT', 'Q2D_ELEMENT', 'PSFC_ELEMENT', 'RAINRATE_ELEMENT'
        ]
        if include_lqfrac:
            base_labels.append('LQFRAC_ELEMENT')

    # Full headers and row values
    headers = [model_time_header] + base_labels
    value_strings = [model_time_str] + [f"{v:.6g}" for v in values]

    # Determine column widths
    col_widths = [max(len(h), len(v)) for h, v in zip(headers, value_strings)]

    # Print header and value rows
    header_row = " | ".join(f"{h:<{w}}" for h, w in zip(headers, col_widths))
    value_row = " | ".join(f"{v:<{w}}" for v, w in zip(value_strings, col_widths))

    print(header_row)
    print(value_row)


def get_options():
    # TODO keyword arguments should start with --
    parser = argparse.ArgumentParser()

    parser.add_argument('start_time',
                        type=str,
                        help="Start time should correspond to the forecast cycle time + 1 timestep. Format = 'YYYY-MM-DD HH:mm:ss'")
    parser.add_argument('end_time',
                        type=str,
                        help="End time should correspond to the last forecast time step you want to calculate. Format = 'YYYY-MM-DD HH:mm:ss'")
    parser.add_argument('-config_path',
                        type=pathlib.Path,
                        help="Config path for config.yml, otherwise defaults to ./config.yml")
    parser.add_argument('-b_date',
                        type=str,
                        help="Begin date, should be the start date/time for the forecast cycle, format= 'YYYYMMDDHHmm'. If omitted, reads from configuration file.")
    parser.add_argument('-geogrid',
                        type=str,
                        help="Full path for geogrid/ESMF Mesh file. If omitted, reads from configuration file.")
    parser.add_argument('-output_path',
                        type=pathlib.Path,
                        help="A user-provided output path - must include full directory and filename. If omitted, a filename will be automatically generated, in the ScratchDir specified in the config file.")

    return parser.parse_args()


def main():
    args = get_options()
    run_bmi(
        start_time=args.start_time,
        end_time=args.end_time,
        config_path=args.config_path,
        b_date=args.b_date,
        geogrid=args.geogrid,
        output_path=args.output_path
    )


if __name__ == '__main__':
    main()
