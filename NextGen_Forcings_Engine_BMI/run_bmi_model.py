from pathlib import Path
import datetime
import pandas as pd
import numpy as np
import sys
import argparse
import pathlib

# This is the NextGen Forcings Engine BMI instance to execute
from NextGen_Forcings_Engine.bmi_model import NWMv3_Forcing_Engine_BMI_model

def execute(args):

    '''
    Wrapper script to execute the forcing engine BMI code. Requires user to pass start_time and end_time as arguments. Additional configurations are parsed from config.yml - User can provide a config_path to point to a specific config file.

    example: python run_bmi_model.py '2024-11-19 20:00:00' '2024-11-20 07:00:00'
    '''

    # User input to specify the start and end time of the 
    # NextGen Forcings Engine BMI standalone execution
    start_time = args.start_time
    end_time = args.end_time

    start_time = datetime.datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
    end_time = datetime.datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
    ngen_datetimes = pd.date_range(start=start_time.strftime('%Y-%m-%d %H:%M:%S'),end=end_time.strftime('%Y-%m-%d %H:%M:%S'),freq='h')

    print(start_time, end_time)
    print(f"ngen_datetimes: {ngen_datetimes}")


    # creating an instance of a model
    print('creating an instance of an BMI_MODEL model object')
    model = NWMv3_Forcing_Engine_BMI_model()

    # Initializing the BMI
    print('Initializing the BMI')
    if(args.config_path != None):
        model.initialize(bmi_cfg_file_name=str(args.config_path), b_date=args.b_date, geogrid=args.geogrid, output_path=args.output_path)
    else:
        current_dir = Path(__file__).parent.resolve()
        model.initialize(bmi_cfg_file_name=str(current_dir.joinpath('config.yml')),b_date=args.b_date, geogrid=args.geogrid, output_path=args.output_path)

    # Now loop through the inputs, set the forcing values, and update the model
    print('Now loop through the inputs, updating the model, and extracting forcing data')
    print('\n')
    print('rank')
    print(model._mpi_meta.rank)
    if(model._grid_type == "gridded"):
        # Initialize numpy arrays for get value
        U2D = np.zeros(model._varsize,dtype=float)
        V2D = np.zeros(model._varsize,dtype=float)
        LWDOWN = np.zeros(model._varsize,dtype=float)
        SWDOWN = np.zeros(model._varsize,dtype=float)
        T2D = np.zeros(model._varsize,dtype=float)
        Q2D = np.zeros(model._varsize,dtype=float)
        PSFC = np.zeros(model._varsize,dtype=float)
        RAINRATE = np.zeros(model._varsize,dtype=float)
        if(model._job_meta.include_lqfrac == 1):
            LQFRAC = np.zeros(model._varsize,dtype=float)
    elif(model._grid_type == "hydrofabric"):
        # Initialize numpy arrays for get value
        CAT_IDS = np.zeros(model._varsize,dtype=int)
        U2D = np.zeros(model._varsize,dtype=float)
        V2D = np.zeros(model._varsize,dtype=float)
        LWDOWN = np.zeros(model._varsize,dtype=float)
        SWDOWN = np.zeros(model._varsize,dtype=float)
        T2D = np.zeros(model._varsize,dtype=float)
        Q2D = np.zeros(model._varsize,dtype=float)
        PSFC = np.zeros(model._varsize,dtype=float)
        RAINRATE = np.zeros(model._varsize,dtype=float)
        if(model._job_meta.include_lqfrac == 1):
            LQFRAC = np.zeros(model._varsize,dtype=float)
    else:
        # Initialize numpy arrays for get value
        U2D_NODE = np.zeros(model._varsize,dtype=float)
        V2D_NODE = np.zeros(model._varsize,dtype=float)
        LWDOWN_NODE = np.zeros(model._varsize,dtype=float)
        SWDOWN_NODE = np.zeros(model._varsize,dtype=float)
        T2D_NODE = np.zeros(model._varsize,dtype=float)
        Q2D_NODE = np.zeros(model._varsize,dtype=float)
        PSFC_NODE = np.zeros(model._varsize,dtype=float)
        RAINRATE_NODE = np.zeros(model._varsize,dtype=float)

        U2D_ELEMENT = np.zeros(model._varsize_elem,dtype=float)
        V2D_ELEMENT = np.zeros(model._varsize_elem,dtype=float)
        LWDOWN_ELEMENT = np.zeros(model._varsize_elem,dtype=float)
        SWDOWN_ELEMENT = np.zeros(model._varsize_elem,dtype=float)
        T2D_ELEMENT = np.zeros(model._varsize_elem,dtype=float)
        Q2D_ELEMENT = np.zeros(model._varsize_elem,dtype=float)
        PSFC_ELEMENT = np.zeros(model._varsize_elem,dtype=float)
        RAINRATE_ELEMENT = np.zeros(model._varsize_elem,dtype=float)
        if(model._job_meta.include_lqfrac == 1):
            LQFRAC_NODE = np.zeros(model._varsize,dtype=float)
            LQFRAC_ELEMENT = np.zeros(model._varsize_elem,dtype=float)
    for x in range(len(ngen_datetimes)):

        #########################################
        # UPDATE THE MODEL AND GET REGRIDDED FORCINGS #
        model.update()     ######################
        #########################################

        # PRINT THE MODEL RESULTS FOR THIS TIME STEP#################################################

        ### Due to numpy version, we must initialize arrays
        ### to get values and directly call the array as an
        ### input arguement
        if(model._grid_type == "gridded"):
            U2D = model.get_value('U2D_ELEMENT',U2D)
            V2D = model.get_value('V2D_ELEMENT',V2D)
            T2D = model.get_value('T2D_ELEMENT',T2D)
            Q2D = model.get_value('Q2D_ELEMENT',Q2D)
            SWDOWN = model.get_value('SWDOWN_ELEMENT',SWDOWN)
            LWDOWN = model.get_value('LWDOWN_ELEMENT',LWDOWN)
            PSFC = model.get_value('PSFC_ELEMENT',PSFC)
            RAINRATE = model.get_value('RAINRATE_ELEMENT',RAINRATE)
            if(model._job_meta.include_lqfrac == 1):
                LQFRAC = model.get_value('LQFRAC_ELEMENT',LQFRAC)
                print('model time', 'U2D_ELEMENT max', 'V2D_ELEMENT max', 'LWDOWN_ELEMENT max','SWDOWN_ELEMENT max','T2D_ELEMENT max','Q2D_ELEMENT max','PSFC_ELEMENT max','RAINRATE_ELEMENT max', 'LQFRAC_ELEMENT max')
                print(model.get_current_time(), U2D.max(), V2D.max(), LWDOWN.max(), SWDOWN.max(), T2D.max(), Q2D.max(), PSFC.max(), RAINRATE.max(), LQFRAC.max())
                print('model time', 'U2D_ELEMENT min', 'V2D_ELEMENT min', 'LWDOWN_ELEMENT min','SWDOWN_ELEMENT min','T2D_ELEMENT min','Q2D_ELEMENT min','PSFC_ELEMENT min','RAINRATE_ELEMENT min', 'LQFRAC_ELEMENT min')
                print(model.get_current_time(), U2D.min(), V2D.min(), LWDOWN.min(), SWDOWN.min(), T2D.min(), Q2D.min(), PSFC.min(), RAINRATE.min(), LQFRAC.min())
            else:
                print('model time', 'U2D_ELEMENT max', 'V2D_ELEMENT max', 'LWDOWN_ELEMENT max','SWDOWN_ELEMENT max','T2D_ELEMENT max','Q2D_ELEMENT max','PSFC_ELEMENT max','RAINRATE_ELEMENT max')
                print(model.get_current_time(), U2D.max(), V2D.max(), LWDOWN.max(), SWDOWN.max(), T2D.max(), Q2D.max(), PSFC.max(), RAINRATE.max())
                print('model time', 'U2D_ELEMENT min', 'V2D_ELEMENT min', 'LWDOWN_ELEMENT min','SWDOWN_ELEMENT min','T2D_ELEMENT min','Q2D_ELEMENT min','PSFC_ELEMENT min','RAINRATE_ELEMENT min')
                print(model.get_current_time(), U2D.min(), V2D.min(), LWDOWN.min(), SWDOWN.min(), T2D.min(), Q2D.min(), PSFC.min(), RAINRATE.min())
        elif(model._grid_type == "hydrofabric"):
            CAT_IDS = model.get_value('CAT-ID',CAT_IDS)
            U2D = model.get_value('U2D_ELEMENT',U2D)
            V2D = model.get_value('V2D_ELEMENT',V2D)
            T2D = model.get_value('T2D_ELEMENT',T2D)
            Q2D = model.get_value('Q2D_ELEMENT',Q2D)
            SWDOWN = model.get_value('SWDOWN_ELEMENT',SWDOWN)
            LWDOWN = model.get_value('LWDOWN_ELEMENT',LWDOWN)
            PSFC = model.get_value('PSFC_ELEMENT',PSFC)
            RAINRATE = model.get_value('RAINRATE_ELEMENT',RAINRATE)
            if(model._job_meta.include_lqfrac == 1):
                LQFRAC = model.get_value('LQFRAC_ELEMENT',LQFRAC)
                print('model time', 'U2D_ELEMENT max', 'V2D_ELEMENT max', 'LWDOWN_ELEMENT max','SWDOWN_ELEMENT max','T2D_ELEMENT max','Q2D_ELEMENT max','PSFC_ELEMENT max','RAINRATE_ELEMENT max', 'LQFRAC_ELEMENT max')
                print(model.get_current_time(), U2D.max(), V2D.max(), LWDOWN.max(), SWDOWN.max(), T2D.max(), Q2D.max(), PSFC.max(), RAINRATE.max(), LQFRAC.max())
                print('model time', 'U2D_ELEMENT min', 'V2D_ELEMENT min', 'LWDOWN_ELEMENT min','SWDOWN_ELEMENT min','T2D_ELEMENT min','Q2D_ELEMENT min','PSFC_ELEMENT min','RAINRATE_ELEMENT min', 'LQFRAC_ELEMENT min')
                print(model.get_current_time(), U2D.min(), V2D.min(), LWDOWN.min(), SWDOWN.min(), T2D.min(), Q2D.min(), PSFC.min(), RAINRATE.min(), LQFRAC.min())
            else:
                print('model time', 'U2D_ELEMENT max', 'V2D_ELEMENT max', 'LWDOWN_ELEMENT max','SWDOWN_ELEMENT max','T2D_ELEMENT max','Q2D_ELEMENT max','PSFC_ELEMENT max','RAINRATE_ELEMENT max')
                print(model.get_current_time(), U2D.max(), V2D.max(), LWDOWN.max(), SWDOWN.max(), T2D.max(), Q2D.max(), PSFC.max(), RAINRATE.max())
                print('model time', 'U2D_ELEMENT min', 'V2D_ELEMENT min', 'LWDOWN_ELEMENT min','SWDOWN_ELEMENT min','T2D_ELEMENT min','Q2D_ELEMENT min','PSFC_ELEMENT min','RAINRATE_ELEMENT min')
                print(model.get_current_time(), U2D.min(), V2D.min(), LWDOWN.min(), SWDOWN.min(), T2D.min(), Q2D.min(), PSFC.min(), RAINRATE.min())

        else:
            U2D_NODE = model.get_value('U2D_NODE',U2D_NODE)
            V2D_NODE = model.get_value('V2D_NODE',V2D_NODE)
            T2D_NODE = model.get_value('T2D_NODE',T2D_NODE)
            Q2D_NODE = model.get_value('Q2D_NODE',Q2D_NODE)
            SWDOWN_NODE = model.get_value('SWDOWN_NODE',SWDOWN_NODE)
            LWDOWN_NODE = model.get_value('LWDOWN_NODE',LWDOWN_NODE)
            PSFC_NODE = model.get_value('PSFC_NODE',PSFC_NODE)
            RAINRATE_NODE = model.get_value('RAINRATE_NODE',RAINRATE_NODE)

            U2D_ELEMENT = model.get_value('U2D_ELEMENT',U2D_ELEMENT)
            V2D_ELEMENT = model.get_value('V2D_ELEMENT',V2D_ELEMENT)
            T2D_ELEMENT = model.get_value('T2D_ELEMENT',T2D_ELEMENT)
            Q2D_ELEMENT = model.get_value('Q2D_ELEMENT',Q2D_ELEMENT)
            SWDOWN_ELEMENT = model.get_value('SWDOWN_ELEMENT',SWDOWN_ELEMENT)
            LWDOWN_ELEMENT = model.get_value('LWDOWN_ELEMENT',LWDOWN_ELEMENT)
            PSFC_ELEMENT = model.get_value('PSFC_ELEMENT',PSFC_ELEMENT)
            RAINRATE_ELEMENT = model.get_value('RAINRATE_ELEMENT',RAINRATE_ELEMENT)

            if(model._job_meta.include_lqfrac == 1):
                LQFRAC_NODE = model.get_value('LQFRAC_NODE',LQFRAC_NODE)
                LQFRAC_ELEMENT = model.get_value('LQFRAC_ELEMENT',LQFRAC_ELEMENT)
                print('model time', 'U2D_NODE max', 'V2D_NODE max', 'LWDOWN_NODE max','SWDOWN_NODE max','T2D_NODE max','Q2D_NODE max','PSFC_NODE max','RAINRATE_NODE max', 'LQFRAC_NODE max', 'U2D_ELEMENT max', 'V2D_ELEMENT max', 'LWDOWN_ELEMENT max','SWDOWN_ELEMENT max','T2D_ELEMENT max','Q2D_ELEMENT max','PSFC_ELEMENT max','RAINRATE_ELEMENT max', 'LQFRAC_ELEMENT max')
                print(model.get_current_time(), U2D_NODE.max(), V2D_NODE.max(), LWDOWN_NODE.max(), SWDOWN_NODE.max(), T2D_NODE.max(), Q2D_NODE.max(), PSFC_NODE.max(), RAINRATE_NODE.max(), LQFRAC_NODE.max(), U2D_ELEMENT.max(), V2D_ELEMENT.max(), LWDOWN_ELEMENT.max(), SWDOWN_ELEMENT.max(), T2D_ELEMENT.max(), Q2D_ELEMENT.max(), PSFC_ELEMENT.max(), RAINRATE_ELEMENT.max(), LQFRAC_ELEMENT.max())
                print('model time', 'U2D_NODE min', 'V2D_NODE min', 'LWDOWN_NODE min','SWDOWN_NODE min','T2D_NODE min','Q2D_NODE min','PSFC_NODE min','RAINRATE_NODE min', 'LQFRAC_NODE min', 'U2D_ELEMENT min', 'V2D_ELEMENT min', 'LWDOWN_ELEMENT min','SWDOWN_ELEMENT min','T2D_ELEMENT min','Q2D_ELEMENT min','PSFC_ELEMENT min','RAINRATE_ELEMENT min','LQFRAC_ELEMENT min')
                print(model.get_current_time(), U2D_NODE.min(), V2D_NODE.min(), LWDOWN_NODE.min(), SWDOWN_NODE.min(), T2D_NODE.min(), Q2D_NODE.min(), PSFC_NODE.min(), RAINRATE_NODE.min(), LQFRAC_NODE.min(), U2D_ELEMENT.min(), V2D_ELEMENT.min(), LWDOWN_ELEMENT.min(), SWDOWN_ELEMENT.min(), T2D_ELEMENT.min(), Q2D_ELEMENT.min(), PSFC_ELEMENT.min(), RAINRATE_ELEMENT.min(),LQFRAC_ELEMENT.min())
            else:
                print('model time', 'U2D_NODE max', 'V2D_NODE max', 'LWDOWN_NODE max','SWDOWN_NODE max','T2D_NODE max','Q2D_NODE max','PSFC_NODE max','RAINRATE_NODE max', 'U2D_ELEMENT max', 'V2D_ELEMENT max', 'LWDOWN_ELEMENT max','SWDOWN_ELEMENT max','T2D_ELEMENT max','Q2D_ELEMENT max','PSFC_ELEMENT max','RAINRATE_ELEMENT max')
                print(model.get_current_time(), U2D_NODE.max(), V2D_NODE.max(), LWDOWN_NODE.max(), SWDOWN_NODE.max(), T2D_NODE.max(), Q2D_NODE.max(), PSFC_NODE.max(), RAINRATE_NODE.max(), U2D_ELEMENT.max(), V2D_ELEMENT.max(), LWDOWN_ELEMENT.max(), SWDOWN_ELEMENT.max(), T2D_ELEMENT.max(), Q2D_ELEMENT.max(), PSFC_ELEMENT.max(), RAINRATE_ELEMENT.max())
                print('model time', 'U2D_NODE min', 'V2D_NODE min', 'LWDOWN_NODE min','SWDOWN_NODE min','T2D_NODE min','Q2D_NODE min','PSFC_NODE min','RAINRATE_NODE min', 'U2D_ELEMENT min', 'V2D_ELEMENT min', 'LWDOWN_ELEMENT min','SWDOWN_ELEMENT min','T2D_ELEMENT min','Q2D_ELEMENT min','PSFC_ELEMENT min','RAINRATE_ELEMENT min')
                print(model.get_current_time(), U2D_NODE.min(), V2D_NODE.min(), LWDOWN_NODE.min(), SWDOWN_NODE.min(), T2D_NODE.min(), Q2D_NODE.min(), PSFC_NODE.min(), RAINRATE_NODE.min(), U2D_ELEMENT.min(), V2D_ELEMENT.min(), LWDOWN_ELEMENT.min(), SWDOWN_ELEMENT.min(), T2D_ELEMENT.min(), Q2D_ELEMENT.min(), PSFC_ELEMENT.min(), RAINRATE_ELEMENT.min())

    # Finalizing the BMI
    print('Finalizing the BMI')
    model.finalize()

def get_options():
    parser = argparse.ArgumentParser()

    parser.add_argument('start_time', help="Start time should correspond to the forecast cycle time + 1 timestep. Format = 'YYYY-MM-DD HH:mm:ss' ")
    parser.add_argument('end_time', help="End time should correspond to the last forecast time step you want to calculate. Format = 'YYYY-MM-DD HH:mm:ss' ")
    parser.add_argument('-config_path', type=pathlib.Path, help="Config path for config.yml, otherwise defaults to ./config.yml")
    parser.add_argument('-b_date', help="Begin date, should be the start date/time for the forecast cycle, format= 'YYYYMMDDHHmm'. If omitted, reads from configuration file.")
    parser.add_argument('-geogrid', help="Full path for geogrid/ESMF Mesh file. If omitted, reads from configuration file.")
    parser.add_argument('-output_path', help="A user-provided output path - must include full directory and filename. If omitted, a filename will be automatically generated, in the ScratchDir specified in the config file.")

    return parser.parse_args()

if __name__ == '__main__':
    args=get_options()
    execute(args)
