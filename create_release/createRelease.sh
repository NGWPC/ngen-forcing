#!/bin/bash

# Start logging everything to a file
LOGFILE="createRelease_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee >(sed -r "s/\x1B\[[0-9;]*[mK]//g" >> "$LOGFILE")) 2>&1
echo "All output will be logged to: $LOGFILE"


declare -a TEMP_BRANCHES

#-----------------------------------------
# Function: usage
# Displays usage information and exits.
#-----------------------------------------
usage() {
  echo "Usage: $(basename "$0") <RELEASE_TYPE> [JSON_FILE] [WAIT_TIME]"
  echo
  echo "This script automates the release process for GitLab repositories, handling merges,"
  echo "submodules, and versioning."
  echo "It performs the following steps based on the release type:"
  echo
  echo "🔹 RC (Release Candidate) Process:"
  echo "  1. Merge from 'development' to 'release-candidate' (except for RC1)."
  echo "  2. If submodules exist, ensure they are on the correct branch."
  echo "  3. Create a GitLab release for the RC."
  echo "  4. Merge 'release-candidate' back into 'development' (except for RC1)."
  echo
  echo "🔹 Official Release Process:"
  echo "  1. Merge from 'release-candidate' to 'main' or 'master'."
  echo "  2. If submodules exist, ensure they are on the correct branch."
  echo "  3. Create a GitLab release for the official version."
  echo "  4. Merge the final release changes back into 'development'."
  echo
  echo "🔹 Handling Submodules:"
  echo "  - If the repository has submodules, they will be checked out to the correct branch ('release-candidate', 'development', or 'main/master')"
  echo "    and merged back into the correct branch of the parent repository."
  echo "  - A temporary branch is created for submodule updates, ensuring consistency across all modules."
  echo "  - The temporary branch is then merged back into the appropriate target branch."
  echo
  echo "Arguments:"
  echo "  RELEASE_TYPE : REQUIRED. Must be either 'OFFICIAL' or 'RC'."
  echo "  JSON_FILE    : Optional. Path to the configuration JSON file."
  echo "                 Default is 'createReleaseConfig.json'."
  echo "  WAIT_TIME    : Optional. Wait time for mergeable check in seconds."
  echo "                 Default is 300 seconds."
  echo
  echo "Example:"
  echo "  $(basename "$0") RC release_config.json 300"
  echo
  exit 0
}

# If the first argument is -h or --help, display usage.
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
fi


# Define color codes
RED='\033[1;31m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
NC='\033[0m' # No Color

#-----------------------------------------
# Function: read_token
# Reads the GitLab token from ~/.gitlab_token.
#
# Returns:
#   Sets the global variable GITLAB_TOKEN.
#-----------------------------------------
read_token() {
  GITLAB_TOKEN=$(cat ~/.gitlab_token)
}

#-----------------------------------------
# Function: clean_and_encode_project
# Removes optional authentication info, the fixed GitLab prefix, and the trailing .git from a URL,
# then returns the URL‑encoded project string.
#
# Parameters:
#   $1 - The raw remote URL (e.g., "https://username:password@gitlab.sh.nextgenwaterprediction.com/NGWPC/nwm-ngen/my-project.git")
#
# Returns:
#   The URL‑encoded project path (e.g., "NGWPC%2Fnwm-ngen%2Fmy-project")
#-----------------------------------------
clean_and_encode_project() {
  local project_url="$1"

  # Remove authentication details (username and password) if present
  project_url=$(echo "$project_url" | sed -e 's#^https\?://[^/]*@#https://#')

  # Remove the fixed GitLab prefix.
  project_url=$(echo "$project_url" | sed -e 's#^https://gitlab\.sh\.nextgenwaterprediction\.com/##')

  # Remove the '.git' suffix if present
  project_url=$(echo "$project_url" | sed -e 's#\.git$##')

  # URL encode the project path
  jq -nr --arg v "$project_url" '$v|@uri'
}

#-----------------------------------------
# Function: determine_release_branch
# Determines whether the repository has a "main" or "master" branch by querying the GitLab API.
#
# Parameters:
#   $1 - Repository API URL (with encoded project path)
#
# Uses:
#   Global variable GITLAB_TOKEN.
#
# Returns:
#   The branch name ("main" or "master"), or an empty string if neither exists.
#-----------------------------------------
determine_release_branch() {
  local repo_url="$1"

  # Check for the existence of the "main" branch.
  branch_main=$(curl --silent --header "PRIVATE-TOKEN: $GITLAB_TOKEN" "$repo_url/repository/branches/main" | jq -r '.name')
  if [ "$branch_main" == "main" ]; then
    echo "main"
    return 0
  fi

  # If not found, check for the "master" branch.
  branch_master=$(curl --silent --header "PRIVATE-TOKEN: $GITLAB_TOKEN" "$repo_url/repository/branches/master" | jq -r '.name')
  if [ "$branch_master" == "master" ]; then
    echo "master"
    return 0
  fi

  # Neither branch was found.
  echo ""
}

#-----------------------------------------
# Function: create_merge_request
# Creates a merge request using the GitLab API.
#
# Arguments:
#   $1 - Repository API URL (e.g., "https://gitlab.sh.nextgenwaterprediction.com/api/v4/projects/ENCODED_PROJECT")
#   $2 - Source branch
#   $3 - Target branch
#   $4 - Title for the merge request
#   $5 - should_remove_source_branch (true or false)
#
# Behavior:
#   Sends a POST request to create a merge request.
#   If successful, echoes the merge request IID.
#   If a 409 Conflict occurs (i.e. another open MR exists for the source branch),
#     it extracts the IID from the error message (expected to contain a pattern like "!10")
#     and echoes that value.
#
# Returns:
#   0 if the merge request was created successfully (or an existing MR was detected),
#   1 if creation failed.
#-----------------------------------------
create_merge_request() {
  local repo_url="$1"
  local source_branch="$2"
  local target_branch="$3"
  local title="$4"
  local should_remove_source_branch="$5"

  # Build the JSON payload for the curl command.
  local data_payload
  data_payload=$(cat <<EOF
{
  "source_branch": "${source_branch}",
  "target_branch": "${target_branch}",
  "title": "${title}",
  "should_remove_source_branch": ${should_remove_source_branch}
}
EOF
)

  echo
  echo -e "Creating merge request from ${GREEN}$source_branch${NC} to ${GREEN}$target_branch${NC} (remove source branch: $should_remove_source_branch)" >&2
  local curl_cmd
  curl_cmd="curl --silent --request POST \
    --header \"PRIVATE-TOKEN: $GITLAB_TOKEN\" \
    --header \"Content-Type: application/json\" \
    --data '$data_payload' \
    \"$repo_url/merge_requests\" \
    -w \"\nHTTP Response Code: %{http_code}\""

  # Echo the entire curl command for debugging.
  # echo "Executing create_merge_request command: $curl_cmd" >&2

  # Execute the curl command.
  local response
  response=$(eval "$curl_cmd")

  # Extract the HTTP code using our known output format.
  local http_code
  http_code=$(echo "$response" | grep -o "HTTP Response Code: [0-9]*" | awk '{print $4}' | tr -d '\n')
  local json_response
  json_response=$(echo "$response" | sed '$d')

  if [[ $http_code =~ ^2 ]]; then
    local iid
    iid=$(echo "$json_response" | jq -r '.iid')
    if [[ "$iid" != "null" && -n "$iid" ]]; then
      # Return this in stdout
      echo "$iid"
      return 0
    else
      echo -e "${RED}HTTP success but no valid merge request IID found.${NC}" >&2
      return 1
    fi
  elif [ "$http_code" -eq 409 ]; then
    # Conflict: extract the merge request IID from the error message.
    local conflict_msg conflict_iid
    # Retrieve the first error message from the JSON response.
    conflict_msg=$(echo "$json_response" | jq -r '.message[0]')
    echo "$conflict_msg" >&2
    # Extract the pattern: an exclamation mark followed by one or more digits.
    # Then remove the exclamation mark so only the IID remains.
    conflict_iid=$(echo "$conflict_msg" | grep -oE '!([0-9]+)' | tr -d '!')
    if [ -n "$conflict_iid" ]; then
      echo "$conflict_iid"
      return 0
    fi
  fi

  # Print errors if we reach here.
  if echo "$json_response" | jq -e '.message | type=="array"' >/dev/null 2>&1; then
    echo -e "${RED}Error creating Merge Request (HTTP $http_code):${NC}" >&2
    echo -e "${RED}$(echo "$json_response" | jq -r '.message[]')${NC}" >&2

  else
    local error_message
    error_message=$(echo "$json_response" | jq -r '.message')
    echo -e "${RED}Error creating Merge Request (HTTP $http_code): $error_message${NC}" >&2
  fi
  return 1
}

#-----------------------------------------
# Function: trigger_merge
# Triggers the merge for a given merge request.
#
# Arguments:
#   $1 - Repository API URL
#   $2 - Merge request IID
#
# Returns:
#   0 on success, 1 on failure.
#-----------------------------------------
trigger_merge() {
  local repo_url="$1"
  local merge_iid="$2"
  local data_payload='{"should_remove_source_branch": false}'

  # Build the curl command as a string.
  local curl_cmd
  curl_cmd="curl --silent --request PUT \
    --header \"PRIVATE-TOKEN: $GITLAB_TOKEN\" \
    --header \"Content-Type: application/json\" \
    --data '$data_payload' \
    \"$repo_url/merge_requests/${merge_iid}/merge\" \
    -w \"\nHTTP Response Code: %{http_code}\""

  # Echo the entire curl command for debugging.
  # echo "Executing trigger_merge command: $curl_cmd"

  echo "Triggering merge for MR IID: $merge_iid..."
  local merge_response
  merge_response=$(eval "$curl_cmd")
  local http_code
  http_code=$(echo "$merge_response" | grep -o "HTTP Response Code: [0-9]*" | awk '{print $4}')

  if [[ $http_code =~ ^2 ]]; then
    echo "Merge triggered successfully."
    echo 
    return 0
  else
    echo -e "${RED}Error triggering merge (HTTP $http_code). Response:${NC}"
    echo -e "${RED}$(echo "$merge_response" | sed '$d')${NC}"
    echo "Trigger merge command: $curl_cmd"
    return 1
  fi
}

#-----------------------------------------
# Function: poll_merge_status
# Polls the merge request until its status is either "merged" or "closed".
#
# Arguments:
#   $1 - Repository API URL
#   $2 - Merge request IID
#
# Behavior:
#   Continuously queries the merge request status and displays progress until the status
#   is either "merged" or "closed".
#-----------------------------------------
poll_merge_status() {
  local repo_url="$1"
  local merge_iid="$2"

  echo "Waiting for merge request $merge_iid to complete..."
  while true; do
    local merge_response
    merge_response=$(curl --silent --header "PRIVATE-TOKEN: $GITLAB_TOKEN" "$repo_url/merge_requests/${merge_iid}")
    local state
    state=$(echo "$merge_response" | jq -r '.state')
    
    if [ "$state" == "merged" ]; then
      echo "Merge is complete."
      echo
      break
    elif [ "$state" == "closed" ]; then
      echo "Merge request closed without merging."
      break
    else
      echo "Current merge request state: $state. Waiting 10 seconds..."
      sleep 10
    fi
  done
}

#-----------------------------------------
# Function: wait_until_mergeable
# Waits until the merge request is mergeable, or until a timeout is reached.
#
# Arguments:
#   $1 - Repository API URL
#   $2 - Merge request IID
#   $3 - Maximum wait time in seconds
#
# Behavior:
#   Retrieves the merge request details and checks:
#     - That merge_status is not empty.
#     - If detailed_merge_status contains "broken_status" (case-insensitive),
#       it indicates there are no changes to merge, so the function prints an error message and returns 2.
#       (GitLab doesn't document the possible values, so we're assuming that "broken_status" means the MR is permanently unmergeable.)
#     - Otherwise, if merge_status equals "can_be_merged", it returns 0.
#
# Returns:
#   0 if the merge request becomes mergeable within the timeout,
#   2 if there are no changes to merge (detailed_merge_status is "broken_status"),
#   1 otherwise.
#-----------------------------------------
wait_until_mergeable() {
  local repo_url="$1"
  local merge_id="$2"
  local max_wait="$3"
  local elapsed=0

  while true; do
    local curl_cmd
    curl_cmd="curl --silent --header \"PRIVATE-TOKEN: $GITLAB_TOKEN\" \"$repo_url/merge_requests/${merge_id}\""
    # Echo the entire curl command for debugging.
    # echo "Executing wait_until_mergeable command: $curl_cmd"
    
    local json_resp mr_status detailed_status
    json_resp=$(eval "$curl_cmd")

    # Validate that the response is not empty.
    if [ -z "$json_resp" ]; then
      echo "Error: Empty response received."
      return 1
    fi

    mr_status=$(echo "$json_resp" | jq -r '.merge_status')
    detailed_status=$(echo "$json_resp" | jq -r '.detailed_merge_status')

    # Validate that mr_status is not empty.
    if [ -z "$mr_status" ]; then
      echo "Error: merge_status field is empty in the response:"
      echo "$json_resp"
      return 1
    fi

    # Check if detailed_merge_status contains "broken_status" (case-insensitive).
    if echo "$detailed_status" | grep -qi "broken_status"; then
      echo -e "${RED}Merge request cannot be completed - either no changes to merge or a conflict (detailed status: $detailed_status).${NC}"
      return 2
    fi

    # Need to check for both statuses to avoid a 405
    if [ "$mr_status" == "can_be_merged" ] && [ "$detailed_status" == "mergeable" ]; then
      echo "Merge request can be merged (merge_status: $mr_status, detailed_merge_status: $detailed_status)"
      return 0
    fi

    if [ "$elapsed" -ge "$max_wait" ]; then
      while true; do
        read -n 1 -s -r -p "Merge request $merge_id is still not mergeable. (C)ontinue waiting, (S)kip this repo: " choice
        echo
        choice=$(echo "$choice" | tr '[:lower:]' '[:upper:]')
        case "$choice" in
          C) echo "Continuing to wait..."; elapsed=0;;  # Reset elapsed time and keep waiting
          S) echo "Skipping repository due to timeout."; return 1;;  # Exit with failure
          *) echo "Invalid option. Please enter C to continue waiting or S to skip.";;
        esac
      done
    fi

    echo "Waiting for MR to be mergeable (current merge_status: $mr_status, detailed_merge_status: $detailed_status)..."
    sleep 2
    elapsed=$((elapsed + 2))
  done
}


#-----------------------------------------
# Function: create_release
# Creates an official GitLab release.
#
# Arguments:
#   $1 - Repository API URL (e.g., "https://gitlab.sh.nextgenwaterprediction.com/api/v4/projects/ENCODED_PROJECT")
#   $2 - Release tag (e.g., "v1.1")
#   $3 - Release name (e.g., "Release 1.1")
#   $4 - Release notes (description)
#   $5 - Ref branch (the branch to base the release on)
#
# Returns:
#   0 on success, 1 on failure.
#-----------------------------------------
create_release() {
  local repo_url="$1"
  local release_tag="$2"
  local release_name="$3"
  local release_notes="$4"
  local ref_branch="$5"

  local data_payload
  data_payload=$(cat <<EOF
{
  "tag_name": "${release_tag}",
  "name": "${release_name}",
  "description": "${release_notes}",
  "ref": "${ref_branch}"
}
EOF
)


  local curl_cmd
  curl_cmd="curl --silent --request POST \
    --header \"PRIVATE-TOKEN: $GITLAB_TOKEN\" \
    --header \"Content-Type: application/json\" \
    --data '$data_payload' \
    \"$repo_url/releases\" \
    -w \"\nHTTP Response Code: %{http_code}\""

  # Echo the entire curl command for debugging.
  # echo "Executing create_release command: $curl_cmd"
  local response
  response=$(eval "$curl_cmd")
  local http_code
  http_code=$(echo "$response" | grep -o "HTTP Response Code: [0-9]*" | awk '{print $4}' | tr -d '\n')
  local json_response
  json_response=$(echo "$response" | sed '$d')

  if [[ $http_code =~ ^2 ]]; then
    echo -e "${GREEN}Release created successfully.${NC}"
    echo
    return 0
  else
    echo -e "${RED}Error creating release (HTTP $http_code):${NC}"
    echo -e "${RED}$json_response${NC}"
    return 1
  fi
}

#-----------------------------------------
# Function: execute_merge_request
# Combines creating a merge request, waiting until it becomes mergeable, and triggering the merge.
# We validate it before creating it, to better ensure that it will succeed.
#
# Arguments:
#   $1 - Repository API URL
#   $2 - Source branch
#   $3 - Target branch
#   $4 - Title for the merge request
#   $5 - should_remove_source_branch (true or false)
#   $6 - wait time
#
# Behavior:
#   - Checks if the source branch has changes compared to the target.
#   - Attempts a local merge to detect conflicts before creating a merge request.
#   - Only proceeds with the GitLab API call if the merge is clean.
#
# Returns:
#   0 on success; 1 on failure.
#-----------------------------------------
execute_merge_request() {
  local repo_url="$1"
  local source_branch="$2"
  local target_branch="$3"
  local title="$4"
  local remove_flag="$5"
  local wait_time="$6"

  local branch_created=0  # Flag to track if the target branch was just created
  local previous_branch
  previous_branch=$(git rev-parse --abbrev-ref HEAD)  # Save current branch

  # Check if the target branch exists in the remote repository
  echo Checking if $target_branch exists...
  if ! git ls-remote --exit-code --heads origin "$target_branch" > /dev/null 2>&1; then
    ### for debugging
    git ls-remote --exit-code --heads origin "$target_branch"
    ###
    echo -e "${YELLOW}Target branch $target_branch does not exist. Creating it from $source_branch...${NC}"

    # Create the target branch locally from the source branch
    git checkout --quiet "$source_branch"
    git checkout --quiet -b "$target_branch"
    git push --set-upstream origin "$target_branch"

    # Push the new branch to origin
    git push origin "$target_branch"

    echo -e "${GREEN}Successfully created and pushed branch $target_branch from $source_branch.${NC}"
    
    branch_created=1  # Mark that we just created the branch
  fi

  # If the target branch was just created, skip the merge request
  if [ "$branch_created" -eq 1 ]; then
    echo -e "${YELLOW}Skipping merge request since $target_branch was just created from $source_branch.${NC}"
    git checkout --quiet "$previous_branch"  # Restore original branch
    return 0
  fi

  echo -e "${YELLOW}Checking merge viability between $source_branch and $target_branch...${NC}"

  # Ensure we have the latest updates for source branch
  git checkout --quiet "$source_branch"
  git pull --quiet

  # Determine merge base (GitLab considers this as the common ancestor)
  local merge_base
  merge_base=$(git merge-base origin/"$source_branch" origin/"$target_branch")

  # Check if there's an actual difference from the merge base
  if git diff --quiet "$merge_base" origin/"$source_branch"; then
    echo -e "${RED}No changes detected in $source_branch relative to $target_branch. Skipping merge request.${NC}"
    git checkout --quiet "$previous_branch"  # Restore original branch
    return 1
  fi

  # Save the currently checked-out branch so we can restore it later
  local previous_branch
  previous_branch=$(git rev-parse --abbrev-ref HEAD)

  # Create a temporary test merge branch
  local temp_merge_branch="merge_test_${source_branch}_to_${target_branch}"
  git checkout --quiet -b "$temp_merge_branch" origin/"$target_branch"
  TEMP_BRANCHES+=("$temp_merge_branch")

  # Attempt to merge the source branch into the target branch quietly
  # if ! git merge --no-commit --no-ff origin/"$source_branch" > /dev/null 2>&1; then
  if ! git merge --no-commit --no-ff origin/"$source_branch" ; then
    echo -e "${RED}Merge conflicts detected between $source_branch and $target_branch. Merge request will not be created.${NC}"
    git merge --abort
    git checkout --quiet "$previous_branch"
    git branch --quiet -D "$temp_merge_branch"
    return 1
  fi

  echo -e "${GREEN}Local merge test successful. Proceeding with API call to create merge request...${NC}"
  echo
  git checkout --quiet "$previous_branch"
  git branch --quiet -D "$temp_merge_branch"

  # Now, create the merge request via GitLab API
  local mr_iid
  mr_iid=$(create_merge_request "$repo_url" "$source_branch" "$target_branch" "$title" "$remove_flag" | tr -d '\n')
  # Our return code check isn't always working, so also check if we have an mr_iid
  if [ $? -ne 0 ] || [ -z "$mr_iid" ]; then
    echo -e "${RED}Error: Merge Request creation failed for merging $source_branch into $target_branch.${NC}"
    return 1
  fi

  echo "Waiting up to $wait_time seconds for merge request $mr_iid to become mergeable..."
  wait_until_mergeable "$repo_url" "$mr_iid" "$wait_time"
  local ret=$?

  if [ $ret -ne 0 ]; then
    echo -e "${RED}Timeout or error waiting for merge request $mr_iid to become mergeable.${NC}"
    return 1
  fi

  if ! trigger_merge "$repo_url" "$mr_iid"; then
    echo -e "${RED}Merge trigger failed for MR $mr_iid.${NC}"
    return 1
  fi

  poll_merge_status "$repo_url" "$mr_iid"
  return 0
}

#-----------------------------------------
# Function: get_next_rc_number
# Determines the next available release-candidate (rcX) number.
#
# Arguments:
#   $1 - Release number (e.g., "10.2")
#
# Behavior:
#   - Lists existing Git tags matching the pattern "<release_number>-rcX".
#   - Extracts the numeric portion (X) from those tags.
#   - Finds the highest existing rc number and increments it.
#   - If no matching tags exist, starts at "rc1".
#
# Returns:
#   The next available release candidate tag (e.g., "10.2-rc1", "10.2-rc2").
#-----------------------------------------
get_next_rc_number() {
  local release_number="$1"  # e.g., "10.2"

  # List tags, filter for those matching "<release_number>-rcX", extract the X part
  local highest_rc=$(git tag | grep -E "^${release_number}-rc[0-9]+$" | sed -E "s/^${release_number}-rc([0-9]+)$/\1/" | sort -nr | head -n1)

  # Determine the next rc number
  if [[ -z "$highest_rc" ]]; then
    echo "${release_number}-rc1"
  else
    local next_rc=$((highest_rc + 1))
    echo "${release_number}-rc${next_rc}"
  fi
}


#-----------------------------------------
# Function: generate_changelog
# Generates a changelog for the upcoming release by listing commit
# messages between the most recent official (previous) tag and HEAD.
#
# Behavior:
#   - Finds the most recent tag that follows the format "X.Y" (e.g., "10.2"),
#     excluding pre-release tags like "10.2-rc1".
#   - If a previous tag is found, sets the commit range as "previous_tag..HEAD".
#     Otherwise, uses HEAD as the range.
#   - Retrieves commit messages (excluding merge commits) in reverse chronological order.
#   - Ensures that the 'changelogs' directory exists in the script's original execution location.
#   - Extracts the last segment of <REPO_PROJECT> (after the last '/') for the filename.
#   - Outputs the changelog to "changelogs/<last_part_of_repo_project>_<RELEASE_NUMBER>_changelog.txt".
#
# Returns:
#   0 on success.
#-----------------------------------------
generate_changelog() {
  # Find the most recent official release tag (numbers and dots only, no rc/beta/etc.)
  local previous_tag
  previous_tag=$(git tag | grep -E '^[0-9]+\.[0-9]+$' | sort -V | tail -n1)

  local commit_range
  if [ -n "$previous_tag" ]; then
    commit_range="${previous_tag}..HEAD"
  else
    commit_range="HEAD"
  fi

  # Get the date and time of the HEAD commit
  local head_date
  head_date=$(git log -1 --pretty=format:'%ad' --date='format:%Y-%m-%d %H:%M:%S' HEAD)

  # Extract the last part of REPO_PROJECT (everything after the last '/')
  local repo_name
  repo_name=$(basename "$REPO_PROJECT")

  # Ensure the changelogs directory exists in the script's original execution location
  local changelog_dir="${SCRIPT_DIR}/changelogs"
  mkdir -p "$changelog_dir"

  # Define the output file path
  local changelog_file="${changelog_dir}/${repo_name}_${RELEASE_NUMBER}_changelog.txt"

  # Print header for the upcoming release into the changelog file (single line)
  printf "## Changelog for %s %s (%s)\n\n" "$REPO_PROJECT" "$RELEASE_NUMBER" "$head_date" > "$changelog_file"

  # Append the commit messages (excluding merge commits) to the changelog file
  git log $commit_range --oneline --reverse | grep -v Merge >> "$changelog_file"

  echo -e "${GREEN}Changelog saved to $changelog_file${NC}"
  return 0
}

#-----------------------------------------
# Function: process_submodules
# Processes all submodules in the repository.
#
# Arguments:
#   $1 - Target branch (e.g., "release-candidate", "development", "main/master")
#
# Behavior:
#   - Iterates over all submodules.
#   - For each submodule, it uses clean_and_encode_project to obtain the encoded project path
#     and then calls determine_release_branch (if needed) to set the correct branch.
#   - Checks out each valid submodule to that branch and updates it.
#   - Creates a temporary branch in the parent repository for submodule updates and triggers a merge request.
#-----------------------------------------
process_submodules() {
  local target_branch="$1"

  echo -e "${GREEN}Processing all submodules for target branch: $target_branch${NC}"

  # Get a list of all submodule paths
  local submodule_paths
  submodule_paths=$(git config --file .gitmodules --get-regexp path | awk '{print $2}')

  # Loop through each submodule
  for submodule_path in $submodule_paths; do
    echo
    echo "Processing submodule: $submodule_path"

    cd "$submodule_path"

    # Skip specific submodules
    if [[ "$submodule_path" == "test/googletest" || "$submodule_path" == "extern/pybind11" || "$submodule_path" == "extern/netcdf-cxx4/netcdf-cxx4" ]]; then
      echo -e "${YELLOW}Skipping submodule: $submodule_path${NC}"
      cd - > /dev/null
      continue
    fi

    # Get the remote URL of the submodule and encode the project path
    submodule_repo_url=$(git remote get-url origin)
    # Use clean_and_encode_project to process the submodule's remote URL.
    local submodule_encoded_project
    submodule_encoded_project=$(clean_and_encode_project "$submodule_repo_url")
   
    # Determine the submodule target branch based on the parent's target branch
    if [[ "$target_branch" == "main" || "$target_branch" == "master" ]]; then
      submodule_target_branch=$(determine_release_branch "https://gitlab.sh.nextgenwaterprediction.com/api/v4/projects/${submodule_encoded_project}")
    else
      submodule_target_branch="$target_branch"
    fi

    if [[ -z "$submodule_target_branch" ]]; then
      echo -e "${RED}Error: Neither 'main' nor 'master' branch found in submodule $submodule_path.${NC}"
      cd - > /dev/null
      continue # skip to next submodule
    fi

    # Checkout and update submodule
    echo -e "Checking out submodule ${GREEN}$submodule_path${NC} to branch ${GREEN}$submodule_target_branch${NC}"
    git checkout --quiet "$submodule_target_branch" && git pull --quiet origin "$submodule_target_branch"

    cd - > /dev/null  # Go back to the main repository
  done

  # Create a temporary branch to commit the submodule changes in the parent repo
  local temp_submodule_branch="temp_submodules_${target_branch}_${RELEASE_NUMBER}"
  echo -e "Creating temporary branch '${GREEN}$temp_submodule_branch${NC}' to commit submodule updates"
  git checkout --quiet -b "$temp_submodule_branch"
  TEMP_BRANCHES+=("$temp_submodule_branch")
  git add $(git config --file .gitmodules --get-regexp path | awk '{print $2}')

  if ! git diff --cached --quiet; then
    git commit -m "Update submodules to $target_branch branch"
    git push --set-upstream origin "$temp_submodule_branch"

    if ! execute_merge_request "$REPO_URL" "$temp_submodule_branch" "$target_branch" \
        "Merge submodule updates into $target_branch" true "$WAIT_TIME"; then
      return 1
    fi
  else
    echo -e "${YELLOW}No submodule changes detected. Skipping merge request.${NC}"
    git checkout --quiet "$target_branch"
    git branch --quiet -D "$temp_submodule_branch"
  fi

  return 0
}

#-----------------------------------------
# Function: process_repo
# Processes a single repository given its directory, a base release number, release notes,
# and optionally NGENCERF_VERSION and NGENCERF_DATE (for repositories with a version.env file).
#
# For RC releases the base number is processed through get_next_rc_number so that RELEASE_NUMBER
# is set (e.g. “10.2-rc1” or “10.2-rc2”). Then, if RELEASE_NUMBER ends with "-rc1" (or if the release
# is OFFICIAL), the script creates an initial merge request from the source branch to the target
# branch and tags the source branch. For subsequent RC releases (i.e. not candidate 1), the initial merge
# and tagging are skipped (assuming the target branch already has all required changes).
#
# Arguments:
#   $1 - Repository directory
#   $2 - Base release number (e.g., "1.2")
#   $3 - Release notes
#   $4 - (Optional) NGENCERF_VERSION value
#   $5 - (Optional) NGENCERF_DATE value
#   $6 - (Optional) has_submodules flag
#-----------------------------------------
process_repo() {
  local repo_directory="$1"
  local base_release_number="$2"
  local release_notes="$3"
  local ngencerf_version="$4"
  local ngencerf_date="$5"
  local has_submodules="$6"

  local start_time=$(date +"%Y-%m-%d %H:%M:%S")
  local start_seconds=$SECONDS  # Capture start time in seconds
  export start_seconds

  echo "----------------------------------------------------------"

  local return_code=0  # Default to success

  # Convert full path to tilde-prefixed path if it starts with $HOME
  if [[ $repo_directory == "$HOME"* ]]; then
    repo_directory_short="~${repo_directory#$HOME}"
  fi

  cd "$repo_directory" || { echo "Cannot cd to $repo_directory"; return_code=1; return; }

  # Set the global RELEASE_NUMBER based on RELEASE_TYPE
  if [ "$RELEASE_TYPE" = "RC" ]; then
    RELEASE_NUMBER=$(get_next_rc_number "$base_release_number")
  else
    RELEASE_NUMBER="$base_release_number"
  fi
  export RELEASE_NUMBER

  # We echo here so we can show the full release number.  So technically, we are missing out the timing for the get_next_rc_number
  echo -e "$start_time ${GREEN}Processing repository: $repo_directory (Release: $RELEASE_NUMBER)${NC}"
  echo


  echo -e "$start_time ${GREEN}Processing repository: $repo_directory (Release: $RELEASE_NUMBER)${NC}"

  echo -e "${YELLOW}Proceed with processing this repository? (C)ontinue, (S)kip, (Q)uit [default: C in 10s]:${NC}"
  read -t 10 -n 1 -s -r user_input
  echo

  # Default to Continue if no input is provided
  user_input="${user_input:-C}"
  user_input=$(echo "$user_input" | tr '[:lower:]' '[:upper:]')

  case "$user_input" in
    Q)
      echo -e "${RED}Quitting script.${NC}"
      exit 2
      ;;
    S)
      echo -e "${YELLOW}Skipping this repository.${NC}"
      return 1
      ;;
    C|*)
      echo -e "${GREEN}Continuing with $repo_directory...${NC}"
      ;;
  esac

  # Get the remote URL.
  repo_remote=$(git remote get-url origin)
  REPO_PROJECT=$(echo "$repo_remote" | sed -E 's|.*/([^/]+/[^/.]+)(\.git)?$|\1|')


  echo "Remote URL: $repo_remote"

  # Ensure cleanup_repo always runs when this function returns
  trap "cleanup_repo '$REPO_PROJECT' '$repo_directory_short'; trap - RETURN" RETURN

  # URL-encode the project path using url_encode_project.
  local ENCODED_PROJECT
  ENCODED_PROJECT=$(clean_and_encode_project "$repo_remote")
  echo "Encoded Project: $ENCODED_PROJECT"

  # Build the API URL.
  local REPO_URL="https://gitlab.sh.nextgenwaterprediction.com/api/v4/projects/${ENCODED_PROJECT}"
  echo "Repository API URL: $REPO_URL"

  # Fetch the list of tags from the remote repository and check if the release tag already exists.
  local remote_tags
  remote_tags=$(git ls-remote --tags origin | awk '{print $2}' | sed 's#refs/tags/##')
  if echo "$remote_tags" | grep -Fxq "$RELEASE_NUMBER"; then
    echo -e "${RED}Tag '$RELEASE_NUMBER' already exists in the remote repository. Please choose a different release number.${NC}"
    return_code=1
    return
  fi

  # Determine source and target branches *before* handling submodules
  local SOURCE_BRANCH TARGET_BRANCH
  if [ "$RELEASE_TYPE" = "RC" ]; then
    SOURCE_BRANCH="development"
    TARGET_BRANCH="release-candidate"
  else
    SOURCE_BRANCH="release-candidate"
    TARGET_BRANCH=$(determine_release_branch "$REPO_URL")
    if [ -z "$TARGET_BRANCH" ]; then
      echo -e "${RED}Error: Neither 'main' nor 'master' branch found in repository $REPO_URL.${NC}"
      return_code=1
      return
    fi
  fi

  echo -e "Source branch: ${GREEN}$SOURCE_BRANCH${NC}"
  echo -e "Target branch: ${GREEN}$TARGET_BRANCH${NC}"

  echo -e "Pulling latest updates for branch ${GREEN}${SOURCE_BRANCH}${NC}..."
  git checkout --quiet "$SOURCE_BRANCH" && git pull --quiet


  # Perform the merge request for the initial RC1 or Official release
  if [ "$RELEASE_TYPE" = "OFFICIAL" ] || [[ "$RELEASE_NUMBER" =~ -rc1$ ]]; then
    if ! execute_merge_request "$REPO_URL" "$SOURCE_BRANCH" "$TARGET_BRANCH" \
         "Merge $SOURCE_BRANCH into $TARGET_BRANCH for release $RELEASE_NUMBER" false "$WAIT_TIME"; then
      return_code=1
      return
    fi
  else
    # For subsequent RC releases, we assume that TARGET_BRANCH already has all needed changes.
    echo -e "${YELLOW}Subsequent RC release detected. Skipping merge from $SOURCE_BRANCH.${NC}"
  fi

  # Pull the latest updates for the target branch.
  echo -e "Pulling latest updates for branch ${GREEN}$TARGET_BRANCH${NC}..."
  git checkout --quiet "$TARGET_BRANCH" && git pull --quiet
  echo

  if [ "$has_submodules" = "true" ]; then
    process_submodules "$TARGET_BRANCH"
  fi


  # Create changelog for OFFICIAL releases
  if [ "$RELEASE_TYPE" = "OFFICIAL" ]; then
    echo
    # Generate the changelog for the current release tag.
    echo "Generating changelog for tag $RELEASE_NUMBER:"
    generate_changelog
  fi

  while true; do
    read -n 1 -s -r -p "Proceed with the actual GitLab $RELEASE_TYPE release for $REPO_PROJECT? (Y)es, (N)o, (Q)uit: " choice
    echo
    choice=$(echo "$choice" | tr '[:lower:]' '[:upper:]')
    case "$choice" in
      Q) echo "Quitting script."; return_code=2; return;;
      N) echo "Skipping $repo_directory_short"; return_code=1; return;;
      Y) echo "Continuing processing $repo_directory_short..."; break;;
      *) echo "Invalid option. Please try again." >&2;;
    esac
  done

  # Create GitLab release
  echo -e "${GREEN}Creating official GitLab release for $REPO_PROJECT...${NC}"
  if ! create_release "$REPO_URL" "$RELEASE_NUMBER" "Release $RELEASE_NUMBER" "$release_notes" "$TARGET_BRANCH"; then
    echo -e "${RED}Error: Official release creation for $REPO_PROJECT failed.${NC}"
    return_code=1
    return
  fi


  # Merge the target branch back to development only for RC releases that are not -rc1
  if [[ "$RELEASE_TYPE" == "RC" && ! "$RELEASE_NUMBER" =~ -rc1$ ]]; then
    if ! execute_merge_request "$REPO_URL" "$TARGET_BRANCH" "development" \
         "Merge $TARGET_BRANCH into development for release $RELEASE_NUMBER" false "$WAIT_TIME"; then
      return_code=1
      return
    fi
 fi


  # If submodules exist, set all submodules to development
  if [ "$has_submodules" = "true" ]; then
    process_submodules "development"
  fi

  echo -e "Pulling latest updates for branch ${GREEN}${SOURCE_BRANCH}${NC}"
  git checkout --quiet "$SOURCE_BRANCH" && git pull --quiet
  echo

  if [ "$SOURCE_BRANCH" != "development" ]; then
    echo -e "Pulling latest updates for branch ${GREEN}development${NC}..."
    git checkout --quiet development && git pull --quiet
    echo
  fi

  echo -e "Pulling latest updates for branch ${GREEN}$TARGET_BRANCH${NC}..."
  git checkout --quiet "$TARGET_BRANCH" && git pull --quiet
  echo

  return "$return_code"
}

#-----------------------------------------
# Function: cleanup_repo
# Cleans up temporary branches and logs the processing status for the current repository.
#
# Behavior:
#   - Checks out the 'development' branch and pulls the latest changes.
#   - Retrieves the latest commit hash for the repository.
#   - Records the release number, processing status (SUCCESS or FAILED), elapsed time,
#     and commit hash in a global associative array.
#   - Iterates through the TEMP_BRANCHES array, deleting each temporary branch locally
#     and remotely (if it exists).
#   - Adds the repository to a global order list and prints a final message with the elapsed time.
#   - Sets a global return code variable (GLOBAL_RETURN_CODE) to reflect the overall status.
#-----------------------------------------
cleanup_repo() {
  local repo_project="$1"
  local repo_short="$2"

  local exit_code=$return_code  # Preserve the return code
  local end_time=$(date +"%Y-%m-%d %H:%M:%S")
  local elapsed_seconds=$(( SECONDS - start_seconds ))

  git checkout --quiet development && git pull --quiet

  # Retrieve the latest commit hash for the release
  local latest_commit_hash
  latest_commit_hash=$(git rev-parse HEAD)

  # Store status, elapsed time, and commit hash in the global array
  local status="FAILED"
  if [ "$return_code" -eq 0 ]; then
    status="SUCCESS"
  fi

  repo_status["$repo_directory"]="$RELEASE_NUMBER | $status | ${elapsed_seconds}s | $latest_commit_hash"

  # Iterate through TEMP_BRANCHES and delete them
  for temp_branch in "${TEMP_BRANCHES[@]}"; do
    if git branch --list | grep -q "$temp_branch"; then
      echo "Deleting local branch: $temp_branch"
      git branch -D "$temp_branch"
    fi

    if git ls-remote --heads origin "$temp_branch" | grep -q "$temp_branch"; then
      echo "Deleting remote branch: $temp_branch"
      git push origin --delete "$temp_branch"
    fi
  done

  repo_order+=("$repo_directory")
  echo -e "$end_time ${GREEN}Finished processing: $REPO_PROJECT ($repo_directory_short)${NC} (Elapsed time: $elapsed_seconds seconds)"

  # Simply returning the return code doesn't see to work.  Need to use a global variable.  It might be Trap that is getting in the way
  GLOBAL_RETURN_CODE=$exit_code  # Set the global return code instead of returning
}

# Summary function to print repo statuses

# Global associative array to store repository status
declare -A repo_status
# Global array to store repository order
repo_order=()

print_summary() {
  local longest_repo_name=0
  local total_elapsed_seconds=$(( SECONDS - total_seconds ))

  # Determine the longest repository name from the repo_order array
  for repo in "${repo_order[@]}"; do
    if (( ${#repo} > longest_repo_name )); then
      longest_repo_name=${#repo}
    fi
  done

  # Column widths
  local repo_column_width=$((longest_repo_name + 2)) # Add extra padding
  local release_column_width=15
  local status_column_width=10
  local time_column_width=6
  local commit_column_width=40 # Adjust based on hash length
  local total_width=$((repo_column_width + release_column_width + status_column_width + time_column_width + commit_column_width + 13))

  # Define summary file path
  local summary_file="${SCRIPT_DIR}/release_summary.txt"

  # Print header to console and file
  printf "\n%-${repo_column_width}s | %-${release_column_width}s | %-${status_column_width}s | %-${time_column_width}s | %-${commit_column_width}s\n" \
    "Repository" "Release" "Status" "Time" "Commit Hash" | tee "$summary_file"
  printf -- "%-${total_width}s\n" | tr ' ' '-' | tee -a "$summary_file"

  # Print repository details in the order they were processed
  for repo in "${repo_order[@]}"; do
    IFS='|' read -r release status time commit_hash <<< "${repo_status[$repo]}"
    printf "%-${repo_column_width}s | %-15s | %-10s | %-6s | %-40s\n" \
      "$repo" "$release" "$status" "$time" "$commit_hash" | tee -a "$summary_file"
  done

  # Print footer
  printf -- "%-${total_width}s\n" | tr ' ' '-' | tee -a "$summary_file"
  echo "All repositories processed (Total elapsed time: ${total_elapsed_seconds} seconds)." | tee -a "$summary_file"

  echo -e "${GREEN}Summary saved to: ${summary_file}${NC}"
}

#-----------------------------------------
# Function: main
# Prompts for the release type, displays a list of repositories that will be processed
# (marking those with the skip flag), and asks the user to confirm whether to continue.
# Then, it loops through the JSON file and processes each repository that is not skipped.
#-----------------------------------------
main() {
  total_seconds=$SECONDS  # start of the whole process
  # Remember where we were executed from
  SCRIPT_DIR="$(pwd)"

  # Check for help option
  if [[ "${1:-}" == "-h" || "${1:-}" == "--help" || "${1:-}" == "?" ]]; then
    usage
  fi

  # Parse other command line arguments
  if [ -n "$1" ]; then
    RELEASE_TYPE="$1"
    RELEASE_TYPE=$(echo "$RELEASE_TYPE" | tr '[:lower:]' '[:upper:]')
  else
    echo "Enter release type (OFFICIAL or RC):"
    read -r RELEASE_TYPE
    RELEASE_TYPE=$(echo "$RELEASE_TYPE" | tr '[:lower:]' '[:upper:]')
  fi

  if [[ "$RELEASE_TYPE" != "OFFICIAL" && "$RELEASE_TYPE" != "RC" ]]; then
    echo -e "${RED}Invalid release type. Must be either OFFICIAL or RC.${NC}"
    echo
    usage
    exit 1
  fi

  # Second argument: JSON file name (default if not provided)
  json_file="${2:-createReleaseConfig.json}"
  if [ ! -f "$json_file" ]; then
    echo -e "${RED}JSON file $json_file not found.${NC}"
    echo
    usage
    exit 1
  fi

  # Third argument: wait time for mergeable check (default to 5 minutes)
  WAIT_TIME="${3:-300}"
  echo "Wait time for merges is $WAIT_TIME seconds"

  echo -e "${GREEN}Reading from $json_file${NC}"
  echo

  read_token

  # Read JSON data once and display the list of repos that will be processed
  json_data=$(cat "$json_file")
  repo_count=$(echo "$json_data" | jq length)

  echo -e "${GREEN}The following repositories will be processed:${NC}"
  for (( i=0; i<repo_count; i++ )); do
    repo_directory=$(echo "$json_data" | jq -r ".[$i].repo_directory")
    release=$(echo "$json_data" | jq -r ".[$i].release")
    # Read the skip flag (default to false)
    skip=$(echo "$json_data" | jq -r ".[$i].skip // false")
    if [ "$skip" = "true" ]; then
      echo "Repo: $repo_directory (Release: $release) (skipping)"
    else
      echo "Repo: $repo_directory (Release: $release)"
    fi
  done

  echo
  echo -n "Proceed with processing these repositories? (Y/N): "
  read -r confirm
  confirm=$(echo "$confirm" | tr '[:lower:]' '[:upper:]')
  if [ "$confirm" != "Y" ]; then
    echo "Aborting."
    exit 0
  fi

  # Loop through each repository and process it (skip if flag is true)
  for (( i=0; i<repo_count; i++ )); do
    repo_directory=$(echo "$json_data" | jq -r ".[$i].repo_directory")
    release=$(echo "$json_data" | jq -r ".[$i].release")

    release_notes=$(echo "$json_data" | jq -r ".[$i].release_notes")
    # Read the additional NGENCERF fields; default to empty if not present.
    ngencerf_version=$(echo "$json_data" | jq -r ".[$i].ngencerf_version // \"\"")
    ngencerf_date=$(echo "$json_data" | jq -r ".[$i].ngencerf_date // \"\"")
    has_submodules=$(echo "$json_data" | jq -r ".[$i].has_submodules // false")  # Default to false
    skip=$(echo "$json_data" | jq -r ".[$i].skip // false")  # Default to false

    # Expand tilde if present.
    if [[ $repo_directory == ~* ]]; then
      repo_directory="${repo_directory/#\~/$HOME}"
    fi

    if [ "$skip" = "true" ]; then
      echo -e "${YELLOW}Skipping repository: $repo_directory (Release: $release)${NC}"
      continue
    fi

    process_repo "$repo_directory" "$release" "$release_notes" "$ngencerf_version" "$ngencerf_date" "$has_submodules"

    # If user selected Quit, exit the loop
    if [ "$GLOBAL_RETURN_CODE" -eq 2 ]; then
      echo "User chose to quit. Exiting script."
      break
    fi
  done

  print_summary
}

main "$@"

