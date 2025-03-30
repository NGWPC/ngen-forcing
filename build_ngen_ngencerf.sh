#!/bin/bash

set -e
set -o pipefail

# ==============================================================================
# NGEN/NGENCERF Build Script
# ==============================================================================
#
# This script builds and symlinks Singularity containers for selected NGEN repos.
# It supports both interactive use and non-interactive (automated) use via CLI.
#
# ------------------------------------------------------------------------------
# USAGE EXAMPLES
# ------------------------------------------------------------------------------
#
# Interactive mode (will prompt for build type and repos):
#   ./build_ngen_ngencerf.sh
#
# Development build (non-interactive, builds ngen and ngen-cal):
#   ./build_ngen_ngencerf.sh --build-type=development ngen ngen-cal
#
# Build all supported repos (non-interactive):
#   ./build_ngen_ngencerf.sh --build-type=development all
#
# Build for release (will still prompt for tags):
#   ./build_ngen_ngencerf.sh --build-type=release ngen ngen-cal ngen-verf
#   (will still prompt for tags)
#
# ------------------------------------------------------------------------------
# ARGUMENTS
# ------------------------------------------------------------------------------
#
#   --build-type=TYPE     One of: development, release
#   repo names              List of repos to build (space-separated), or use "all"
#
# Supported repos:
#   ngen, ngen-cal, ngen-bmi-forcing, ngen-lumped-forcing, ngen-fcst, ngen-verf
#
# Notes:
# - If no arguments are passed, the script runs interactively.
# - If "all" is passed as a repo, it expands to all supported repos.
# - For release, tag prompts will appear.
#
# ==============================================================================

# --- BASE DIRECTORY SETUP ---
# BASE_PATH is the root for all NGEN build assets, including repos and Singularity output
BASE_PATH="/ngencerf-app"
SINGULARITY_DIR="${BASE_PATH}/singularity"
mkdir -p $SINGULARITY_DIR

# Redirect stdout and stderr to a log file in the Singularity directory
LOGFILE="${SINGULARITY_DIR}/build_$(date -u +"%Y-%m-%dT%H:%M:%SZ").log"
exec > >(tee -i "$LOGFILE") 2>&1

REPOS=(
    "ngencerf_ui"
    "ngencerf-server"
    "ngencerf-docker"
    "ngen"
    "ngen-cal"
    "ngen-bmi-forcing"
    "ngen-lumped-forcing"
    "ngen-fcst"
    "ngen-verf"
)
REGISTRY="registry.sh.nextgenwaterprediction.com/ngwpc/nwm-ngen"

BUILD_TYPE=""
SELECTED_REPOS=()

# --- Parse command-line args ---
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --build-type=*)
                BUILD_TYPE="${1#*=}"
                ;;
            --build-type)
                shift
                BUILD_TYPE="$1"
                ;;
            -*)
                echo "Unknown option: $1"
                exit 1
                ;;
            *)
                SELECTED_REPOS+=("$1")
                ;;
        esac
        shift
    done
}

parse_args "$@"

# --- Prompt interactively if needed ---
if [[ -z "$BUILD_TYPE" && -t 0 ]]; then
    echo "Select build type:"
    echo "1) development"
    echo "2) release"
    read -p "Enter number [1-2]: " build_choice
    case $build_choice in
        1) BUILD_TYPE="development" ;;
        2) BUILD_TYPE="release" ;;
        *) echo "Invalid choice, exiting."; exit 1 ;;
    esac
fi

if [[ ${#SELECTED_REPOS[@]} -eq 0 && -t 0 ]]; then
    echo "Available repos: ${REPOS[*]}"
    read -p "Enter repos to build (space-separated from the list above): " -a SELECTED_REPOS
fi

if [[ -z "$BUILD_TYPE" || ${#SELECTED_REPOS[@]} -eq 0 ]]; then
    echo "Error: build type and at least one repo must be provided."
    exit 1
fi

echo "Build type selected: $BUILD_TYPE"
echo "Selected repos: ${SELECTED_REPOS[*]}"

# Handle 'all' keyword
if [[ " ${SELECTED_REPOS[*]} " =~ " all " ]]; then
    echo "'all' specified — building all available repos."
    SELECTED_REPOS=("${REPOS[@]}")
    echo "Repos to build: ${SELECTED_REPOS[*]}"
fi

# validate SELECTED_REPOS
INVALID_REPOS=()
for repo in "${SELECTED_REPOS[@]}"; do
    if [[ ! " ${REPOS[*]} " =~ " $repo " ]]; then
        INVALID_REPOS+=("$repo")
    fi
done

if [[ ${#INVALID_REPOS[@]} -gt 0 ]]; then
    echo "Error: Invalid repo(s): ${INVALID_REPOS[*]}"
    echo "Allowed repos are: ${REPOS[*]}"
    exit 1
fi

# prompt for tags if 'release'
declare -A TAGS
if [[ "$BUILD_TYPE" == "release" ]]; then
    for repo in "${SELECTED_REPOS[@]}"; do
        case $repo in
            ngencerf_ui)
                read -p "Enter ngencerf_ui tag: " TAGS[ngencerf_ui]
                ;;
            ngencerf-server)
                read -p "Enter ngencerf-server tag: " TAGS[ngencerf-server]
                ;;
            ngencerf-docker)
                read -p "Enter ngencerf-docker tag: " TAGS[ngencerf-docker]
                ;;
            ngen)
                read -p "Enter ngen tag: " TAGS[ngen]
                ;;
            ngen-cal)
                read -p "Enter ngen-cal tag: " TAGS[ngen-cal]
                ;;
            ngen-bmi-forcing | ngen-lumped-forcing)
                read -p "Enter ngen-forcing tag (shared for both forcing repos): " TAGS[forcing]
                ;;
            ngen-fcst)
                read -p "Enter ngen-fcst tag: " TAGS[ngen-fcst]
                ;;
            ngen-verf)
                read -p "Enter ngen-verf tag: " TAGS[ngen-verf]
                read -p "Enter ngen-eval tag: " TAGS[ngen-eval]
                ;;
        esac
    done
fi

# function to update symlinks after building SIFs
build_singularity_container_update_symlink() {
    local build_type="$1"
    local repo="$2"
    local image="$3"

    # Directory where SIFs and symlinks are stored
    local sif_dir="${SINGULARITY_DIR}"

    # The actual .sif filename with a timestamp
    # use 'latest' tag for development builds and provided tag for release builds
    if [[ "$build_type" == "development" ]]; then
        local sif_file="${repo}-latest-$(date -u +"%Y-%m-%dT%H:%M:%SZ").sif"
    
    else
        local sif_file="${repo}-${TAGS[$repo]}-$(date -u +"%Y-%m-%dT%H:%M:%SZ").sif"
    fi

    # The symlink name (e.g., ngen-cal.sif)
    local symlink_name="${repo}.sif"

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
        echo "Removing old ${symlink_name} symlink for $repo..."
        rm -f "${symlink_name}"

        echo "Building SIF: ${sif_file} from ${image}"
        singularity build "${sif_dir}/${sif_file}" "docker-daemon://${image}"
        ln -s "${sif_file}" "${symlink_name}"
    )
}

# update repo to latest from specified branch
update_repo_branch() {
    local repo="$1"
    local branch="$2"

    echo "Updating $repo to latest from $branch branch..."
    cd "$BASE_PATH/$repo"
    git fetch origin
    git stash save
    git checkout "$branch"
    git pull --rebase
    git stash pop || true # prevent exit if nothing to pop
}

# checkout repo at specified tag
checkout_repo_tag() {
    local repo="$1"
    local tag="$2"

    echo "Checking out $repo at tag $tag..."
    cd "$BASE_PATH/$repo"
    git fetch origin
    git stash save
    git checkout tags/"$tag"
    git stash pop || true # prevent exit if nothing to pop

    # set ngen submodules to master/main branch
    if [[ "$repo" == "ngen" ]]; then
        git submodule set-branch --branch master extern/cfe/cfe
        git submodule set-branch --branch master extern/SoilFreezeThaw/SoilFreezeThaw
        git submodule set-branch --branch main extern/SoilMoistureProfiles/SoilMoistureProfiles
        git submodule set-branch --branch master extern/evapotranspiration/evapotranspiration
        git submodule set-branch --branch main extern/noah-owp-modular/noah-owp-modular
        git submodule set-branch --branch master extern/topmodel/topmodel
        git submodule set-branch --branch master extern/t-route
        git submodule set-branch --branch master extern/sloth
        git submodule set-branch --branch master extern/LASAM
        git submodule set-branch --branch master extern/snow17
        git submodule set-branch --branch master extern/sac-sma/sac-sma
        git submodule set-branch --branch master extern/ueb-bmi

        git submodule update --remote
    fi
}

# --- RELEASE WORKFLOW ---
if [[ "$BUILD_TYPE" == "release" ]]; then
    cd "$BASE_PATH"

    # build order: ngen -> others
    if [[ " ${SELECTED_REPOS[@]} " =~ " ngen " ]]; then
        # checkout ngen to specified tag
        checkout_repo_tag "ngen" "${TAGS[ngen]}"

        echo "Building ngen Docker image..."
        GITLAB_TOKEN=$(cat "${BASE_PATH}/.gitlab_token") docker build \
            --progress=plain \
            --no-cache \
            --secret id=GITLAB_TOKEN,env=GITLAB_TOKEN \
            --tag="${REGISTRY}/ngen:${TAGS[ngen]}" \
            "${BASE_PATH}/ngen"
    fi

    for repo in "${SELECTED_REPOS[@]}"; do
        case "$repo" in
            "ngen-cal")
                # checkout ngen-cal to specified tag
                checkout_repo_tag "ngen-cal" "${TAGS[ngen-cal]}"
                echo "Building ngen-cal Docker image..."
                GITLAB_TOKEN=$(cat "${BASE_PATH}/.gitlab_token") docker build \
                    --progress=plain \
                    --no-cache \
                    --secret id=GITLAB_TOKEN,env=GITLAB_TOKEN \
                    --build-arg IMAGE_TAG="${TAGS[ngen]}" \
                    --tag="${REGISTRY}/ngen-cal:${TAGS[ngen-cal]}" \
                    "${BASE_PATH}/ngen-cal"
                ;;

            "ngen-bmi-forcing")
                echo "Pulling ngen-bmi-forcing Docker image..."
                docker pull "${REGISTRY}/ngen-forcing/ngen-bmi-forcing:${TAGS[forcing]}"
                ;;

            "ngen-lumped-forcing")
                echo "Pulling ngen-lumped-forcing Docker image..."
                docker pull "${REGISTRY}/ngen-forcing/ngen-lumped-forcing:${TAGS[forcing]}"
                ;;

            "ngen-fcst")
                # checkout ngen-fcst to specified tag
                checkout_repo_tag "ngen-fcst" "${TAGS[ngen-fcst]}"
                echo "Building ngen-fcst Docker image..."
                GITLAB_TOKEN=$(cat "${BASE_PATH}/.gitlab_token") docker build \
                    --progress=plain \
                    --no-cache \
                    --secret id=GITLAB_TOKEN,env=GITLAB_TOKEN \
                    --build-arg NGEN_VERSION="${TAGS[ngen]}" \
                    --tag="${REGISTRY}/ngen-fcst:${TAGS[ngen-fcst]}" \
                    "${BASE_PATH}/ngen-fcst"
                ;;

            "ngen-verf")
                # checkout ngen-verf to specified tag
                checkout_repo_tag "ngen-verf" "${TAGS[ngen-verf]}"
                echo "Building ngen-verf Docker image..."
                GITLAB_TOKEN=$(cat "${BASE_PATH}/.gitlab_token") docker build \
                    --progress=plain \
                    --no-cache \
                    --secret id=GITLAB_TOKEN,env=GITLAB_TOKEN \
                    --build-arg NGEN_EVAL_TAG="${TAGS[ngen-eval]}" \
                    --tag="${REGISTRY}/ngen-verf:${TAGS[ngen-verf]}" \
                    "${BASE_PATH}/ngen-verf"
                ;;
            
            ngencerf*)
                # checkout ngencerf* repos to specified tag
                checkout_repo_tag "$repo" "${TAGS[$repo]}"
                ;;
        esac

        if [[ "$repo" != ngencerf* ]]; then
            if [[ "$repo" == "ngen-bmi-forcing" || "$repo" == "ngen-lumped-forcing" ]]; then
                IMAGE="${REGISTRY}/ngen-forcing/${repo}:${TAGS[forcing]}"
            else
                IMAGE="${REGISTRY}/${repo}:${TAGS[$repo]}"
            fi
            build_singularity_container_update_symlink "$BUILD_TYPE" "$repo" "$IMAGE"
        fi
    done

    echo "Release build completed successfully!"
    exit 0
fi

# ---- DEVELOPMENT WORKFLOW ----
if [[ "$BUILD_TYPE" == "development" ]]; then
    cd "$BASE_PATH"

    for repo in "${SELECTED_REPOS[@]}"; do
        echo
        if [[ "$repo" == ngencerf* ]]; then
            # update ngencerf* repos to latest from development branch
            update_repo_branch "$repo" "development"
        else 
            if [[ "$repo" == "ngen-bmi-forcing" || "$repo" == "ngen-lumped-forcing" ]]; then
                IMAGE="${REGISTRY}/ngen-forcing/${repo}:latest"
            else
                IMAGE="${REGISTRY}/${repo}:latest"
            fi

            echo "Pulling docker image: $IMAGE"
            docker pull "$IMAGE"
            build_singularity_container_update_symlink "$BUILD_TYPE" "$repo" "$IMAGE"
        fi
    done

    echo "Development build completed successfully!"
fi
