#!/usr/bin/env bash

set -x
pdy_begin=$1
pdy_end=$2


start_pdy=$(date -u -d "${pdy_begin} 00" +"%s")
end_pdy=$(date -u -d "${pdy_end} 23" +"%s")

while [ $start_pdy -le $end_pdy ]; do
  
  pdy=$(date -u -d "@${start_pdy}" +"%Y%m%d")
  cyc=$(date -u -d "@${start_pdy}" +"%H")
  if [ $pdy -lt "20230108" ]; then
    if [[ ! -d "./estofs_${pdy}" ]]; then
      mkdir ./estofs_${pdy}
    fi
    wget -P ./estofs_${pdy} https://noaa-gestofs-pds.s3.amazonaws.com/estofs.${pdy}/estofs.t${cyc}z.fields.cwl.nc 
  else
    if [[ ! -d "./stofs_${pdy}" ]]; then
      mkdir ./stofs_${pdy}
    fi
    wget -P ./stofs_${pdy} https://noaa-gestofs-pds.s3.amazonaws.com/stofs_2d_glo.${pdy}/stofs_2d_glo.t${cyc}z.fields.cwl.nc
  fi

  ((start_pdy+=3600*6))
done
