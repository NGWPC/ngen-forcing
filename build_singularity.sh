#!/bin/bash

# exit on failed command
set -e

# exit on failed pipeline
set -o pipefail

# create log file with timestamp
LOGFILE="./build_$(date --iso-8601=seconds).log"

# redirect stdout and stderr to tee, which will:
# 1. write output to the log file
# 2. print it to the terminal
exec > >(tee -i "$LOGFILE") 2>&1

# available repos
REPOS=("ngen" "ngen-cal" "ngen-bmi-forcing" "ngen-lumped-forcing" "ngen-fcst" "ngen-verf")

# prompt for build type selection
echo "Select build type:"
echo "1) development"
echo "2) release-candidate"
echo "3) official release"
read -p "Enter number [1-3]: " release_choice

case $release_choice in
    1) RELEASE_TYPE="development" ;;
    2) RELEASE_TYPE="release-candidate" ;;
    3) RELEASE_TYPE="official release" ;;
    *) 
        echo "Invalid choice, exiting."
        exit 1
        ;;
esac

echo "Release type selected: $RELEASE_TYPE"

# prompt user to select which repos they want to build
echo "Available repos: ${REPOS[@]}"
read -p "Enter repos to build (space-separated from the list above): " -a SELECTED_REPOS

# define base path where SIF files and symlinks are located
BASE_PATH="/ngencerf-app/singularity"

# define Docker registry base path
REGISTRY="registry.sh.nextgenwaterprediction.com/ngwpc/nwm-ngen"

# 'development'
if [[ "$RELEASE_TYPE" == "development" ]]; then

    cd "$BASE_PATH"

    # remove old symlinks if they exist for the selected repos
    for repo in "${SELECTED_REPOS[@]}"; do
        echo "Removing old symlink for $repo..."
        rm -f "${repo}.sif"
    done

    # iterate over each selected repo and process them
    for repo in "${SELECTED_REPOS[@]}"; do
        # forcing repos have a different registry path
        if [[ "$repo" == "ngen-bmi-forcing" || "$repo" == "ngen-lumped-forcing" ]]; then
            IMAGE="${REGISTRY}/ngen-forcing/${repo}:latest"
        else
            IMAGE="${REGISTRY}/${repo}:latest"
        fi

        # define sif file name with timestamp
        SIF_FILE="${repo}.sif_$(date --iso-8601=seconds)"
        
        # pull the Docker image
        echo "Pulling docker image: $IMAGE"
        docker pull "$IMAGE"

        # build Singularity container from Docker image
        echo "Building SIF: $SIF_FILE"
        singularity build "${BASE_PATH}/${SIF_FILE}" "docker-daemon://${IMAGE}"

        # create symlink to point to new sif file
        echo "Creating symlink: ${repo}.sif -> ${SIF_FILE}"
        ln -s "$SIF_FILE" "${repo}.sif"

        echo "$repo done!"
    done

    echo "All selected builds completed successfully!"

else
    echo "Release type '$RELEASE_TYPE' is not implemented yet."
    exit 0
fi
