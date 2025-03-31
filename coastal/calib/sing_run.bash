#!/usr/bin/env bash

#SBATCH --job-name=sing_mpi  #job name
#SBATCH -N 2                     #number of nodes to use
#SBATCH --partition=compute      #the patition
#SBATCH --ntasks-per-node=18     #numebr of cores per node
#SBATCH --exclusive 
##SBATCH --chdir=/contrib/Zhengtao.Cui/home/ngwpc/nwmv3_oe_install/test/tmp/hi_nwm_ana_arch_test_stofs

set -x

export NODES=2          #this must match the number of nodes defined above by slurm
export NCORES=18        #this must match the number of cores per node defined above by slurm
export NPROCS=$((NODES*NCORES))
#
# define the start time of the calibration
# in the format of YYYYMMDD
#export STARTPDY=20240220
export STARTPDY=20230101
#
# define the start hour of the calibration
#export STARTCYC=10
export STARTCYC=00
# define the forecast length in hours of the calibration
export FCST_LENGTH_HRS=12
#
# location of the hot restart file for SCHISM
#export HOT_START_FILE=/contrib/Zhengtao.Cui/home/ngwpc/nwmv3_oe_install/test/com/nwm/v3.0/nwm.20240220/restart_coastal/hotstart_analysis_assim_coastal_prvi_20240220_1800.nc
export HOT_START_FILE=/contrib/Zhengtao.Cui/home/ngwpc/nwmv3_oe_install/test/com/nwm/v3.0/nwm.20240220/restart_coastal/hotstart_analysis_assim_coastal_hawaii_ana_20240220_1000.nc

#
# location of the archived STOFS file if STOFS data is 
# going to be used for the boundary nodes
#export STOFS_FILE=/contrib/Zhengtao.Cui/home/ngwpc/lfs/h1/ops/prod/com/stofs/v1.1/stofs_2d_glo.20240220/stofs_2d_glo.t06z.fields.cwl.nc
export STOFS_FILE=/contrib/Zhengtao.Cui/home/ngwpc/lfs/h1/ops/prod/com/stofs/v1.1/estofs_20230101/estofs.t00z.fields.cwl.nc

#
# location of the NWM retrospective or archieved forcing files
# note that the time span of the files must cover the whole simulation period
#export NWM_FORCING_DIR=/contrib/Zhengtao.Cui/home/ngwpc/nwmv3_oe_install/test/tmp/pr_nwm_forcing_retro
#export NWM_FORCING_DIR=/contrib/Zhengtao.Cui/home/ngwpc/nwmv3_oe_install/test/tmp/pr_nwm_ana_forcing
#export NWM_FORCING_DIR=/contrib/Zhengtao.Cui/home/ngwpc/nwmv3_oe_install/test/tmp/hi_nwm_ana_forcing_20240220
export NWM_FORCING_DIR=/contrib/Zhengtao.Cui/home/ngwpc/nwmv3_oe_install/test/tmp/hi_nwm_ana_forcing
#
# location of the NWM retrospective or archieved streamflow files
# note that the time span of the files must cover the whole simulation period
#export NWM_CHROUT_DIR=/contrib/Zhengtao.Cui/home/ngwpc/nwmv3_oe_install/test/tmp/pr_nwm_chout_retro
#export NWM_CHROUT_DIR=/contrib/Zhengtao.Cui/home/ngwpc/nwmv3_oe_install/test/tmp/pr_nwm_ana_chout
#export NWM_CHROUT_DIR=/contrib/Zhengtao.Cui/home/ngwpc/nwmv3_oe_install/test/tmp/hi_nwm_ana_chout_20240220
export NWM_CHROUT_DIR=/contrib/Zhengtao.Cui/home/ngwpc/nwmv3_oe_install/test/tmp/hi_nwm_ana_chout
#
# Whether or not to use TPXO forecast instead of STOFS data
# "YES" or "NO"
export USE_TPXO="NO"
#
#the name of the NWM domain to calibrate
#export COASTAL_DOMAIN=prvi
export COASTAL_DOMAIN=hawaii
#
#define working directory of the SCHISM calibration run
#export COASTAL_WORK_DIR=/contrib/Zhengtao.Cui/home/ngwpc/nwmv3_oe_install/test/tmp/hi_nwm_ana_arch_test_stofs_20240220_tpxo
export COASTAL_WORK_DIR=/contrib/Zhengtao.Cui/home/ngwpc/nwmv3_oe_install/test/tmp/hi_nwm_ana_arch_test_stofs_sing
##################################################################################################
# End of user defined section
##################################################################################################

#set the Singularity image file
SIF_PATH="singularity/ngen_coastal_sing.sif_2025-02-19T01:38:32+00:00"

export NGWPC_COASTAL_PARM_DIR=/efs/ngwpc-coastal

export NGEN_APP_DIR=/ngen-app
#
# define the model time step in seconds
export FCST_TIMESTEP_LENGTH_SECS=3600
#
# location of the OTPSnc program and TPXO10_atlas model data
# the OTPSnc program can be downloaded from https://www.tpxo.net/otps
# the TPXO10_atlas data is available on the AWS s3 bucket 
# s3://ngwpc-data/Coastal_and_atmospheric_forcing_for_calibration/TPXO_atlas/TPXO10_atlas_v2_nc.zip
# The zip file must be unpacked and extracted folders are put inside the OTPSnc directory
export OTPSDIR=$NGEN_APP_DIR/OTPSnc

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

# User specific aliases and functions
# >>> conda initialize >>>
# !! Contents within this block are managed by 'conda init' !!
__conda_setup="$('/opt/conda/bin/conda' 'shell.bash' 'hook' 2> /dev/null)"
if [ $? -eq 0 ]; then
    eval "$__conda_setup"
else
    if [ -f "/opt/conda/etc/profile.d/conda.sh" ]; then
        . "/opt/conda/etc/profile.d/conda.sh"
    else
        export PATH="/opt/conda/bin:$PATH"
    fi
fi
unset __conda_setup
# <<< conda initialize <<<
#

export PATH=/opt/conda/bin:${PATH}
export CONDA_ENVS_PATH=/efs/ngen-app/conda/envs/
export PATH=${CONDA_ENV_PATH}/bin:${PATH}
export CONDA_ENV_NAME=ngen_forcing_coastal

conda activate $CONDA_ENV_NAME

export LD_LIBRARY_PATH=/opt/conda/lib:${CONDA_ENV_PATH}/lib:$LD_LIBRARY_PATH

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

export NSCRIBES=2

export BINDINGS="$CONDA_ENVS_PATH,$NGWPC_COASTAL_PARM_DIR,/usr/bin/bc,/usr/bin/srun,/usr/lib64/libpmi2.so,/usr/lib64/libefa.so,/usr/lib64/libibmad.so,/usr/lib64/libibnetdisc.so,/usr/lib64/libibumad.so,/usr/lib64/libibverbs.so,/usr/lib64/libmana.so,/usr/lib64/libmlx4.so,/usr/lib64/libmlx5.so,/usr/lib64/librdmacm.so"

work_dir=/contrib/Zhengtao.Cui/home/ngwpc/ngen-forcing/coastal/calib

singularity exec -B $BINDINGS --pwd ${work_dir} $SIF_PATH \
	 ./run_sing_coastal_workflow_pre_forcing_coastal.bash


export LENGTH_HRS=$FCST_LENGTH_HRS
export FORCING_BEGIN_DATE=${STARTPDY}${STARTCYC}00

start_timestamp=$(date -u -d "${STARTPDY} ${STARTCYC}" +"%s")
itime=$(( 10#${LENGTH_HRS} * 3600 + $start_timestamp ))
export FORCING_END_DATE=$(date -u -d "@${itime}" +"%Y%m%d%H00")

export NWM_FORCING_OUTPUT_DIR=$DATAexec/forcing_input
export COASTAL_FORCING_OUTPUT_DIR=$DATAexec/coastal_forcing_output

export FECPP_JOB_INDEX=0
export FECPP_JOB_COUNT=1

${MPICOMMAND3} singularity exec -B $BINDINGS \
	  --pwd ${work_dir} \
         $SIF_PATH \
	 $CONDA_ENVS_PATH/$CONDA_ENV_NAME/bin/python \
         $USHnwm/wrf_hydro_workflow_dev/forcings/WrfHydroFECPP/workflow_driver.py 

singularity exec -B $BINDINGS \
	  --pwd ${work_dir} \
         $SIF_PATH \
	 ./run_sing_coastal_workflow_post_forcing_coastal.bash

singularity exec -B $BINDINGS \
	  --pwd ${work_dir} \
         $SIF_PATH \
	 ./run_sing_coastal_workflow_update_params.bash

if [[ $USE_TPXO == "YES" ]]; then
   singularity exec -B $BINDINGS \
	  --pwd ${work_dir} \
         $SIF_PATH \
	 ./run_sing_coastal_workflow_make_tpxo_ocean.bash
else
   export CYCLE_DATE=$STARTPDY
   export CYCLE_TIME=${STARTCYC}00
   export LENGTH_HRS=$(singularity exec -B $BINDINGS \
	  --pwd ${work_dir} \
         $SIF_PATH \
	 ./run_sing_coastal_workflow_pre_make_stofs_ocean.bash)

   export ESTOFS_INPUT_FILE=$STOFS_FILE
   export SCHISM_OUTPUT_FILE=$DATAexec/elev2D.th.nc
   export OPEN_BNDS_HGRID_FILE=$DATAexec/open_bnds_hgrid.nc

   ${MPICOMMAND3} singularity exec -B $BINDINGS \
	  --pwd ${work_dir} \
         $SIF_PATH \
	 $CONDA_ENVS_PATH/$CONDA_ENV_NAME/bin/python \
         $USHnwm/wrf_hydro_workflow_dev/coastal/regrid_estofs.py $ESTOFS_INPUT_FILE $OPEN_BNDS_HGRID_FILE $SCHISM_OUTPUT_FILE 

   singularity exec -B $BINDINGS \
	  --pwd ${work_dir} \
         $SIF_PATH \
	 ./run_sing_coastal_workflow_post_make_stofs_ocean.bash

fi

singularity exec -B $BINDINGS \
	  --pwd ${work_dir} \
         $SIF_PATH \
	 ./run_sing_coastal_workflow_pre_schism.bash


export PATH=/opt/amazon/openmpi/bin:/opt/amazon/efa/bin:/usr/local/bin:/usr/bin:/usr/local/sbin:/usr/sbin

export LD_LIBRARY_PATH=/opt/amazon/openmpi/lib:/opt/amazon/openmpi/lib64
export OMPI_ALLOW_RUN_AS_ROOT=1
export OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1

${MPICOMMAND2} singularity exec -B $BINDINGS --pwd $COASTAL_WORK_DIR \
         $SIF_PATH \
	/bin/bash -c "/ngen-app/nwm.v3.0.6/exec/pschism_wcoss2_NO_PARMETIS_TVD-VL.openmpi $NSCRIBES"


singularity exec -B $BINDINGS \
	  --pwd ${work_dir} \
         $SIF_PATH \
	 ./run_sing_coastal_workflow_post_schism.bash


