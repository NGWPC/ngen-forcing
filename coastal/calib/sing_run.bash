#!/usr/bin/env bash
#SBATCH --job-name=sing_schism  #job name
#SBATCH -N 1                     #number of nodes to use
#SBATCH --partition=compute      #the patition
#SBATCH --ntasks-per-node=18     #numebr of cores per node
#SBATCH --exclusive

export NODES=1          #this must match the number of nodes defined above by slurm
export NCORES=18
export NPROCS=$((NODES*NCORES))

set -x

#load the configuration file
. ./schism_calib.cfg

export NGEN_APP_DIR=/ngen-app
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

export NFS_MOUNT=/efs

#SIF_PATH=/ngencerf-app/singularity/ngen-coastal.sif
SIF_PATH=/contrib/Zhengtao.Cui/home/ngwpc/singularity/ngen_coastal_sing.sif

export MPICOMMAND2="mpiexec -n ${NPROCS} "

export NSCRIBES=2

export BINDINGS="$NFS_MOUNT,$DOMAIN_PATH,/usr/bin/bc,/usr/bin/srun,/usr/lib64/libpmi2.so,/usr/lib64/libefa.so,/usr/lib64/libibmad.so,/usr/lib64/libibnetdisc.so,/usr/lib64/libibumad.so,/usr/lib64/libibverbs.so,/usr/lib64/libmana.so,/usr/lib64/libmlx4.so,/usr/lib64/libmlx5.so,/usr/lib64/librdmacm.so"

work_dir=${NGEN_APP_DIR}/ngen-forcing/coastal/calib

singularity exec -B $BINDINGS \
	  --pwd ${work_dir} \
         $SIF_PATH \
	 ./run_sing_coastal_workflow_pre_schism2.bash


export PATH=/opt/amazon/openmpi/bin:/opt/amazon/efa/bin:/usr/local/bin:/usr/bin:/usr/local/sbin:/usr/sbin

export LD_LIBRARY_PATH=/opt/amazon/openmpi/lib:/opt/amazon/openmpi/lib64
export OMPI_ALLOW_RUN_AS_ROOT=1
export OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1

date

${MPICOMMAND2} singularity exec -B $BINDINGS --pwd $COASTAL_WORK_DIR \
         $SIF_PATH \
	/bin/bash -c "/ngen-app/nwm.v3.0.6/exec/pschism_wcoss2_NO_PARMETIS_TVD-VL.openmpi $NSCRIBES"


singularity exec -B $BINDINGS \
	  --pwd ${work_dir} \
         $SIF_PATH \
	 ./run_sing_coastal_workflow_post_schism.bash
date

