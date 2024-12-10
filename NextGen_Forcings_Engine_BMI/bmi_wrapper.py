'''
BMI Forcings Engine standalone mode wrapper script. 

Provides ability to run the BMI Forcings Engine pipeline in standalone mode using a single command.

example usage: python bmi_wrapper.py short_range Gage_01011000.gpkg
'''

import argparse
import datetime
import subprocess
import yaml
import os
import mpi4py

def execute(args):

    '''
    Execute the full forcings engine BMI pipeline in standalone mode.
    
    Modules executed: ESMF Mesh Conversion, Forcing Extraction, Forcing Engine BMI
    
    args:
        cycle_name (str): The NWM Forecast cycle to execute (ie: short_range)
        hyfab_name (str): The name of the hydrofabric domain file to use (ie: Gage_01011000.gpkg)
        -config_input (str): Optional path to the wrapper config file.
        -output_path (str): Optional full path to specify forcing engine output location.
        -np (str): Optional number of processes to use.
    '''
    
    #read in user-provided arguments
    cycle_name=args.cycle_name
    hyfab_name=args.hyfab_name
    config_input=args.config_input
    output_path=args.output_path
    num_processes=args.np
    
    #read in config file
    if config_input != None:
        config_read = config_input
    else:
        config_read = './wrapper_config.yml'  
    with open(config_read, 'r') as config_file:
        config= yaml.safe_load(config_file)
    
    #use the Gage_######## string to construct ESMF mesh filename
    base_geo_name = hyfab_name.split('.')[0]
    mesh_fileName = f"{base_geo_name}_ESMF_Mesh.nc"
    
    #Reading path variables from config file
    mesh_scriptPath=config['global']['mesh_script_path']
    mesh_inPath = os.path.join(config['global']['mesh_in_base_path'], hyfab_name)
    mesh_outPath = os.path.join(config['global']['mesh_out_base_path'], mesh_fileName)
    extraction_scriptPath = config['global']['extraction_script_path']
    extraction_outPath = config['global']['extraction_out_path']
    bmi_scriptPath = config['global']['bmi_script_path']
    mesh_env = config['global']['mesh_env']
    extraction_env = config['global']['extract_env']
    engine_env = config['global']['engine_env']
    
    #Get the current time in UTC
    dNowUTC = datetime.datetime.utcnow()
    dNow = datetime.datetime(dNowUTC.year,dNowUTC.month,dNowUTC.day,dNowUTC.hour)
    
    if not os.path.exists(mesh_outPath):
        # Execute hyfab to ESMF mesh conversion
        cmd0 = [
                "conda", "run", "-n", mesh_env,
                "python", mesh_scriptPath, mesh_inPath, mesh_outPath
        ]   
        subprocess.run(cmd0, check=True)
    else:
        print(f"ESMF mesh file already exists at {mesh_outPath}, skipping conversion.")
    
    #Process based on NWM forecast cycle
    if cycle_name=="short_range":
        
        #Set cycle-specific path variables
        configPath = config['short_range']['sr_config_path']
        hrrr_extract_scriptPath = os.path.join(extraction_scriptPath, "CONUS", "get_conus_HRRR.py")
        hrrr_extract_outPath = os.path.join(extraction_outPath, config['short_range']['hrrr_out_path'].lstrip('/'))     
        rap_extract_scriptPath = os.path.join(extraction_scriptPath,"CONUS", "get_conus_RAP.py")
        rap_extract_outPath = os.path.join(extraction_outPath, config['short_range']['rap_out_path'].lstrip('/'))
        
        #set cycle-specific time variables
        #TODO: Make timesteps configurable with defaults set in config file?
        b_date_dt = dNow - datetime.timedelta(seconds=3600*2)
        start_time_dt = b_date_dt + datetime.timedelta(seconds=3600*1)
        end_time_dt = start_time_dt + datetime.timedelta(seconds=3600*17)      
        #create strings from datetime objects for use in commands
        b_date = b_date_dt.strftime("%Y%m%d%H%M")
        start_time = start_time_dt.strftime("%Y-%m-%d %H:%M:%S")
        end_time = end_time_dt.strftime("%Y-%m-%d %H:%M:%S")
        
        #Run the forcing_extraction script for HRRR
        cmd1 = [
            "conda", "run", "-n", extraction_env,
            "python", hrrr_extract_scriptPath, hrrr_extract_outPath,
            "--lookBackHours=2",
            "--lagBackHours=1"
        ]
        subprocess.run(cmd1, check=True)
        
        #Run the forcing_extraction script for RAP
        cmd2 = [
            "conda", "run", "-n", extraction_env,
            "python", rap_extract_scriptPath, rap_extract_outPath,
            "--lookBackHours=2",
            "--lagBackHours=1"
        ]
        subprocess.run(cmd2, check=True)        

    elif cycle_name == 'medium_range_blend':
        
        #Set cycle-specific path variables
        configPath = config['medium_range_blend']['mrb_config_path']
        gfs_extract_scriptPath = os.path.join(extraction_scriptPath, "Global", "get_prod_GFS.py")
        gfs_extract_outPath = os.path.join(extraction_outPath, config['medium_range_blend']['gfs_out_path'].lstrip('/'))
        nbm_extract_scriptPath = os.path.join(extraction_scriptPath, "CONUS", "get_prod_NBM.py")
        nbm_extract_outPath = os.path.join(extraction_outPath, config['medium_range_blend']['nbm_out_path'].lstrip('/'))
                
        #set cycle-specific time variables
        #TODO: Make timesteps configurable with defaults set in config file?
        #TODO: Set end time to actual NWM cycle (10-day)
        
        b_date_dt = dNow - datetime.timedelta(seconds=3600*3)
        b_date_dt = b_date_dt.replace(hour=(b_date_dt.hour // 6) * 6, minute=0, second=0, microsecond=0)
        start_time_dt = b_date_dt + datetime.timedelta(seconds=3600*1)
        end_time_dt = start_time_dt + datetime.timedelta(seconds=3600*17)      
        #create strings from datetime objects for use in commands
        b_date = b_date_dt.strftime("%Y%m%d%H%M")
        start_time = start_time_dt.strftime("%Y-%m-%d %H:%M:%S")
        end_time = end_time_dt.strftime("%Y-%m-%d %H:%M:%S")     

        #calculate lookback window since GFS is on a 6-hourly cycle
        hours_difference = (dNow - b_date_dt).total_seconds() / 3600
        lagback = hours_difference - 1
        lookback = hours_difference


        #Run the forcing_extraction script for GFS        
        cmd1 = [
            "conda", "run", "-n", extraction_env,
            "python", gfs_extract_scriptPath, gfs_extract_outPath,
            f"--lookBackHours={int(lookback)}",
            f"--lagBackHours={int(lagback)}"
        ]
        subprocess.run(cmd1, check=True)
        
        #Run the forcing_extraction script for NBM
                
        cmd2 = [
            "conda", "run", "-n", extraction_env,
            "python", nbm_extract_scriptPath, nbm_extract_outPath,
            f"--lookBackHours={int(lookback)}",
            f"--lagBackHours={int(lagback)}"
        ]
        subprocess.run(cmd2, check=True)  

    elif cycle_name == 'standard_ana':
        
        #Set cycle-specific path variables
        configPath = config['standard_ana']['ana_config_path']
        hrrr_extract_scriptPath = os.path.join(extraction_scriptPath, "CONUS", "get_conus_HRRR_AnA.py")
        hrrr_extract_outPath = os.path.join(extraction_outPath, config['standard_ana']['hrrr_out_path'].lstrip('/'))
        rap_extract_scriptPath = os.path.join(extraction_scriptPath, "CONUS", "get_conus_RAP_AnA.py")
        rap_extract_outPath = os.path.join(extraction_outPath, config['standard_ana']['rap_out_path'].lstrip('/'))
        mrms_ms_extract_scriptPath = os.path.join(extraction_scriptPath, "CONUS", "get_conus_MRMS_MultiSensor.py")
        mrms_ms_extract_outPath = os.path.join(extraction_outPath, config['standard_ana']['mrms_ms_out_path'].lstrip('/'))  
        mrms_ro_extract_scriptPath = os.path.join(extraction_scriptPath, "CONUS", "get_conus_MRMS_Radar.py")
        mrms_ro_extract_outPath = os.path.join(extraction_outPath, config['standard_ana']['mrms_ro_out_path'].lstrip('/'))  
                     
        #set cycle-specific time variables
        #TODO: Make timesteps configurable with defaults set in config file?
        
        b_date_dt = dNow - datetime.timedelta(seconds=3600*1)
        start_time_dt = b_date_dt - datetime.timedelta(seconds=3600*3)
        end_time_dt = b_date_dt - datetime.timedelta(seconds=3600*1)
        #create strings from datetime objects for use in commands
        b_date = b_date_dt.strftime("%Y%m%d%H%M")
        start_time = start_time_dt.strftime("%Y-%m-%d %H:%M:%S")
        end_time = end_time_dt.strftime("%Y-%m-%d %H:%M:%S")     

        #calculate lookback window since this is an AnA run
        hours_difference = (dNow - b_date_dt).total_seconds() / 3600
        lagback = 0
        lookback = hours_difference + 4

        #Run the forcing_extraction script for HRRR        
        cmd1a = [
            "conda", "run", "-n", extraction_env,
            "python", hrrr_extract_scriptPath, hrrr_extract_outPath,
            f"--lookBackHours={int(lookback)}",
            f"--lagBackHours={int(lagback)}", 
            "--cleanBackHours=0"
        ]
        subprocess.run(cmd1a, check=True)
        
        #Run the forcing_extraction script for RAP
                
        cmd1b = [
            "conda", "run", "-n", extraction_env,
            "python", rap_extract_scriptPath, rap_extract_outPath,
            f"--lookBackHours={int(lookback)}",
            f"--lagBackHours={int(lagback)}", 
            "--cleanBackHours=0"
        ]
        subprocess.run(cmd1b, check=True)  
        
        #Run the forcing_extraction script for MRMS_MS        
        cmd2a = [
            "conda", "run", "-n", extraction_env,
            "python", mrms_ms_extract_scriptPath, mrms_ms_extract_outPath,
            f"--lookBackHours={int(lookback)}",
            f"--lagBackHours={int(lagback)}"
        ]
        subprocess.run(cmd2a, check=True)
        
        #Run the forcing_extraction script for MRMS_RO
                
        cmd2b = [
            "conda", "run", "-n", extraction_env,
            "python", mrms_ro_extract_scriptPath, mrms_ro_extract_outPath,
            f"--lookBackHours={int(lookback)}",
            f"--lagBackHours={int(lagback)}"
        ]
        subprocess.run(cmd2b, check=True)  

    elif cycle_name=="long_range":
        
        #TODO: alter for NWM cycle -  ensemble forecasting, 30 day
        
        #Set cycle-specific path variables
        configPath = config['long_range']['lr_config_path']
        cfs_extract_scriptPath = os.path.join(extraction_scriptPath, "Global", "get_CFSv2.py")
        cfs_extract_outPath = os.path.join(extraction_outPath, config['long_range']['cfs_out_path'].lstrip('/'))     

        #set cycle-specific time variables
        #TODO: Make timesteps configurable with defaults set in config file?
        #TODO: Set end time to actual NWM cycle (30-day)

        if dNowUTC.hour in [1, 2, 7, 8, 13, 14, 19, 20]:
            b_date_dt = dNow - datetime.timedelta(seconds=3600*3)
        else: 
            b_date_dt = dNow - datetime.timedelta(seconds=3600*7)

        b_date_dt = b_date_dt.replace(hour=(b_date_dt.hour // 6) * 6, minute=0, second=0, microsecond=0)
        start_time_dt = b_date_dt + datetime.timedelta(seconds=3600*1)
        end_time_dt = start_time_dt + datetime.timedelta(seconds=3600*48)      
        #create strings from datetime objects for use in commands
        b_date = b_date_dt.strftime("%Y%m%d%H%M")
        start_time = start_time_dt.strftime("%Y-%m-%d %H:%M:%S")
        end_time = end_time_dt.strftime("%Y-%m-%d %H:%M:%S")     

        #calculate lookback window since CFS is on a 6-hourly cycle
        hours_difference = (dNow - b_date_dt).total_seconds() / 3600
        lagback = hours_difference - 1
        lookback = hours_difference
        
        #Run the forcing_extraction script for CFS
        cmd1 = [
            "conda", "run", "-n", extraction_env,
            "python", cfs_extract_scriptPath, cfs_extract_outPath,
            f"--lookBackHours={int(lookback)}",
            f"--lagBackHours={int(lagback)}"
        ]
        subprocess.run(cmd1, check=True)

    elif cycle_name == 'extended_ana':
        
        #Set cycle-specific path variables
        configPath = config['extended_ana']['ana_config_path']
        hrrr_extract_scriptPath = os.path.join(extraction_scriptPath, "CONUS", "get_conus_HRRR_AnA.py")
        hrrr_extract_outPath = os.path.join(extraction_outPath, config['extended_ana']['hrrr_out_path'].lstrip('/'))
        rap_extract_scriptPath = os.path.join(extraction_scriptPath, "CONUS", "get_conus_RAP_AnA.py")
        rap_extract_outPath = os.path.join(extraction_outPath, config['extended_ana']['rap_out_path'].lstrip('/'))
        stage_iv_extract_scriptPath = os.path.join(extraction_scriptPath, "CONUS", "get_conus_StageIV.py")
        stage_iv_extract_outPath = os.path.join(extraction_outPath, config['extended_ana']['stage_iv_out_path'].lstrip('/'))  
                 
        #set cycle-specific time variables
        #TODO: Make timesteps configurable with defaults set in config file?
        
        b_date_dt = dNow - datetime.timedelta(seconds=3600*1)
        start_time_dt = b_date_dt - datetime.timedelta(seconds=3600*16)
        print(f"start_time_dt: {start_time_dt}")
        end_time_dt = b_date_dt - datetime.timedelta(seconds=3600*1)
        print(f"end_time_dt: {end_time_dt}")      
        #create strings from datetime objects for use in commands
        b_date = b_date_dt.strftime("%Y%m%d%H%M")
        start_time = start_time_dt.strftime("%Y-%m-%d %H:%M:%S")
        end_time = end_time_dt.strftime("%Y-%m-%d %H:%M:%S")     

        #calculate lookback window since this is an AnA run
        hours_difference = (dNow - b_date_dt).total_seconds() / 3600
        lagback = 0
        lookback = hours_difference + 17
        print(f"lagback = {lagback}")
        print(f"lookback = {lookback}")


        #Run the forcing_extraction script for HRRR        
        cmd1a = [
            "conda", "run", "-n", extraction_env,
            "python", hrrr_extract_scriptPath, hrrr_extract_outPath,
            f"--lookBackHours={int(lookback)}",
            f"--lagBackHours={int(lagback)}", 
            "--cleanBackHours=0"
        ]
        subprocess.run(cmd1a, check=True)
        
        #Run the forcing_extraction script for RAP
                
        cmd1b = [
            "conda", "run", "-n", extraction_env,
            "python", rap_extract_scriptPath, rap_extract_outPath,
            f"--lookBackHours={int(lookback)}",
            f"--lagBackHours={int(lagback)}", 
            "--cleanBackHours=0"
        ]
        subprocess.run(cmd1b, check=True)  
        
        #Run the forcing_extraction script for stage_iv        
        cmd2 = [
            "conda", "run", "-n", extraction_env,
            "python", stage_iv_extract_scriptPath, stage_iv_extract_outPath,
            f"--lookBackHours={int(lookback)}",
            f"--lagBackHours={int(lagback)}"
        ]
        subprocess.run(cmd2, check=True)      
   
    else:
        print("valid cycle options: short_range, medium_range_blend, standard_ana, long_range, extended_ana")     
    
    #run the forcing engine BMI
    if output_path != None:
        if num_processes != None:
            cmd3 = [
                "conda", "run", "-n", engine_env,
                "mpirun", "-np", str(num_processes), 
                "python", bmi_scriptPath, f"-config_path={configPath}", f"-b_date={b_date}", f"-geogrid={mesh_outPath}",
                f"-output_path={output_path}", start_time, end_time        
            ]
        else:
            cmd3 = [
                "conda", "run", "-n", engine_env,
                "python", bmi_scriptPath, f"-config_path={configPath}", f"-b_date={b_date}", f"-geogrid={mesh_outPath}",
                f"-output_path={output_path}",start_time, end_time        
            ]
    else:
        if num_processes != None:
            cmd3 = [
                "conda", "run", "-n", engine_env,
                "mpirun", "-np", str(num_processes), 
                "python", bmi_scriptPath, f"-config_path={configPath}", f"-b_date={b_date}", f"-geogrid={mesh_outPath}",
                start_time, end_time
            ]
        else:
            cmd3 = [
                "conda", "run", "-n", engine_env,
                "python", bmi_scriptPath, f"-config_path={configPath}", f"-b_date={b_date}", f"-geogrid={mesh_outPath}",
                start_time, end_time
            ]       
    subprocess.run(cmd3, check=True)

  

def get_options():
    '''
    Function to accept and parse arguments.
    
    Returns an argparse object.
    '''
    parser = argparse.ArgumentParser()
    parser.add_argument('cycle_name', help='Name of NWM cycle, for example short_range')
    parser.add_argument('hyfab_name', help='Name of hydrofabric file for conversion to ESMF. Ex: Gage_01123000.gpkg')
    parser.add_argument('-config_input', help='Path to wrapper config file. If omitted, defaults to ./wrapper_config.yml')
    parser.add_argument('-output_path', help='Full path for nc output file. If omitted, filename will be generated automatically, and placed in the ScratchDir configured in config file.') 
    parser.add_argument('-np', help='The number of processes to use when executing the forcing engine. If omitted, will default to one process.')
    
    return parser.parse_args()

if __name__ == '__main__':
    args = get_options()
    execute(args)   
