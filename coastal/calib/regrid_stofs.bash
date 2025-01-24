#!/usr/bin/bash

set -x

#--------------------------------------------------------------
#This task regrids ESTOFS forecasts to the coastal domain, and fills in water level forecasts as needed for the
#cycle length, using pytides.
#
#If $REGRIDDED_ESTOFS_FILE is populated, the task just copies this file to the output file, which is:
#
#   $DATAexec/elev2D.th.nc
#
#If $COASTAL_ESTOFS_FILE is populated, the task regrids this file:
#
#Otherwise, it looks in $$COMINestofs/estofs.YYYYMMDD for the closest file within 6 hours.
#
#If no ESTOFS file can be found, the task fails.
#
nwm_coastal_regrid_estofs() {
   #
   # regrid_estofs needs gcc not intel
   #
#   module switch intel/${intel_ver} gcc/${gcc_ver}

#   start_date=${FORCING_BEGIN_DATE:0:8}
#   start_hour=${FORCING_START_HOUR}
   
   PDY=${1:0:8}
   cyc=${1:8}
   export LENGTH_HRS=$2
   export COASTAL_ESTOFS_FILE=$3

   start_date=${PDY}
   start_hour=${cyc}
   #estofs_data=$DATAexec/estofs.t${start_hour}z.fields.cwl.nc
   estofs_data=$DATAexec/stofs_2d_glo.t${start_hour}z.fields.cwl.nc
   output_file=$DATAexec/elev2D.th.nc

   if [[ "$REGRIDDED_ESTOFS_FILE" != "" ]]; then
       cp $REGRIDDED_ESTOFS_FILE $output_file
   else
       if [[ "$COASTAL_ESTOFS_FILE" != "" ]]; then
           ln -sf $COASTAL_ESTOFS_FILE $estofs_data
           diffhrs=0

       #	
       #no mapping for extend AnA,  Long AnA, or medium range
       #
       elif [[ "${LENGTH_HRS}" -lt -6 || "${CASETYPE}" =~ "medium_range_" ]]; then
          diffhrs=6
          estofs_file=$COMINestofs/stofs_2d_glo.${start_date:0:8}/stofs_2d_glo.t${start_hour}z.fields.cwl.nc
          ln -sf $estofs_file $estofs_data
       else
           estofs_file=""
           best=""

#           # look back up to 2 days
#           # for the closest ESTOFS file
#           # expects estofs.YYYYMMDD/estofs.tHHz.fields.cwl.nc
#           for d in 0 1
#           do
#               dt=`date -u -d "${start_date} -$d days" +%Y%m%d`
#               dir=$COMINestofs/estofs.$dt
#               if [[ ! -d $dir ]]; then
#                   continue
#               fi
#   
#               for f in `cd $dir; ls -1`
#               do
#                   if [[ $f == *.fields.cwl.nc ]]; then
#                       tm=`echo $f | gawk 'match($0, /t([0-9][0-9])z/, arr) { print arr[1]}'`
#                       if [[ $tm == "" || ( $tm -gt $start_hour && $dt == "${start_date}" ) ]]; then
#                           continue
#                       fi
#                       if [[ $best == "" ]]; then
#                           best=$tm
#                       fi
#                       if [[ $best -le $tm ]]; then
#                           best=$tm
#                           estofs_file="$dir/$f"
#                       fi
#                   fi
#               done
#
#               if [[ $estofs_file != "" ]]; then
#                   break
#               fi
#           done
#
#           # see if it's more than 6 hours old
#           if [[ $estofs_file != "" ]]; then
#             t1=`date -u -d "${start_date} $start_hour" +%s`
#             t2=`date -u -d "$dt $best" +%s`
#             diff=$((t1-t2))
#             diffhrs=$((diff/3600))
##             if [ $diffhrs -gt 6 ]; then
##               estofs_file=""
##             fi
#           fi

           diffhrs=0
           if [ ${cyc} -lt "06" ]; then
              estofs_file=$COMINestofs/stofs_2d_glo.${PDYm1}/stofs_2d_glo.t18z.fields.cwl.nc
              t1=`date -u -d "${PDY} ${cyc}" +%s`
              t2=`date -u -d "${PDYm1} 18" +%s`
              diff=$((t1-t2))
              diffhrs=$((diff/3600))
           elif [ ${cyc} -ge "06" ] && [ ${cyc} -lt "12" ]; then
              estofs_file=$COMINestofs/stofs_2d_glo.${PDY}/stofs_2d_glo.t00z.fields.cwl.nc
              t1=`date -u -d "${PDY} ${cyc}" +%s`
              t2=`date -u -d "${PDY} 00" +%s`
              diff=$((t1-t2))
              diffhrs=$((diff/3600))
           elif [ ${cyc} -ge "12" ] && [ ${cyc} -lt "18" ]; then
              estofs_file=$COMINestofs/stofs_2d_glo.${PDY}/stofs_2d_glo.t06z.fields.cwl.nc
              t1=`date -u -d "${PDY} ${cyc}" +%s`
              t2=`date -u -d "${PDY} 06" +%s`
              diff=$((t1-t2))
              diffhrs=$((diff/3600))
           else
              estofs_file=$COMINestofs/stofs_2d_glo.${PDY}/stofs_2d_glo.t12z.fields.cwl.nc
              t1=`date -u -d "${PDY} ${cyc}" +%s`
              t2=`date -u -d "${PDY} 12" +%s`
              diff=$((t1-t2))
              diffhrs=$((diff/3600))
           fi

           ln -sf $estofs_file $estofs_data
       fi

#       $USHnwm/utils/waitFile.sh ${estofs_file} $waitTime
#
#       if [[ ! -f ${estofs_file} ]]; then
#	    err_exit "ESTOFS ${estofs_file} file doesn't exist." 
#       fi
       #cpfs $estofs_file $estofs_data

       hgrid_file=$DATAexec/open_bnds_hgrid.nc
       ln -sf ${PARMnwm}/coastal/$COASTAL_DOMAIN/open_bnds_hgrid.nc $hgrid_file
       #cpfs ${PARMnwm}/coastal/$COASTAL_DOMAIN/open_bnds_hgrid.nc $hgrid_file

       export ESTOFS_INPUT_FILE=$estofs_data
       export OPEN_BNDS_HGRID_FILE=$hgrid_file
       export SCHISM_OUTPUT_FILE=$output_file

       export CYCLE_DATE=$start_date
       #export CYCLE_TIME=$start_time
       export CYCLE_TIME=$cyc'00'
       local _old_length_hrs=${LENGTH_HRS}
       export LENGTH_HRS=$(( ${LENGTH_HRS/#-} + 1 )) 

       #${MPICOMMAND2} python $USHnwm/wrf_hydro_workflow_dev/coastal/regrid_estofs.py $ESTOFS_INPUT_FILE $OPEN_BNDS_HGRID_FILE $SCHISM_OUTPUT_FILE  >> $DATAlogs/regrid_stofs.${PDY}${cyc}.log 2>&1
       ${MPICOMMAND3} python $USHnwm/wrf_hydro_workflow_dev/coastal/regrid_estofs.py $ESTOFS_INPUT_FILE $OPEN_BNDS_HGRID_FILE $SCHISM_OUTPUT_FILE  >> $DATAlogs/regrid_stofs.${PDY}${cyc}.log 2>&1

       export LENGTH_HRS=${_old_length_hrs}

       # if we are Medium-Range, use PyTides to fill in the water levels for hours 181-241
       if [ ${LENGTH_HRS} -gt $((180-$diffhrs)) ]; then
           old_length_hrs=$LENGTH_HRS
           export LENGTH_HRS=$(($LENGTH_HRS+$diffhrs))
           export TIDAL_CONSTANTS_DIR=$COASTAL_ROOT_DIR/Tides/TidalConst
           export COASTAL_DOMAIN_GR3=$PARMnwm/coastal/$COASTAL_DOMAIN/hgrid.gr3

           python $USHnwm/wrf_hydro_workflow_dev/coastal/Tides/makeOceanTide.py >> $DATAlogs/regrid_stofs.{PDY}${cyc}.log 2>&1
           export LENGTH_HRS=${old_length_hrs}

       fi

       local _correction_file=$DATAexec/elevation_correction.csv
       if [[ -f  ${_correction_file} ]]; then
           echo "Applying elevation datum correction to elev2D.th.nc file"
           ${MPICOMMAND3} python $USHnwm/wrf_hydro_workflow_dev/coastal/correct_elevation.py \
		   $SCHISM_OUTPUT_FILE \
		    ${_correction_file} >> $DATAlogs/regrid_stofs.${PDY}${cyc}.log 2>&1
       fi

   fi
   #
   #switch back to intel
#   module switch gcc/${gcc_ver} intel/${intel_ver} 
}

