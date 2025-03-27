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
edit_file_with_message "$NGENCERF_APP/.gitlab_token" "Paste your GitLab token into this file."

# Configure Git to use the token
git config --global url."https://oauth2:$(cat /ngencerf-app/.gitlab_token)@gitlab.sh.nextgenwaterprediction.com/".insteadOf "https://gitlab.sh.nextgenwaterprediction.com/"

cd $NGENCERF_APP

# ------------------------------------------------------------------------------
# Clone Repositories
# ------------------------------------------------------------------------------
echo "Cloning repos"
echo
git clone -b development https://gitlab.sh.nextgenwaterprediction.com/NGWPC/nwm-ngen/ngencerf_ui.git
echo
git clone -b development https://gitlab.sh.nextgenwaterprediction.com/NGWPC/nwm-ngen/ngencerf-server.git
echo
git clone -b development https://gitlab.sh.nextgenwaterprediction.com/NGWPC/nwm-ngen/ngencerf-docker.git
echo
git clone -b development --recurse-submodules https://gitlab.sh.nextgenwaterprediction.com/NGWPC/nwm-ngen/ngen.git
echo
git clone -b development https://gitlab.sh.nextgenwaterprediction.com/NGWPC/nwm-ngen/ngen-cal.git
echo
git clone -b development https://gitlab.sh.nextgenwaterprediction.com/NGWPC/nwm-ngen/ngen-forcing.git
echo
git clone -b development https://gitlab.sh.nextgenwaterprediction.com/NGWPC/nwm-ngen/ngen-fcst.git
echo
git clone -b development https://gitlab.sh.nextgenwaterprediction.com/NGWPC/nwm-ngen/ngen-pw-automation.git
echo

# ------------------------------------------------------------------------------
# Docker login and pull images
# ------------------------------------------------------------------------------
echo "Logging into Docker. Enter your AWS credentials if prompted..."
docker login registry.sh.nextgenwaterprediction.com

echo
echo "Pulling docker images..."

echo
docker pull registry.sh.nextgenwaterprediction.com/ngwpc/nwm-ngen/ngen:latest
echo
docker pull registry.sh.nextgenwaterprediction.com/ngwpc/nwm-ngen/ngen-cal:latest
echo
docker pull registry.sh.nextgenwaterprediction.com/ngwpc/nwm-ngen/ngen-forcing/ngen-bmi-forcing:latest
echo
docker pull registry.sh.nextgenwaterprediction.com/ngwpc/nwm-ngen/ngen-forcing/ngen-lumped-forcing:latest
echo
docker pull registry.sh.nextgenwaterprediction.com/ngwpc/nwm-ngen/ngen-fcst:latest
echo
docker pull registry.sh.nextgenwaterprediction.com/ngwpc/nwm-ngen/ngen-verf:latest

# ------------------------------------------------------------------------------
# Build Singularity images
# ------------------------------------------------------------------------------
echo
echo "Building singularities..."
$NGENCERF_APP/ngen-pw-automation/build_singularity.sh --release-type=development all

# ------------------------------------------------------------------------------
# Build nginx singularity
# ------------------------------------------------------------------------------
echo
echo "Building nginx singularity..."

cd $NGENCERF_APP
git clone https://github.com/parallelworks/interactive_session.git
cp interactive_session/downloads/jupyter/nginx-unprivileged.sif singularity/
rm -rf interactive_session

# ------------------------------------------------------------------------------
# Configure ngencerf-server
# ------------------------------------------------------------------------------
cd ngencerf-server
cp ngencerf-services.env ngencerf-services.override.env
echo

edit_file_with_message "ngencerf-services.override.env" \
  "Update the database host, password, and EDS URL in this file."

edit_file_with_message ".env" \
  "Update the NGEN_CAL_TAG and NGEN_FORCING_TAG values in this file."

# ------------------------------------------------------------------------------
# Prepare static data
# ------------------------------------------------------------------------------
echo "Preparing static data directory..."

sudo mkdir -p /ngencerf-app/data/ngen-cal-data/ngen-static-files
sudo chown -R $(whoami):pwuser /ngencerf-app/data/ngen-cal-data
sudo chmod -R g+rwx /ngencerf-app/data/ngen-cal-data

echo

echo "Copying module_parameter_files directory from the ngen-cal repo..."
cp --archive /ngencerf-app/ngen-cal/module_parameter_files /ngencerf-app/data/ngen-cal-data/ngen-static-files/

# ------------------------------------------------------------------------------
# AWS Credentials + Static File Sync
# ------------------------------------------------------------------------------
edit_file_with_message "/tmp/aws.credentials" \
  "Paste export statements for your AWS credentials in this file."

source /tmp/aws.credentials

echo
echo "Copying data from NGWPC data bucket..."
aws s3 sync s3://ngwpc-dev/ngen-static-files /ngencerf-app/data/ngen-cal-data/ngen-static-files/.

