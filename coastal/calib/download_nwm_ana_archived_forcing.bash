#!/usr/bin/env bash

set -x
pdy_begin=$1
pdy_end=$2
domain=$3

declare -A domain_to_foldername=( \
	   [puertorico]="forcing_analysis_assim_puertorico" \
	   [hawaii]="forcing_analysis_assim_hawaii" \
	   [atlgulf]="forcing_analysis_assim" \
	   [pacific]="forcing_analysis_assim" )
declare -A domain_to_postfix=( \
	   [puertorico]="puertorico" \
	   [hawaii]="hawaii" \
	   [atlgulf]="conus" \
	   [pacific]="conus" )

start_pdy=$(date -u -d "${pdy_begin} 00" +"%s")
end_pdy=$(date -u -d "${pdy_end} 23" +"%s")


while [ $start_pdy -le $end_pdy ]; do
  
 pdy=$(date -u -d "@${start_pdy}" +"%Y%m%d")
 cyc=$(date -u -d "@${start_pdy}" +"%H")
 itime=$(( $start_pdy + 2 * 3600))
 pdycyc=$(date -u -d "@${itime}" +"%Y%m%d%H")
 pdyout=$(date -u -d "@${itime}" +"%Y%m%d")
 cycout=$(date -u -d "@${itime}" +"%H")
 pdycyc_out=$(date -u -d "@${start_pdy}" +"%Y%m%d%H")
 gsutil -m cp  \
	    "gs://national-water-model/nwm.${pdyout}/${domain_to_foldername[$domain]}/nwm.t${cycout}z.analysis_assim.forcing.tm02.${domain_to_postfix[$domain]}.nc" ./${pdycyc_out}.LDASIN_DOMAIN1
 ((start_pdy+=3600))
done
