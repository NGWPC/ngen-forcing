#!/usr/bin/env bash
#

set -x
## User specific aliases and functions
## >>> conda initialize >>>
## !! Contents within this block are managed by 'conda init' !!
#__conda_setup="$('/opt/conda/bin/conda' 'shell.bash' 'hook' 2> /dev/null)"
#if [ $? -eq 0 ]; then
#    eval "$__conda_setup"
#else
#    if [ -f "/opt/conda/etc/profile.d/conda.sh" ]; then
#        . "/opt/conda/etc/profile.d/conda.sh"
#    else
#        export PATH="/opt/conda/bin:$PATH"
#    fi
#fi
#unset __conda_setup
## <<< conda initialize <<<
##
#
##conda activate ${CONDA_ENVS_PATH}/$CONDA_ENV_NAME
#conda activate $CONDA_ENV_NAME

source /contrib/software/py_venvs/ngen_python_3_10_14/bin/activate
source ./nexgen_preprocessing.bash
source ../calib/update_param.bash
source ../calib/regrid_stofs.bash
source ../calib/nwm_coastal.bash

nexgen_preprocessing  $COASTAL_PREPROCESSING_SCRIPT_DIR \
	$NGWPC_COASTAL_PARM_DIR/parm/coastal \
	$COASTAL_DOMAIN \
        $HRRRFILE \
	$COASTAL_WORK_DIR \
        $HRRRDIR          \
	"$START_TIME" \
	"$END_TIME"   \
	$TROUTE_PATH

nwm_coastal_update_params ${STARTPDY}${STARTCYC} $COASTAL_DOMAIN $FCST_LENGTH_HRS $HOT_START_FILE 

deactivate

# User specific aliases and functions
# >>> conda initialize >>>
# !! Contents within this block are managed by 'conda init' !!
__conda_setup="$('/contrib/software/miniconda/miniconda/bin/conda' 'shell.bash' 'hook' 2> /dev/null)"
if [ $? -eq 0 ]; then
    eval "$__conda_setup"
else
    if [ -f "/contrib/software/miniconda/miniconda/etc/profile.d/conda.sh" ]; then
        . "/contrib/software/miniconda/miniconda/etc/profile.d/conda.sh"
    else
        export PATH="/contrib/software/miniconda/miniconda/bin:$PATH"
    fi
fi
unset __conda_setup
# <<< conda initialize <<<

conda activate /contrib/software/miniconda/miniconda/envs/nwm

nwm_coastal_regrid_estofs ${STARTPDY}${STARTCYC} $FCST_LENGTH_HRS \
	$STOFS_FILE

conda deactivate
conda deactivate

nwm_coastal
