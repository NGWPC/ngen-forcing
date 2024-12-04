#!/usr/bin/env bash

#SBATCH --job-name=test_sr_pac
#SBATCH -N 1 
#SBATCH --partition=c5n
#SBATCH --ntasks-per-node=16
#SBATCH --exclusive

# >>> conda initialize >>>
# !! Contents within this block are managed by 'conda init' !!
__conda_setup="$('/contrib/software/miniconda/miniconda/bin/conda' 'shell.bash' 'hook' 2> /dev/null)"
if [ $? -eq 0 ]; then
    eval "$__conda_setup"
else
    if [ -f "/contrib/software/miniconda/miniconda/etc/profile.d/conda.sh" ]; then
        . "/contrib/software/miniconda/miniconda/etc/profile.d/conda.sh"
    else
        export PATH="/contrib/software/miniconda/miniconda/bin:$PATH"
    fi
fi
unset __conda_setup
# <<< conda initialize <<<

conda activate /contrib/software/miniconda/miniconda/envs/nwmwcoss3

export PATH=$PATH:${OE_DIR}/test/packages/prod_util.v2.0.14/ush
export PATH=/contrib/software/gcc/8.5.0/bin:/contrib/software/netcdf/4.7.4/bin:/contrib/software/hdf5/1.12.3/bin:$PATH
export WGRIB2=${OE_DIR}/test/packages/grib2/wgrib2/wgrib2
export LD_LIBRARY_PATH=/contrib/software/gcc/8.5.0/lib64:/contrib/software/netcdf/4.7.4/lib:/contrib/software/hdf5/1.12.3/lib:/home/Zhengtao.Cui/anaconda3/lib:$LD_LIBRARY_PATH

export NDATE=${OE_DIR}/test/packages//prod_util.v2.0.14/exec/ndate

export PARMnwm=${OE_DIR}/test/packages/nwm.v3.0.6/parm

#export COASTAL_FORCING_INPUT_DIR=/lustre/Zhengtao.Cui/test/tmp/nwm_analysis_assim_coastal_hawaii_13_v3.0/analysis_assim_coastal_hawaii_2024022010/forcing_input/2024022013
#export COASTAL_FORCING_INPUT_DIR=/contrib/Zhengtao.Cui/home/nextgen/sfincs_met/atmo/forcing_input
export COASTAL_FORCING_INPUT_DIR=/contrib/Zhengtao.Cui/home/nextgen/sfincs_met/atmo/forcing_input_20230401
export LENGTH_HRS=-3
export FORCING_BEGIN_DATE=202402201000
export FORCING_END_DATE=202402201300
export NWM_FORCING_OUTPUT_DIR=/lustre/Zhengtao.Cui/test/tmp/nwm_analysis_assim_coastal_hawaii_13_v3.0/analysis_assim_coastal_hawaii_2024022010/forcing_input
export COASTAL_FORCING_OUTPUT_DIR=/lustre/Zhengtao.Cui/test/tmp/nwm_analysis_assim_coastal_hawaii_13_v3.0/coastal_forcing_output
export COASTAL_FORCING_OUTPUT_DIR=/lustre/Zhengtao.Cui/coastal_forcing_output
#export SCHISM_ESMFMESH=/lustre/Zhengtao.Cui/test/packages/nwm.v3.0.6/parm/coastal/hawaii/hgrid.nc
#export GEOGRID_FILE=/lustre/Zhengtao.Cui/test/packages/nwm.v3.0.6/parm/domain_hawaii/geo_em_HI.nc
export SCHISM_ESMFMESH=/lustre/Zhengtao.Cui/test/packages/nwm.v3.0.6/parm/coastal/atlgulf/hgrid.nc
export GEOGRID_FILE=/lustre/Zhengtao.Cui/test/packages/nwm.v3.0.6/parm/domain/geo_em_CONUS.nc

export COASTAL_WORK_DIR=/lustre/Zhengtao.Cui/sfincs_atmo
export FORCING_START_YEAR=2024
export FORCING_START_MONTH=02
export FORCING_START_DAY=20
export FORCING_START_HOUR=10

mkdir -p $COASTAL_WORK_DIR/sflux/

python -u .//makeAtmo.py 

