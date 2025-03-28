#!/bin/bash

NGENCERF_APP=/ngencerf-app

# ------------------------------------------------------------------------------
# Helper: Prompt user with a message, then open the file in an editor
# ------------------------------------------------------------------------------
edit_file_with_message() {
    local file="$1"
    local message="$2"

    echo
    echo "================================================================================"
    echo "$message"
    echo
    echo "When you're done, save and exit your editor (e.g., :wq in vim)."
    echo "================================================================================"
    echo

    read -p "Press ENTER to open $file..." _

    # Fallback chain: $EDITOR -> vim -> vi
    if [[ -n "$EDITOR" ]]; then
        "$EDITOR" "$file"
    elif command -v vim >/dev/null 2>&1; then
        vim "$file"
    else
        vi "$file"
    fi
}

# ------------------------------------------------------------------------------
# Prompt user to paste GitLab token
# ------------------------------------------------------------------------------
# edit_file_with_message "$NGENCERF_APP/.gitlab_token" "Paste your GitLab token into this file."

# Configure Git to use the token
# git config --global url."https://oauth2:$(cat /ngencerf-app/.gitlab_token)@gitlab.sh.nextgenwaterprediction.com/".insteadOf "https://gitlab.sh.nextgenwaterprediction.com/"

cd $NGENCERF_APP

# ------------------------------------------------------------------------------
# Clone Repositories
# ------------------------------------------------------------------------------
# echo "Cloning repos"
# echo
# git clone -b development https://gitlab.sh.nextgenwaterprediction.com/NGWPC/nwm-ngen/ngencerf_ui.git
# echo
# git clone -b development https://gitlab.sh.nextgenwaterprediction.com/NGWPC/nwm-ngen/ngencerf-server.git
# echo
# git clone -b development https://gitlab.sh.nextgenwaterprediction.com/NGWPC/nwm-ngen/ngencerf-docker.git
# echo
# git clone -b development --recurse-submodules https://gitlab.sh.nextgenwaterprediction.com/NGWPC/nwm-ngen/ngen.git
# echo
# git clone -b development https://gitlab.sh.nextgenwaterprediction.com/NGWPC/nwm-ngen/ngen-cal.git
# echo
# git clone -b development https://gitlab.sh.nextgenwaterprediction.com/NGWPC/nwm-ngen/ngen-forcing.git
# echo
# git clone -b development https://gitlab.sh.nextgenwaterprediction.com/NGWPC/nwm-ngen/ngen-fcst.git
# echo
# git clone -b development https://gitlab.sh.nextgenwaterprediction.com/NGWPC/nwm-ngen/ngen-pw-automation.git
# echo

# ------------------------------------------------------------------------------
# Pull/build Docker images and build Singularity containers
# ------------------------------------------------------------------------------
echo "Logging into Docker. Enter your AWS credentials if prompted..."
docker login registry.sh.nextgenwaterprediction.com

echo
echo "Building singularity containers..."
$NGENCERF_APP/ngen-pw-automation/build_singularity.sh --release-type=development all

# ------------------------------------------------------------------------------
# Build nginx singularity
# ------------------------------------------------------------------------------
echo
echo "Building nginx singularity container if it doesn't exist..."
if [[ ! -f "$NGENCERF_APP/singularity/nginx-unprivileged.sif" ]]; then
    cd $NGENCERF_APP
    git clone https://github.com/parallelworks/interactive_session.git
    cp interactive_session/downloads/jupyter/nginx-unprivileged.sif singularity/
    rm -rf interactive_session
else
    echo "nginx-unprivileged.sif already exists in $NGENCERF_APP/singularity/"
fi

# ------------------------------------------------------------------------------
# Configure ngencerf-server
# ------------------------------------------------------------------------------
cd ngencerf-server

# Only copy if override file doesn't exist
if [[ ! -f ngencerf_services.override.env ]]; then
    echo "Creating ngencerf_services.override.env from template..."
    cp ngencerf_services.env ngencerf_services.override.env
else
    echo "Override file already exists: ngencerf_services.override.env"
fi
echo

edit_file_with_message "ngencerf_services.override.env" \
    "Update the database host, password, and EDS URL in this file."

edit_file_with_message ".env" \
    "Update the NGEN_CAL_TAG and NGEN_FORCING_TAG values in this file."

# ------------------------------------------------------------------------------
# Prepare static data
# ------------------------------------------------------------------------------
echo "Preparing static data directory..."

STATIC_DIR="$NGENCERF_APP/data/ngen-cal-data/ngen-static-files"
SOURCE_DIR="$NGENCERF_APP/ngen-cal/module_parameter_files"

if [[ -d "$STATIC_DIR" ]]; then
    echo "Static data directory already exists at $STATIC_DIR"
    echo "Skipping module_parameter_files copy and S3 sync."
else
    echo "Creating static data directory..."
    sudo mkdir -p "$STATIC_DIR"
    sudo chown -R $(whoami):pwuser $NGENCERF_APP/data/ngen-cal-data
    sudo chmod -R g+rwx $NGENCERF_APP/data/ngen-cal-data

    if [[ ! -d "$STATIC_DIR/module_parameter_files" ]]; then
        echo "Copying module_parameter_files directory from ngen-cal repo..."
        cp --archive "$SOURCE_DIR" "$STATIC_DIR/"
    else
        echo "Skipping copy: module_parameter_files already exists in $STATIC_DIR"
    fi

    edit_file_with_message "/tmp/aws.credentials" \
      "Paste export statements for your AWS credentials in this file.  These are temporary credentials to copy the static files"

    source /tmp/aws.credentials

    echo
    echo "Copying data from NGWPC data bucket..."
    aws s3 sync s3://ngwpc-dev/ngen-static-files "$STATIC_DIR/"
fi
