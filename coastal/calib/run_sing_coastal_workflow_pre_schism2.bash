#!/usr/bin/env bash
#

 cd $DATAexec
./gpmetis ./graphinfo $((${NPROCS} - ${NSCRIBES})) -ufactor=1.01 -seed=15
awk '{print NR,$0}' graphinfo.part.$((${NPROCS} - ${NSCRIBES})) > partition.prop
