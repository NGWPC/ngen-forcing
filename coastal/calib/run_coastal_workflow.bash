#!/usr/bin/env bash
#
###########################################################################
# Start of user defined section
###########################################################################
#SBATCH --job-name=test_sr_prvi  #job name
#SBATCH -N 2                     #number of nodes to use
#SBATCH --partition=compute      #the patition
#SBATCH --ntasks-per-node=18     #numebr of cores per node
#SBATCH --exclusive 

export NODES=2          #this must match the number of nodes defined above by slurm
export NCORES=18        #this must match the number of cores per node defined above by slurm
export NPROCS=$((NODES*NCORES))
#
# define the start time of the calibration
# in the format of YYYYMMDD
export STARTPDY=20230101
#
# define the start hour of the calibration
export STARTCYC=00
# define the forecast length in hours of the calibration
export FCST_LENGTH_HRS=12
#
# define the model time step in seconds
export FCST_TIMESTEP_LENGTH_SECS=3600

#
# location of the hot restart file for SCHISM
export HOT_START_FILE=/contrib/Zhengtao.Cui/home/ngwpc/nwmv3_oe_install/test/com/nwm/v3.0/nwm.20240220/restart_coastal/hotstart_analysis_assim_coastal_prvi_20240220_1800.nc

#
# location of the archived STOFS file if STOFS data is 
# going to be used for the boundary nodes
export STOFS_FILE=/contrib/Zhengtao.Cui/home/ngwpc/lfs/h1/ops/prod/com/stofs/v1.1/estofs_20230101/estofs.t00z.fields.cwl.nc

#
# location of the NWM retrospective forcing files
# note that the time span of the files must cover the whole simulation period
export NWM_FORCING_DIR=/contrib/Zhengtao.Cui/home/ngwpc/nwmv3_oe_install/test/tmp/pr_nwm_forcing_retro
#
# location of the NWM retrospective streamflow files
# note that the time span of the files must cover the whole simulation period
export NWM_CHROUT_DIR=/contrib/Zhengtao.Cui/home/ngwpc/nwmv3_oe_install/test/tmp/pr_nwm_chout_retro
#
# Whether or not to use TPXO forecast instead of STOFS data
# "YES" or "NO"
export USE_TPXO="NO"
#
# location of the OTPSnc program and TPXO10_atlas model data
# the OTPSnc program can be downloaded from https://www.tpxo.net/otps
# the TPXO10_atlas data is available on the AWS s3 bucket 
# s3://ngwpc-data/Coastal_and_atmospheric_forcing_for_calibration/TPXO_atlas/TPXO10_atlas_v2_nc.zip
# The zip file must be unpacked and extracted folders are put inside the OTPSnc directory
export OTPSDIR=/contrib/software/OTPSnc
#
#the name of the NWM domain to calibrate
export COASTAL_DOMAIN=prvi
#
#define the NWM v3 installation directory
export NWM_V3_INSTALL_DIR=/contrib/software/nwmv3_oe_install
#
#define working directory of the SCHISM calibration run
export COASTAL_WORK_DIR=/contrib/Zhengtao.Cui/home/ngwpc/nwmv3_oe_install/test/tmp/retro_test_stofs
##################################################################################################
# End of user defined section
##################################################################################################

export USHnwm=$NWM_V3_INSTALL_DIR/test/packages/nwm.v3.0.6/ush
export PARMnwm=$NWM_V3_INSTALL_DIR/test/packages/nwm.v3.0.6/parm
export EXECnwm=$NWM_V3_INSTALL_DIR/test/packages/nwm.v3.0.6/exec
export DATAexec=$COASTAL_WORK_DIR

source ./nwm_forcing_coastal.bash
source ./update_param.bash
source ./regrid_stofs.bash
source ./initial_discharge.bash
source ./combine_sink_source.bash
source ./merge_source_sink.bash
source ./nwm_coastal.bash
source ./make_tpxo_ocean.bash

export SAVE_ALL_TASKS=yes
export OMP_NUM_THREADS=2
export IOBUF_PARAMS='*.LAKEOUT_DOMAIN1:size=64M:count=2:prefetch=1,*:size=32M:count=4:vbuffer_count=4096:prefetch=1'
#export IOBUF_PARAMS='*:verbose'
export OMP_PLACES=cores
# ----------------: added (WCOSS2/Pete)
# set up MPI connections and buffers at start of run - helps efficiency of MPI later in run
export MPICH_OFI_STARTUP_CONNECT=1
# pace MPI_Bcast messaging when reading and distributing initial conditions - prevents the Bcast hangs
export MPICH_COLL_SYNC=MPI_Bcast
# turn off MPI_Reduce on node optimization - prevent MPI_Reduce hangs during time stepping
export MPICH_REDUCE_NO_SMP=1

export FI_OFI_RXM_SAR_LIMIT=3145728
export FI_MR_CACHE_MAX_COUNT=0
export FI_EFA_RECVWIN_SIZE=65536

# User specific aliases and functions
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

conda activate /contrib/software/miniconda/miniconda/envs/nwm

#export PATH=$PATH:${OE_DIR}/test/packages/prod_util.v2.0.14/ush
export PATH=/contrib/software/gcc/8.5.0/bin:/contrib/software/netcdf/4.7.4/bin:/contrib/software/hdf5/1.12.3/bin:$PATH
export WGRIB2=${OE_DIR}/test/packages/grib2/wgrib2/wgrib2
export LD_LIBRARY_PATH=/contrib/software/gcc/8.5.0/lib64:/contrib/software/netcdf/4.7.4/lib:/contrib/software/hdf5/1.12.3/lib:/contrib/software/miniconda/miniconda/lib:$LD_LIBRARY_PATH

export MPICOMMAND2="mpiexec -n ${NPROCS} "
export MPICOMMAND3="mpiexec -n 1 "

declare -A coastal_domain_to_inland_domain=( \
	   [prvi]="domain_puertorico" \
	   [hawaii]="domain_hawaii" \
	   [atlgulf]="domain" \
	   [pacific]="domain" )

export SCHISM_ESMFMESH=${PARMnwm}/coastal/${COASTAL_DOMAIN}/hgrid.nc
export GEOGRID_FILE=${PARMnwm}/${coastal_domain_to_inland_domain[$COASTAL_DOMAIN]}/geo_em_PRVI.nc
export DATAlogs=$DATAexec

if [[ ! -d $DATAexec ]]; then
   mkdir -p $DATAexec
fi

nwm_forcing_coastal ${STARTPDY}${STARTCYC} \
	$DATAexec/coastal_forcing_output \
	$FCST_LENGTH_HRS \
        $NWM_FORCING_DIR


export RESTART_WRITE_HR=2

nwm_coastal_update_params ${STARTPDY}${STARTCYC} $COASTAL_DOMAIN $FCST_LENGTH_HRS $HOT_START_FILE 

if [[ $USE_TPXO == "YES" ]]; then
   ngen_forcing_dir=$(pwd)/../../
   make_tpxo_ocean ${STARTPDY}${STARTCYC} $FCST_LENGTH_HRS \
	$OTPSDIR \
	$ngen_forcing_dir\
	$PARMnwm/coastal \
	$COASTAL_DOMAIN  \
	$FCST_TIMESTEP_LENGTH_SECS

else
   nwm_coastal_regrid_estofs ${STARTPDY}${STARTCYC} $FCST_LENGTH_HRS \
	$STOFS_FILE
fi

export NWM_CYCLE=forecast
export WRF_HYDRO_ROOT=$DATAexec/nwm_output

nwm_coastal_initial_discharge ${STARTPDY}${STARTCYC} $FCST_LENGTH_HRS $COASTAL_DOMAIN $NWM_CHROUT_DIR

nwm_coastal_combine_sink_source

export COASTAL_ROOT_DIR=$DATAexec

nwm_coastal_merge_source_sink "" "forecast" "forecast"

export NSCRIBES=2

nwm_coastal
