#!/usr/bin/env bash

if [[ -z $ROOT_SHARE ]]; then
    ROOT_SHARE_TXT="ERROR: ROOT_SHARE variable not set!"
else
    ROOT_SHARE_TXT="ROOT_SHARE set to: $ROOT_SHARE"
fi

usage() { echo -e "Usage: $0 [-d <utcdate>(yyyymmdd)] [-o <output path>]\n\tdefaults: \n\t\t<utcdate>: current utc day\n\t\t<output path>: \$ROOT_SHARE/data)" 1>&2; exit 1; }

options=$(getopt -o d:o:h --long utcdate:,output:,help -- "$@")
eval set -- "$options"

while :; do
    case "$1" in
        -d|--utcdate)
            shift
            INPUT_DATE=$1
            echo "got option: $INPUT_DATE"
            ;;
        -o|--output)
            shift
            OPTION_DIR=$1
            echo "got option: $OPTION_DIR"
            ;;
        -h|--help)
            usage
            exit
            ;;
        --)
            shift
            break
            ;;
    esac

    shift
done

if [[ -z $INPUT_DATE ]]; then
    UTC_DATE=`date "+%Y%m%d"`
else
    echo "Date specified on cmd line... `date -d $INPUT_DATE "+%Y%m%d"`"
    UTC_DATE=`date -d $INPUT_DATE "+%Y%m%d"`
fi
if [[ -z $OPTION_DIR ]]; then
    echo -e $ROOT_SHARE_TXT
    if [[ -z $ROOT_SHARE ]]; then
        exit 1
    fi
    OUTPUT_DIR="$ROOT_SHARE/data"
else
    OUTPUT_DIR="$OPTION_DIR"
fi

pdy=$UTC_DATE


#=========================================================
#  https://noaa-nos-ofs-pds.s3.amazonaws.com/${domain}/netcdf/[YYYYMM]/
#  nowcast grid
#     ${domain}.t[00-18.6]z.[date].regulargrid.n[000..006].nc
#  nowcast field
#     ${domain}.t[00-18.6]z.[date].fields.n[000..006].nc
#  nowcast station
#     ${domain}.t[00-18.6]z.[date].stations.nowcast.nc
#  forecast grid
#     ${domain}.t[00-18.6]z.[date].regulargrid.f[000..006].nc
#  forecast field
#     ${domain}.t[00-18.6]z.[date].fields.f[000..006].nc
#  forecast station
#     ${domain}.t[00-18.6]z.[date].stations.forecast.nc
#=========================================================
# pre 202403 files
# nocast field
#   nos.{domain}.fields.n[000..006].[date].t[00-18.6]z.nc
# nocast stations
#   nos.{domain}.stations.nowcast.[date].t[00-18.6]z.nc
# nocast grid
#   N/A
# forecast field
#   N/A
# forecast stations
#   N/A
# forecast grid
#   N/A
#=========================================================
# pre 202301 files
# nocast field
#   nos.{domain}.fields.n[000..006].[date].t[00-18.6]z.nc
# nocast stations
#   N/A
# nocast grid
#   N/A
# forecast field
#   N/A
# forecast stations
#   N/A
# forecast grid
#   N/A
#=========================================================

for domain in leofs lmhofs loofs lsofs; do
     
   OFSDIR=$OUTPUT_DIR/${domain}
   if [ ! -d "${OFSDIR}" ]; then 
        mkdir -p $OFSDIR
   fi
         
   cd $OFSDIR

   for cyc in 00 06 12 18; do
     #pre 202301
     if [ ${pdy} -lt 20230101 ]; then
        for i in {000..006}; do 
            wget -nc --no-check-certificate \
	        https://noaa-nos-ofs-pds.s3.amazonaws.com/${domain}/netcdf/${pdy:0:-2}/nos.${domain}.fields.n${i}.${pdy}.t${cyc}z.nc
        done
     
     #pre 202403
     elif [ ${pdy} -lt 20240301 ]; then
        for i in {000..006}; do 
            wget -nc --no-check-certificate \
	        https://noaa-nos-ofs-pds.s3.amazonaws.com/${domain}/netcdf/${pdy:0:-2}/nos.${domain}.fields.n${i}.${pdy}.t${cyc}z.nc
        done
        wget -nc --no-check-certificate \
	        https://noaa-nos-ofs-pds.s3.amazonaws.com/${domain}/netcdf/${pdy:0:-2}/nos.${domain}.stations.nowcast.${pdy}.t${cyc}z.nc
     else
	#nowcast station
        wget -nc --no-check-certificate \
	        https://noaa-nos-ofs-pds.s3.amazonaws.com/${domain}/netcdf/${pdy:0:-2}/${domain}.t${cyc}z.${pdy}.stations.nowcast.nc
	#nowcast regulargrid and grid
        for i in {000..006}; do 
            wget -nc --no-check-certificate \
	        https://noaa-nos-ofs-pds.s3.amazonaws.com/${domain}/netcdf/${pdy:0:-2}/${domain}.t${cyc}z.${pdy}.regulargrid.n${i}.nc
            wget -nc --no-check-certificate \
	        https://noaa-nos-ofs-pds.s3.amazonaws.com/${domain}/netcdf/${pdy:0:-2}/${domain}.t${cyc}z.${pdy}.fields.n${i}.nc

        done

	#forecast station
        wget -nc --no-check-certificate \
	        https://noaa-nos-ofs-pds.s3.amazonaws.com/${domain}/netcdf/${pdy:0:-2}/${domain}.t${cyc}z.${pdy}.stations.forecast.nc
	#forecast regulargrid and grid
        for i in {000..120}; do 
            wget -nc --no-check-certificate \
	        https://noaa-nos-ofs-pds.s3.amazonaws.com/${domain}/netcdf/${pdy:0:-2}/${domain}.t${cyc}z.${pdy}.regulargrid.f${i}.nc
            wget -nc --no-check-certificate \
	        https://noaa-nos-ofs-pds.s3.amazonaws.com/${domain}/netcdf/${pdy:0:-2}/${domain}.t${cyc}z.${pdy}.fields.f${i}.nc
        done
     fi
   done

   cd -

done

