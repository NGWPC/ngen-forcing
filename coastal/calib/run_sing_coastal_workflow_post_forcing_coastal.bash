#!/usr/bin/env bash
#

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

source ./post_nwm_forcing_coastal.bash


post_nwm_forcing_coastal ${STARTPDY}${STARTCYC} \
	$DATAexec/coastal_forcing_output \
	$FCST_LENGTH_HRS \
        $NWM_FORCING_DIR




