#!/bin/bash

set -e
set -o pipefail

# --- BASE DIRECTORY SETUP ---
# BASE_PATH is the root for all NGEN build assets, including repos and Singularity output
BASE_PATH="/ngencerf-app"
SINGULARITY_DIR="${BASE_PATH}/singularity"

# Redirect stdout and stderr to a log file in the Singularity directory
LOGFILE="${SINGULARITY_DIR}/build_$(date --iso-8601=seconds).log"
exec > >(tee -i "$LOGFILE") 2>&1

REPOS=("ngen" "ngen-cal" "ngen-bmi-forcing" "ngen-lumped-forcing" "ngen-fcst" "ngen-verf")

echo "Select build type:"
echo "1) development"
echo "2) release-candidate"
echo "3) official release"
read -p "Enter number [1-3]: " release_choice

case $release_choice in
    1) RELEASE_TYPE="development" ;;
    2) RELEASE_TYPE="release-candidate" ;;
    3) RELEASE_TYPE="official release" ;;
    *) echo "Invalid choice, exiting."; exit 1 ;;
esac

echo "Release type selected: $RELEASE_TYPE"

echo "Available repos: ${REPOS[*]}"
read -p "Enter repos to build (space-separated from the list above): " -a SELECTED_REPOS

REGISTRY="registry.sh.nextgenwaterprediction.com/ngwpc/nwm-ngen"

# prompt for tags if 'official release' or 'release-candidate'
declare -A TAGS
if [[ "$RELEASE_TYPE" == "official release" || "$RELEASE_TYPE" == "release-candidate" ]]; then
    for repo in "${SELECTED_REPOS[@]}"; do
        case $repo in
            ngen)
                read -p "Enter NGEN_TAG: " TAGS[ngen]
                ;;
            ngen-cal)
                read -p "Enter NGEN_CAL_TAG: " TAGS[ngen-cal]
                ;;
            ngen-bmi-forcing | ngen-lumped-forcing)
                read -p "Enter NGEN_FORCING_TAG (shared for both forcing repos): " TAGS[forcing]
                ;;
            ngen-fcst)
                read -p "Enter NGEN_FCST_TAG: " TAGS[ngen-fcst]
                ;;
            ngen-verf)
                read -p "Enter NGEN_VERF_TAG: " TAGS[ngen-verf]
                read -p "Enter NGEN_EVAL_TAG: " TAGS[ngen-eval]
                ;;
        esac
    done
fi

# function to update symlinks after building SIFs
update_symlinks() {
    local release_type="$1"
    local repo="$2"
    local image="$3"

    # Directory where SIFs and symlinks are stored
    local sif_dir="${SINGULARITY_DIR}"

    # The actual .sif filename with a timestamp
    local sif_file="${repo}.sif_$(date --iso-8601=seconds)"

    # The symlink name (e.g., ngen-cal.sif)
    local symlink_name="${repo}.sif"

    echo "Removing old symlink for $repo..."
    rm -f "${sif_dir}/${symlink_name}"

    echo "Building SIF: ${sif_file} from ${image}"
    singularity build "${sif_dir}/${sif_file}" "docker-daemon://${image}"

    # Why we use a relative symlink:
    # -----------------------------------------
    # Absolute symlinks (e.g., /ngencerf-app/singularity/file.sif) may break
    # inside a container if the container does not see the same full path.
    #
    # Relative symlinks (e.g., file.sif -> file.sif_2025-03-25...) are resilient
    # because they are interpreted relative to the symlink’s own location.
    # This makes them portable and ensures they work inside both the host and
    # container — as long as the base directory structure is preserved.
    #
    # We `cd` into the target directory before creating the symlink so the relative
    # path resolves correctly from the symlink’s point of view.
    echo "Creating relative symlink: ${symlink_name} -> ${sif_file}"
    (
        cd "$sif_dir"
        ln -s "${sif_file}" "${symlink_name}"
    )
}

# --- OFFICIAL RELEASE WORKFLOW ---
if [[ "$RELEASE_TYPE" == "official release" ]]; then
    cd "$BASE_PATH"

    # build order: ngen -> others
    if [[ " ${SELECTED_REPOS[@]} " =~ " ngen " ]]; then
        echo "Processing ngen..."
        docker pull "${REGISTRY}/ngen/ngen:master-test"
        docker tag "${REGISTRY}/ngen/ngen:master-test" "${REGISTRY}/ngen/ngen:${TAGS[ngen]}"
    fi

    for repo in "${SELECTED_REPOS[@]}"; do
        if [[ "$repo" == "ngen-cal" ]]; then
            echo "Building ngen-cal..."
            GITLAB_TOKEN=$(cat "${BASE_PATH}/.gitlab_token")
            docker build \
                --progress=plain \
                --no-cache \
                --secret id=GITLAB_TOKEN,env=GITLAB_TOKEN \
                --build-arg IMAGE_TAG="${TAGS[ngen]}" \
                --tag="${REGISTRY}/ngen-cal:${TAGS[ngen-cal]}" \
                "${BASE_PATH}/ngen-cal"
        elif [[ "$repo" == "ngen-bmi-forcing" ]]; then
            echo "Pulling ngen-bmi-forcing..."
            docker pull "${REGISTRY}/ngen-forcing/ngen-bmi-forcing:${TAGS[forcing]}"
        elif [[ "$repo" == "ngen-lumped-forcing" ]]; then
            echo "Pulling ngen-lumped-forcing..."
            docker pull "${REGISTRY}/ngen-forcing/ngen-lumped-forcing:${TAGS[forcing]}"
        elif [[ "$repo" == "ngen-fcst" ]]; then
            echo "Building ngen-fcst..."
            GITLAB_TOKEN=$(cat "${BASE_PATH}/.gitlab_token")
            docker build \
                --progress=plain \
                --no-cache \
                --secret id=GITLAB_TOKEN,env=GITLAB_TOKEN \
                --build-arg NGEN_VERSION="${TAGS[ngen]}" \
                --tag="${REGISTRY}/ngen-fcst:${TAGS[ngen-fcst]}" \
                "${BASE_PATH}/ngen-fcst"
        elif [[ "$repo" == "ngen-verf" ]]; then
            echo "Building ngen-verf..."
            GITLAB_TOKEN=$(cat "${BASE_PATH}/.gitlab_token")
            docker build \
                --progress=plain \
                --no-cache \
                --secret id=GITLAB_TOKEN,env=GITLAB_TOKEN \
                --build-arg NGEN_EVAL_TAG="${TAGS[ngen-eval]}" \
                --tag="${REGISTRY}/ngen-verf:${TAGS[ngen-verf]}" \
                "${BASE_PATH}/ngen-verf"
        fi
    done

    # run singularity build and update symlinks
    for repo in "${SELECTED_REPOS[@]}"; do
        if [[ "$repo" == "ngen-bmi-forcing" || "$repo" == "ngen-lumped-forcing" ]]; then
            IMAGE="${REGISTRY}/ngen-forcing/${repo}:${TAGS[forcing]}"
        else
            IMAGE="${REGISTRY}/${repo}:${TAGS[$repo]}"
        fi
        update_symlinks "$RELEASE_TYPE" "$repo" "$IMAGE"
    done

    echo "Official release completed successfully!"
    exit 0
fi

# ---- DEVELOPMENT WORKFLOW ----
if [[ "$RELEASE_TYPE" == "development" ]]; then
    cd "$BASE_PATH"

    for repo in "${SELECTED_REPOS[@]}"; do
        if [[ "$repo" == "ngen-bmi-forcing" || "$repo" == "ngen-lumped-forcing" ]]; then
            IMAGE="${REGISTRY}/ngen-forcing/${repo}:latest"
        else
            IMAGE="${REGISTRY}/${repo}:latest"
        fi

        echo "Pulling docker image: $IMAGE"
        docker pull "$IMAGE"
        update_symlinks "$RELEASE_TYPE" "$repo" "$IMAGE"
    done

    echo "Development build completed successfully!"
fi

