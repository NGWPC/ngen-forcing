#!/usr/bin/env bash

export BINDINGS="/efs/coastal_testdata,/efs/ngwpc-coastal,/usr/bin/bc,/usr/bin/srun,/usr/lib64/libpmi2.so,/usr/lib64/libefa.so,/usr/lib64/libibmad.so,/usr/lib64/libibnetdisc.so,/usr/lib64/libibumad.so,/usr/lib64/libibverbs.so,/usr/lib64/libmana.so,/usr/lib64/libmlx4.so,/usr/lib64/libmlx5.so,/usr/lib64/librdmacm.so,/contrib/software"


repo=/ngen-app/ngen-forcing
 
export PYTHONPATH="${repo}:${PYTHONPATH}"

singularity exec -B $BINDINGS \
	  --pwd /ngen-app  \
        singularity/ngen_coastal_sing.sif \
	ls /efs/ngwpc-coastal/

singularity exec -B $BINDINGS \
	  --pwd /ngen-app  \
        singularity/ngen_coastal_sing.sif \
	 conda run -n ngen_forcings_engine_bmi --no-capture-output \
    python "${repo}/NextGen_Forcings_Engine_BMI/run_bmi_model.py" \
    -config_path /efs/ngwpc-coastal/Lower_Colorado_River/sr_config.yml \
    -geogrid /efs/ngwpc-coastal/Lower_Colorado_River//esmf_mesh/LowerColorado_v22_no_lakes_mesh.nc \
    -b_date 202402191100 \
    "2024-02-19 11:00:00" "2024-02-20 00:00:00"

singularity exec -B $BINDINGS \
	  --pwd /ngen-app  \
        singularity/ngen_coastal_sing.sif \
conda run -n ngen_forcings_engine_bmi --no-capture-output \
    python "${repo}/NextGen_Forcings_Engine_BMI/post_process/netcdf_to_csv.py" \
     "/efs/coastal_testdata/hrrr_scratch/NextGen_Forcings_Engine_HYDROFABRIC_output_202402191100.nc" \
     /efs/coastal_testdata/csv_dir/output_202402190000



