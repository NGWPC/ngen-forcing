#!/usr/bin/env bash

export BINDINGS="/efs/coastal_testdata,/efs/ngwpc-coastal,/usr/bin/bc,/usr/bin/srun,/usr/lib64/libpmi2.so,/usr/lib64/libefa.so,/usr/lib64/libibmad.so,/usr/lib64/libibnetdisc.so,/usr/lib64/libibumad.so,/usr/lib64/libibverbs.so,/usr/lib64/libmana.so,/usr/lib64/libmlx4.so,/usr/lib64/libmlx5.so,/usr/lib64/librdmacm.so,/contrib/software"


repo=/ngen-app/ngen
 
export PYTHONPATH="${repo}:${PYTHONPATH}"

singularity exec -B $BINDINGS \
	  --pwd /ngen-app  \
        singularity/ngen_coastal_sing.sif \
	ls /ngen-app/ngen-python/bin/activate

singularity exec -B $BINDINGS \
	  --pwd /efs/coastal_testdata/Lower_Colorado_River_ngen  \
        singularity/ngen_coastal_sing.sif \
	/bin/bash -c "source /ngen-app/ngen-python/bin/activate; \
        /ngen-app/ngen/cmake_build/ngen ./domain/LowerColorado_v22_no_lakes.gpkg \"all\" \
	./domain/LowerColorado_v22_no_lakes.gpkg \"all\" ./Lower_Colorado_River_ngen.json"
	


