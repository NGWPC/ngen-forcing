#!/usr/bin/env bash

#SBATCH --job-name=sing_mpi  #job name
#SBATCH -N 4                     #number of nodes to use
#SBATCH --partition=compute      #the patition
#SBATCH --ntasks-per-node=18     #numebr of cores per node
#SBATCH --exclusive 

set -x

export NODES=4          #this must match the number of nodes defined above by slurm
export NCORES=18        #this must match the number of cores per node defined above by slurm
export NPROCS=$((NODES*NCORES))
#
# define the start time of the calibration
# in the format of YYYYMMDD
export STARTPDY=20240219
#
# define the start hour of the calibration
export STARTCYC=00
# define the forecast length in hours of the calibration
export FCST_LENGTH_HRS=12
#
# location of the hot restart file for SCHISM. For cold start, set the value to ''.
export HOT_START_FILE=/efs/ngwpc-coastal/restart_coastal/hotstart_analysis_assim_coastal_atlgulf_ana_20240220_1000.nc

#
# location of the archived STOFS file if STOFS data is 
# going to be used for the boundary nodes
#export STOFS_FILE=/efs/schism_use_case/stofs_20240913/stofs_2d_glo.t00z.fields.cwl.nc
export STOFS_FILE=/contrib/Zhengtao.Cui/home/ngwpc/lfs/h1/ops/prod/com/stofs/v1.1/stofs_20240219/stofs_2d_glo.t00z.fields.cwl.nc

#
# location of the NWM retrospective or archieved forcing files
# note that the time span of the files must cover the whole simulation period
export NWM_FORCING_DIR=/contrib/Zhengtao.Cui/home/ngwpc/nwmv3_oe_install/test/tmp/pacific_nwm_ana_forcing
export HRRRDIR=/contrib/Zhengtao.Cui/home/ngwpc/hrrr_20240219/conus
export HRRRFILE=$HRRRDIR/hrrr.20240219/hrrr.t00z.wrfsfcf00.grib2
#
# location of the NWM retrospective or archieved streamflow files
# note that the time span of the files must cover the whole simulation period
export NWM_CHROUT_DIR=/contrib/Zhengtao.Cui/home/ngwpc/nwmv3_oe_install/test/tmp/pacific_nwm_ana_chout
#the name of the NWM domain to calibrate, one of hawaii, prvi, pacific or atlgulf
#export COASTAL_DOMAIN=prvi
export COASTAL_DOMAIN=atlgulf
#
export TROUTE_PATH=/contrib/Zhengtao.Cui/home/ngwpc/t-route/test/LowerColorado_TX_HYFeatures_v22/output_schism_test

#define working directory of the SCHISM calibration run
export COASTAL_WORK_DIR=/efs/coastal_testdata/atl_nwm_ana_nexgen_20240219
##################################################################################################
# End of user defined section
##################################################################################################

#set the Singularity image file
SIF_PATH="singularity/ngen_coastal_sing.sif"

export NGWPC_COASTAL_PARM_DIR=/efs/ngwpc-coastal

#export NGEN_APP_DIR=/ngen-app
export NGEN_APP_DIR=/contrib/software/nwmv3_oe_install/test/packages

#
# define the model time step in seconds
export FCST_TIMESTEP_LENGTH_SECS=3600
#

export USHnwm=$NGEN_APP_DIR/nwm.v3.0.6/ush
export PARMnwm=$NGWPC_COASTAL_PARM_DIR/parm
export EXECnwm=$NGEN_APP_DIR/nwm.v3.0.6/exec
export DATAexec=$COASTAL_WORK_DIR

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

## User specific aliases and functions
## >>> conda initialize >>>
## !! Contents within this block are managed by 'conda init' !!
#__conda_setup="$('/opt/conda/bin/conda' 'shell.bash' 'hook' 2> /dev/null)"
#if [ $? -eq 0 ]; then
#    eval "$__conda_setup"
#else
#    if [ -f "/opt/conda/etc/profile.d/conda.sh" ]; then
#        . "/opt/conda/etc/profile.d/conda.sh"
#    else
#        export PATH="/opt/conda/bin:$PATH"
#    fi
#fi
##unset __conda_setup
## <<< conda initialize <<<
##

export NFS_MOUNT=/efs
#export PATH=/opt/conda/bin:${PATH}
#export CONDA_ENVS_PATH=$NFS_MOUNT/ngen-app/conda/envs
#export CONDA_ENV_NAME=ngen_forcing_coastal
#export PATH=${CONDA_ENVS_PATH}/${CONDA_ENV_NAME}/bin:${PATH}

#conda activate ${CONDA_ENVS_PATH}/$CONDA_ENV_NAME

export PATH=/contrib/software/python_3_10_14/bin:${PATH}
export LD_LIBRARY_PATH=/contrib/software/python_3_10_14/lib:/contrib/software/netcdf/4.7.4/lib:/contrib/software/hdf5/1.12.3/lib:/opt/conda/lib:${CONDA_ENVS_PATH}/lib:$LD_LIBRARY_PATH

export MPICOMMAND2="mpiexec -n ${NPROCS} "
export MPICOMMAND3="mpiexec -n 4 "

declare -A coastal_domain_to_inland_domain=( \
	   [prvi]="domain_puertorico" \
	   [hawaii]="domain_hawaii" \
	   [atlgulf]="domain" \
	   [pacific]="domain" )

declare -A coastal_domain_to_geo_grid=( \
	   [prvi]="geo_em_PRVI.nc" \
	   [hawaii]="geo_em_HI.nc" \
	   [atlgulf]="geo_em_CONUS.nc" \
	   [pacific]="geo_em_CONUS.nc" )

export SCHISM_ESMFMESH=${PARMnwm}/coastal/${COASTAL_DOMAIN}/hgrid.nc
export GEOGRID_FILE=${PARMnwm}/${coastal_domain_to_inland_domain[$COASTAL_DOMAIN]}/${coastal_domain_to_geo_grid[$COASTAL_DOMAIN]}

export DATAlogs=$DATAexec

if [[ ! -d $DATAexec ]]; then
   mkdir -p $DATAexec
fi

export NSCRIBES=2

export BINDINGS="/contrib,$NFS_MOUNT,$CONDA_ENVS_PATH,$NGWPC_COASTAL_PARM_DIR,/usr/bin/bc,/usr/bin/srun,/usr/lib64/libpmi2.so,/usr/lib64/libefa.so,/usr/lib64/libibmad.so,/usr/lib64/libibnetdisc.so,/usr/lib64/libibumad.so,/usr/lib64/libibverbs.so,/usr/lib64/libmana.so,/usr/lib64/libmlx4.so,/usr/lib64/libmlx5.so,/usr/lib64/librdmacm.so"

#work_dir=${NGEN_APP_DIR}/ngen-forcing/coastal/forecast
work_dir=/contrib/Zhengtao.Cui/home/ngwpc/ngen-forcing/coastal/forecast
export COASTAL_PREPROCESSING_SCRIPT_DIR=$work_dir/../

#export WGRIB2=/contrib/software/nwmv3_oe_install/test/packages/grib2/wgrib2/wgrib2
export WGRIB2=${NGEN_APP_DIR}/grib2/wgrib2/wgrib2

#singularity exec -B $BINDINGS --pwd ${work_dir} $SIF_PATH \
#	 ./run_forecast_nexgen_preprocessing.bash


export LENGTH_HRS=$FCST_LENGTH_HRS
export FORCING_BEGIN_DATE=${STARTPDY}${STARTCYC}00
export START_TIME="${STARTPDY:0:4}-${STARTPDY:4:2}-${STARTPDY:6} ${STARTCYC}:00:00"

start_timestamp=$(date -u -d "${STARTPDY} ${STARTCYC}" +"%s")
itime=$(( 10#${LENGTH_HRS} * 3600 + $start_timestamp ))
export FORCING_END_DATE=$(date -u -d "@${itime}" +"%Y%m%d%H00")
export END_TIME="$(date -u -d "@${itime}" +"%Y-%m-%d %H:00:00")"

cd ${work_dir}
./run_forecast_nexgen_preprocessing.bash
