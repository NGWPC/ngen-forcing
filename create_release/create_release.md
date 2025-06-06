# Release Automation Script Documentation

This document describes how to use the provided Bash script to automate GitLab releases (both release candidates and official releases) across one or more repositories. It covers command-line options, the JSON configuration file format, and interactive prompts.

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [JSON Configuration File](#json-configuration-file)

   * [Required Fields](#required-fields)
   * [Optional Fields](#optional-fields)
   * [Sample JSON](#sample-json)
4. [Command-Line Usage](#command-line-usage)

   * [Positional Arguments](#positional-arguments)
   * [Default Values](#default-values)
   * [Help Flag](#help-flag)
5. [Script Behavior](#script-behavior)

   * [Release Types](#release-types)
   * [Submodule Handling](#submodule-handling)
   * [Interactive Prompts](#interactive-prompts)
6. [Detailed Steps per Repository](#detailed-steps-per-repository)

   1. [Determine Branches](#determine-branches)
   2. [Merge Requests and Tagging](#merge-requests-and-tagging)
   3. [Changelog Generation](#changelog-generation)
   4. [Create Release & Merge Back](#create-release-merge-back)
   5. [Cleanup & Summary](#cleanup-summary)
7. [Examples](#examples)
8. [Troubleshooting](#troubleshooting)

---

## Overview

This script automates the end-to-end release workflow for GitLab repositories, including:

* Creating merge requests (MRs) from one branch to another
* Waiting for merge requests to become mergeable
* Triggering merges via GitLab’s API
* Tagging releases (both release candidates and official releases)
* Generating changelogs for official releases
* Handling submodules (if applicable)
* Merging changes back into the appropriate branches
* Producing a summary report of successes/failures

The script reads a JSON file containing one or more repository configurations. For each entry, it:

1. Switches to the specified local `repo_directory` as specified in the Json file.
2. Decides on source/target branches based on `RELEASE_TYPE` (RC vs OFFICIAL).
3. Creates a merge request (unless it’s the first RC or an official release, in some cases).
4. Waits until the merge request is mergeable (polling GitLab).
5. Triggers the merge and monitors until it is merged.
6. Generates a changelog (only for OFFICIAL).
7. Creates a GitLab release tag (e.g., `v1.2` or `1.2-rc1`).
8. If RC (and not `-rc1`), merges back to `development`.
9. If submodules exist, repeats branch/merge process for each submodule.
10. Cleans up any temporary branches and prints a summary.

---

## Prerequisites

1. **Bash** (≥ 4.x) on a Unix-like system (e.g., Linux, macOS).

2. **`jq`** installed and available on `PATH` (used to parse/encode JSON).

3. **`curl`** (with TLS support).

4. A file `~/.gitlab_token` containing a valid GitLab [Personal Access Token](https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html) with API privileges.

   * The script reads this file to set `GITLAB_TOKEN`.
   * Ensure no extra whitespace or newline after the token.

5. A working Git repository in each `repo_directory` listed in the JSON file, with an `origin` remote pointing to your GitLab instance (e.g., `git@gitlab.sh.nextgenwaterprediction.com:…`).

6. Network access to the GitLab API (e.g., `https://gitlab.sh.nextgenwaterprediction.com/api/v4/`).

7. If any repository uses submodules, those submodules must already be initialized (`git submodule init && git submodule update`).

---

## JSON Configuration File

The script expects a JSON array (list) of objects. Each object represents one “release job” for a repository. The default filename is `createReleaseConfig.json` (unless overridden on the command line).

### Required Fields

* **`repo_directory`**

  * String path to the local clone of the GitLab repository.
  * Can use a tilde (`~`) prefix; the script will expand it to `$HOME`.
  * Example: `"~/projects/peter-test1"`.

* **`release`**

  * String base version (e.g., `"10.9"`, `"1.2"`).
  * For RCs, the script will automatically compute the next `-rcX` tag (e.g., `"10.9-rc1"`, `"10.9-rc2"`, etc.).
  * For OFFICIAL, it uses exactly what you provide (e.g., `"10.9"`).

* **`release_notes`**

  * String text that will be used as the “description” for the GitLab release (in the web UI).
  * Can include multiple lines if you wrap in JSON properly (e.g., use `\n`).
  * Example: `"Fixes for edge-case handling\n– Updated dependencies\n– Security patch"`.

### Optional Fields

* **`skip`** (boolean)

  * If `true`, the script will not process this repository and will show `(skipping)` in the interactive summary.
  * Defaults to `false` if omitted.

* **`ngencerf_version`** (string)

  * If provided, the script will inject this string into a `version.env` or similar file in the repo before tagging.
  * Used by repos that embed a separate “ngencerf” version.
  * If omitted or empty, no version injection is performed.
  * Used for the server only

* **`ngencerf_date`** (string)

  * If provided (e.g., `"2025-02-20"`), the script can write/update a `version.env` or metadata file with this date (format `YYYY-MM-DD`).
  * Omit if not needed.
  * Used for the server only

* **`has_submodules`** (boolean)

  * If `true`, the script will detect submodules via `.gitmodules`, check them out to the appropriate branch, and create a temporary MR in the parent repo to capture the submodule pointer updates.
  * Defaults to `false` if omitted.
  * If your repo does not have submodules or you do not want the script to adjust submodules, omit this field or set it to `false`.
  * The parent of the sub-modules (e.g., ngen) should be listed after all of the submodules

### Sample JSON

```json
[
  {
    "repo_directory": "~/projects/peter-test1",
    "release": "10.9",
    "release_notes": "Implement feature XYZ\nFixed bug #123",
    "ngencerf_version": "v2.0.0",
    "ngencerf_date": "2025-02-20"
  },
  {
    "repo_directory": "~/projects/peter-test-sub1",
    "release": "10.4",
    "release_notes": "Initial RC for module ABC",
    "skip": true
  },
  {
    "repo_directory": "~/projects/peter-test2",
    "release": "10.5",
    "release_notes": "Stabilize integration with other repos",
    "has_submodules": true
  }
]
```

* The first entry will create an **OFFICIAL** or **RC** (depending on command-line) release of version `10.9`, plus inject `v2.0.0` and `2025-02-20` into any `version.env` (if your repo expects it).
* The second entry is marked `"skip": true`, so the script will list it but will not process it.
* The third entry will process submodules (assuming `~/projects/peter-test2` has submodules).

---

## Command-Line Usage

```
./create_release.sh <RELEASE_TYPE> [JSON_FILE] [WAIT_TIME]
```

* `create_release.sh` is the name of the script (e.g., if you saved it as `create_release.sh`).
* You can also invoke it via `bash create_release.sh` or make it executable (`chmod +x create_release.sh`).

### Positional Arguments

1. **`RELEASE_TYPE`** (required)

   * Either `RC` or `OFFICIAL` (case-insensitive).
   * `RC` will generate a release candidate tag (`<release>-rcX`) and follow the RC workflow.
   * `OFFICIAL` will create an official release tag (`<release>`).

2. **`JSON_FILE`** (optional)

   * Path to your JSON configuration file.
   * Default: `createReleaseConfig.json` in the current directory.
   * Must be valid JSON array as described above.

3. **`WAIT_TIME`** (optional)

   * Number of seconds to wait for each merge request to become mergeable before prompting you.
   * Default: `300` (5 minutes).
   * If a merge request is still blocked after `WAIT_TIME`, the script prompts “Continue waiting (C) or Skip this repo (S)?”.

### Default Values

* If `JSON_FILE` is omitted, the script attempts to read `./createReleaseConfig.json`.
* If `WAIT_TIME` is omitted, it uses `300` (5 minutes) as the default poll timeout.

### Help Flag

```
./create_release.sh --help
```

or

```
./create_release.sh -h
```

or

```
./create_release.sh ?
```

Any of the above will print a usage summary and exit. The usage summary includes:

* Synopsis: `Usage: create_release.sh <RELEASE_TYPE> [JSON_FILE] [WAIT_TIME]`
* Description of RC vs OFFICIAL workflows.
* Explanation of arguments and defaults.
* Example call (e.g., `create_release.sh RC release_config.json 300`).

---

## Script Behavior

Below is a high-level overview of what the script does, focusing on the user-facing steps and interactive prompts.

### Release Types

1. **RC (Release Candidate) Process**

   * If this is the first RC for a given `release` (e.g., no tags matching `10.9-rc*`), it:

     1. Merges `development → release-candidate`.
     2. Optionally updates submodules (if `has_submodules: true`).
     3. Creates GitLab release with tag `10.9-rc1` (or `10.9-rc2`, etc.).
     4. Merges `release-candidate → development` (except for `rc1`; only for subsequent RCs).

   * For subsequent RCs for the same `release` (e.g., `10.9-rc2`, `10.9-rc3`):

     1. It skips the initial merge from `development` (assuming `release-candidate` already has those commits).
     2. Still tags the existing `release-candidate` branch with the new `-rcX`.
     3. Merges `release-candidate → development` upon completion.

2. **OFFICIAL Release Process**

   * Merges `release-candidate → main` (or `master`) (detects which exists).
   * Optionally updates submodules on `main/master`.
   * Creates a GitLab release tag (e.g., `10.9`).
   * Merges those final changes back into `development`.

> **Note:** The script detects whether your repo uses `main` or `master` by querying the GitLab API. If neither exists, it reports an error and skips that repo.

### Submodule Handling

* If an entry’s JSON object has `"has_submodules": true`, the script will:

  1. Read `.gitmodules` to list submodule paths.
  2. For each submodule:

     * Check out the appropriate branch (`release-candidate`, `development`, or `main/master`).
     * Run `git pull` in that submodule.
  3. In the parent repository, create a temporary branch named `temp_submodules_<target>_<RELEASE_NUMBER>`.
  4. Commit the updated submodule pointers on that temporary branch.
  5. Open a merge request (`temp_submodules_… → <target_branch>`), wait until mergeable, then trigger the merge.
  6. Delete the temporary branch locally and remotely after merging.

If a submodule does not have `main` or `master`, it prints an error and skips that submodule.

### Interactive Prompts

1. **Initial Confirmation**

   * After reading the JSON file and listing each repo (with `(skipping)` flagged accordingly), the script prompts:

     ```
     Proceed with processing these repositories? (Y/N):
     ```
   * `Y` (or `y`): continue.
   * `N` (or `n`): abort the entire script (exit).

2. **Per-Repo Confirmation (before creating the actual GitLab release)**

   * Right before “Creating official GitLab release for …” (or right before tagging an RC), the script pauses and prompts:

     ```
     Proceed with the actual GitLab <RELEASE_TYPE> release for <REPO_PROJECT>? (Y)es, (N)o, (Q)uit:
     ```
   * `Y`: proceed for this repo.
   * `N`: skip this repo (mark it “FAILED” in summary).
   * `Q`: quit the entire script immediately.

3. **Merge Request Polling Timeout**

   * If a MR does not become mergeable within `WAIT_TIME` seconds (default 300 s), the script prompts:

     ```
     Merge request <MR_ID> is still not mergeable. (C)ontinue waiting, (S)kip this repo:
     ```
   * `C`: reset the timer and keep waiting.
   * `S`: skip this repository (mark as failed) and move on.

---

## Detailed Steps per Repository

Below is a breakdown of what happens internally when `process_repo` is invoked for each non-skipped entry:

### 1. Determine Branches

* The script reads `"release": "<base>"`.
* If `RELEASE_TYPE="RC"`, it calls `get_next_rc_number("<base>")` (e.g., `10.9 → 10.9-rc1`).
* If `RELEASE_TYPE="OFFICIAL"`, it uses `<base>` verbatim (e.g., `10.9`).
* It checks for existing tags on the remote (`git ls-remote --tags origin`).

  * If that tag already exists, it errors out and skips the repo.
* It determines:

  * For RC:

    * `SOURCE_BRANCH="development"`
    * `TARGET_BRANCH="release-candidate"`
  * For OFFICIAL:

    * `SOURCE_BRANCH="release-candidate"`
    * `TARGET_BRANCH` is detected dynamically via `determine_release_branch()`, which queries GitLab’s API for `main` or `master`.

### 2. Merge Requests and Tagging

1. **Initial MR (if RC1 or OFFICIAL)**

   * If `RC` and tag ends with `-rc1`, create an MR `development → release-candidate`.
   * If `OFFICIAL`, create an MR `release-candidate → <main or master>`.
   * Uses `execute_merge_request()` which:

     * Does a local merge test on a temporary branch to catch conflicts early.
     * If no conflicts, calls `create_merge_request()` (via GitLab API) to open a MR.
     * Calls `wait_until_mergeable()` to poll the MR until it is mergeable (checks both `merge_status == "can_be_merged"` and `detailed_merge_status == "mergeable"`).
     * Once mergeable, calls `trigger_merge()` to merge the MR via API.
     * Monitors until `state == "merged"`.

2. **Subsequent RCs**

   * If `-rcX` where `X > 1`, skip creating the first MR (`development → release-candidate`) because those commits should already be on `release-candidate`.
   * Still tag the existing `release-candidate` branch with the new `-rcX` tag.

### 3. Changelog Generation (OFFICIAL Only)

* If `RELEASE_TYPE="OFFICIAL"`, after merging `release-candidate` into `main/master`, it calls `generate_changelog()`.

  * Finds the most recent “official” tag matching `^[0-9]+\.[0-9]+$` (skips any `-rc*`).
  * Computes the commit range from that tag to `HEAD`.
  * Writes a file in `./changelogs/<repo_name>_<RELEASE_NUMBER>_changelog.txt` containing:

    ```
    ## Changelog for <repo> <RELEASE_NUMBER> (<commit_date>)

    <list of commit messages (one line each, excluding merges), in chronological order>
    ```
  * Prints “Changelog saved to …” in green.

### 4. Create Release & Merge Back

1. **Interactive Confirmation**

   * Prompt:

     ```
     Proceed with the actual GitLab <RELEASE_TYPE> release for <REPO_PROJECT>? (Y)es, (N)o, (Q)uit:
     ```

2. **Create GitLab Release**

   * Calls `create_release("<API_URL>", "<RELEASE_NUMBER>", "Release <RELEASE_NUMBER>", "<release_notes>", "<TARGET_BRANCH>")`
   * If successful (HTTP 2xx), prints in green “Release created successfully.”
   * If failed, prints error in red and marks this repo as failed in the summary.

3. **Merge Back into Development (RC Except RC1)**

   * If `RELEASE_TYPE="RC"` and `<RELEASE_NUMBER>` is *not* `-rc1`, then create an MR `release-candidate → development`.
   * If `RELEASE_TYPE="OFFICIAL"`, after creating the release, it always merges `main/master → development` so that any hotfixes included in the official tag are propagated forward.

4. **Submodule Branch Reset**

   * If `has_submodules=true`, after the above merges, it calls `process_submodules("development")` to ensure all submodules are now on `development`.

### 5. Cleanup & Summary

1. **Branch Cleanup**

   * `cleanup_repo()` is registered via `trap` so it always runs when `process_repo` exits.
   * It:

     * Checks out `development` and pulls the latest.
     * Captures the latest commit hash.
     * Records status (`SUCCESS` or `FAILED`), elapsed time, and commit hash into a global associative array (`repo_status[<path>]`).
     * Iterates over any temporary branches stored in `TEMP_BRANCHES[]` and deletes them both locally (`git branch -D`) and remotely (`git push origin --delete`).
     * Appends the repo to `repo_order[]`.
2. **Global Summary**

   * After all repos are processed (or the user chooses to quit), the script calls `print_summary()`.
   * It prints a formatted table:

     ```
     Repository                | Release       | Status     | Time   | Commit Hash
     ----------------------------------------------------------------------------------------
     ~/projects/peter-test1   | 10.9-rc1      | SUCCESS    |  42s   | abcdef1234567890...
     ~/projects/peter-test2   | 10.5          | FAILED     |  30s   | 123456abcdef7890...
     ...
     ----------------------------------------------------------------------------------------
     All repositories processed (Total elapsed time: 75 seconds).
     ```
   * It also writes the same output to `release_summary.txt` in the script’s original working directory.

---

## Examples

1. **Basic RC Release with Default JSON File and Default Wait Time**

   ```bash
   ./create_release.sh RC
   ```

   * Reads `./createReleaseConfig.json`.
   * Uses `300s` (5 minutes) as `WAIT_TIME`.
   * Prompts for each interactive confirmation.

2. **Official Release with Custom JSON File**

   ```bash
   ./create_release.sh OFFICIAL my_repos.json
   ```

   * Reads `my_repos.json`.
   * Uses default `WAIT_TIME=300s`.
   * For each entry not marked `"skip": true`, merges `release-candidate → main`, generates changelog, and tags.

3. **RC Release with 10-Minute Wait Time**

   ```bash
   ./create_release.sh RC createReleaseConfig.json 600
   ```

   * Same as example 1, but waits up to 600 seconds for each MR to become mergeable.

4. **Help Invocation**

   ```bash
   ./create_release.sh --help
   ```

   * Prints usage and exits.

---

## Troubleshooting

* **JSON File Not Found / Invalid JSON**

  * If `JSON_FILE` does not exist, you’ll see:

    ```
    JSON file <filename> not found.
    ```

    and the script exits with usage information.
  * If the JSON is syntactally invalid, `jq length` will fail. Double-check your JSON with `jq . myfile.json`.

* **Missing `~/.gitlab_token`**

  * If no `~/.gitlab_token` is present, `GITLAB_TOKEN` will be empty.
  * API calls to GitLab will return `401 Unauthorized` or `404 Not Found`.
  * Ensure `~/.gitlab_token` contains exactly your GitLab personal token (no extra newline or spaces).

* **Target Branch (`main` or `master`) Not Found**

  * If neither `main` nor `master` exists in the remote, you’ll see:

    ```
    Error: Neither 'main' nor 'master' branch found in repository ...
    ```
  * Confirm your default branch name (e.g., `master` vs `main`) and update accordingly.

* **Merge Conflicts Detected Locally**

  * The script does a local `git merge --no-commit --no-ff origin/<source>` test in a temporary branch.
  * If conflicts are detected, it aborts the merge test and prints:

    ```
    Merge conflicts detected between <source> and <target>. Merge request will not be created.
    ```
  * Resolve conflicts manually in your local `development` or `release-candidate` branch, commit, push, and then re-run the script.

* **“Merge request cannot be completed – either no changes to merge or a conflict”**

  * If the API’s `detailed_merge_status` contains `broken_status`, it indicates either there truly are no changes remaining to merge (e.g., everything is already up to date), or a conflict is blocking the MR.
  * In that case, you may skip or continue waiting. If truly “no changes,” it’s safe to skip.

* **Skipping Repositories**

  * If you accidentally marked a repo with `"skip": true`, it will be listed as “(skipping)” during the initial summary.
  * To include it, remove `skip` or set it to `false` in the JSON.

* **Submodule Errors**

  * If a submodule lacks both `main` and `master`, you will see a red error line:

    ```
    Error: Neither 'main' nor 'master' branch found in submodule <path>.
    ```
  * Make sure your submodules use a recognized default branch, or set `"has_submodules": false`.

---

