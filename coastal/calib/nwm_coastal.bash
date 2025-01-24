#!/usr/bin/env bash

set -x

#--------------------------------------------------------------
#
#This task runs SCHISM on the prepared coastal inputs, combines output and restarts, and writes output to:
#
#   $DATAexec/outputs
#
nwm_coastal() {

   if [[ ! -d $DATAexec/outputs ]]; then
       mkdir -p $DATAexec/outputs
   fi
   cd $DATAexec

   #create offline partition
   create_offline_partition $NPROCS "${NSCRIBES}"
   #cpfs ${EXECnwm}/pschism_wcoss2_NO_PARMETIS_TVD-VL .
   #cpfs ${EXECnwm}/pschism_mistral_NOPM_VL .
   cp ${EXECnwm}/pschism_wcoss2_NO_PARMETIS_TVD-VL_intel .

   OLD_PATH=$PATH
   OLD_LD_LIBRARY_PATH=$LD_LIBRARY_PATH

   #export PATH=/contrib/software/intel_studio_x2_2020_u2_cluster_ed/impi/2019.9.304/intel64/bin:/contrib/software/intel_studio_x2_2020_u2_cluster_ed/compilers_and_libraries/linux/mpi/intel64/bin:/contrib/software/intel_studio_x2_2020_u2_cluster_ed/bin:$PATH
   #export DIR=/contrib/software/intel_19_1_3_304_opt
   #export LD_LIBRARY_PATH=/contrib/software/intel_studio_x2_2020_u2_cluster_ed/impi/2019.9.304/intel64/lib:/contrib/software/intel_studio_x2_2020_u2_cluster_ed/compilers_and_libraries/linux/mpi/intel64/lib:/contrib/software/intel_studio_x2_2020_u2_cluster_ed/lib:/contrib/software/intel_studio_x2_2020_u2_cluster_ed/compilers_and_libraries_2020.4.304/linux/compiler/lib/intel64_lin:$DIR/netcdf/lib:$DIR/zlib_1.3.1/lib:$DIR/hdf5_1.12.3/lib:$DIR/libcurl_8.5.0/lib

   export PATH=/contrib/software/intel_19_1_3_304_opt/impi/2019.9.304/intel64/bin:/contrib/software/intel_19_1_3_304_opt/compilers_and_libraries/linux/mpi/intel64/bin:/contrib/software/intel_19_1_3_304_opt/bin:$PATH
   export DIR=/contrib/Zhengtao.Cui/home/ngwpc/contrib/software/intel_19_1_3_304_opt
   export LD_LIBRARY_PATH=/contrib/software/intel_19_1_3_304_opt/impi/2019.9.304/intel64/lib:/contrib/software/intel_19_1_3_304_opt/compilers_and_libraries/linux/mpi/intel64/lib:/contrib/software/intel_19_1_3_304_opt/lib:/contrib/software/intel_19_1_3_304_opt/compilers_and_libraries_2020.4.304/linux/compiler/lib/intel64_lin:$DIR/netcdf/lib:$DIR/zlib_1.3.1/lib:$DIR/hdf5_1.12.3/lib:$DIR/libcurl_8.5.0/lib

   #${MPICOMMAND2} ./pschism_wcoss2_NO_PARMETIS_TVD-VL ${NSCRIBES} >> $pgmout 2>&1
   #${MPICOMMAND2} ./pschism_mistral_NOPM_VL ${NSCRIBES} >> $pgmout 2>&1
   ${MPICOMMAND2} ./pschism_wcoss2_NO_PARMETIS_TVD-VL_intel ${NSCRIBES} >> nwm_coastal.log 2>&1

   export PATH=$OLD_PATH
   export LD_LIBRARY_PATH=$OLD_LD_LIBRARY_PATH


   #${MPICOMMAND2} ./pschism_wcoss2_NO_PARMETIS_TVD-VL ${NSCRIBES} >> $pgmout 2>&1
   #cpfs ${EXECnwm}/pschism_wcoss2_NO_PARMETIS_OLDIO_TVD-VL .
   #${MPICOMMAND2} ./pschism_wcoss2_NO_PARMETIS_OLDIO_TVD-VL >> $pgmout 2>&1

   #cpfs ${EXECnwm}/pschism_wcoss2_TVD-VL .
   #${MPICOMMAND2} ./pschism_wcoss2_TVD-VL ${NSCRIBES} >> $pgmout 2>&1

   # if outputs/fatal.error size > 0, mark our status as failed
   # TODO: use ecFlow to return a more useful error
   if [ -s outputs/fatal.error ]; then
      echo "pschism_wcoss2_NO_PARMETIS_TVD-VL program failed. See $DATAexec/outputs/fatal.error file for more detail."
      exit 1
   fi

   cd ./outputs
   # combine hotstarts for analysis, or if running a chained renalysis
   if [[ $LENGTH_HRS -lt 0 || "$CHAINED_REANALYSIS" != "" ]]; then
       # create the hotstart for the next AnA run
       let hotstart_it=18*${RESTART_WRITE_HR/#-}
       cp ${EXECnwm}/combine_hotstart7 ./
       ./combine_hotstart7 -i ${hotstart_it} 

#       #ana_hotstart_time=$($NDATE $(($LENGTH_HRS + $RESTART_WRITE_HR)) $PDY$cyc)'00'
#       ana_hotstart_time=$(${USHnwm}/utils/advance_time.sh $PDY$cyc $(($LENGTH_HRS + $RESTART_WRITE_HR)))'00'
#       cpfs "hotstart_it=${hotstart_it}.nc" hotstart_${CASETYPE}_ana_${ana_hotstart_time:0:8}_${ana_hotstart_time:8:12}'.nc'
#       # create the hotstart for the forecast runs
#       let hotstart_it=18*${LENGTH_HRS/#-}
#       ./combine_hotstart7 -i  ${hotstart_it}
#       cpfs "hotstart_it=${hotstart_it}.nc" hotstart_${CASETYPE}_${PDY}_${cyc}'00.nc'
#       #rm hotstart_0*.nc

   fi
   # remove traps so below cleanup doesn't error out if the
   # files don't exist
   trap 0

   # clean up unneeded output
#   rm -f local_to_global*
#   rm -f global_to_local.prop
#   rm -f maxdahv_*
#   rm -f maxelev_*
#   rm -f nonfatal_*
   cd ../
}

#--------------------------------------------------------------
#
# Create offline partition file for a given number of processors
#  and domain
function create_offline_partition() {
  local num_procs=$1
  local scribes=$2

  cp ${EXECnwm}/metis_prep ./
  cp ${EXECnwm}/gpmetis ./
  ./metis_prep ./hgrid.gr3 ./vgrid.in
  ./gpmetis ./graphinfo $((${num_procs} - ${scribes})) -ufactor=1.01 -seed=15
  awk '{print NR,$0}' graphinfo.part.$((${num_procs} - ${scribes})) > partition.prop
}

