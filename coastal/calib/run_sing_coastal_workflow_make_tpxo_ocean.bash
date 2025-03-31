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

source ./make_tpxo_ocean.bash

ngen_forcing_dir=$(pwd)/../../
make_tpxo_ocean ${STARTPDY}${STARTCYC} $FCST_LENGTH_HRS \
	$OTPSDIR \
	$ngen_forcing_dir\
	$PARMnwm/coastal \
	$COASTAL_DOMAIN  \
	$FCST_TIMESTEP_LENGTH_SECS



