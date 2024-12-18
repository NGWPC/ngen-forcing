#PDY=20240206
#PDYm1=20240205
#PDYm2=20240204
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
    #echo "Date specified on cmd line... `date -d $INPUT_DATE "+%Y%m%d"`"
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

PDY=$UTC_DATE


#=========================================================
#  https://noaa-nos-ofs-pds.s3.amazonaws.com/leofs/netcdf/[YYYYMM]/
#  leofs - nowcast grid
#     leofs.t[00-18.3]z.[date].regulargrid.n[000..006].nc
#  leofs - forecast grid
#     leofs.t[00-18.3]z.[date].regulargrid.f[000..006].nc
#=========================================================
#for pdy in $PDYm1 $PDY; do
for pdy in $PDY; do
    for cyc in 00 06 12 18; do
     
      for domain in leofs lmhofs loofs lsofs; do

        OFSDIR=$OUTPUT_DIR/${domain}
        if [ ! -d "${OFSDIR}" ]; then 
            mkdir -p $OFSDIR
        fi
         
        cd $OFSDIR
     
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
      done
    done
done

