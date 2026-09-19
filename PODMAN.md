# Podman Support (Additive Path)

This repository maintains Docker as its primary documented and production CI path. Podman is supported as an **additional** option for local development, rootless execution, and container build/smoke verification.

Existing Docker workflows (`.github/workflows/cicd.yml`) and production release tags remain untouched and active.

---

## Prerequisites

Verify that Podman is installed on your workstation:

```bash
podman version
podman info
```

For Ubuntu 24.04+ (Noble) or RHEL 8/9, Podman 4.9+ is recommended.

---

## Registry Authentication

`Dockerfile.bmi-forcings` builds from `ghcr.io/ngwpc/ngen-dependencies-bookworm:latest`. Ensure you are logged in to GHCR before building:

```bash
echo "<GITHUB_PAT_OR_TOKEN>" | podman login ghcr.io -u "<GITHUB_USERNAME>" --password-stdin
```

---

## Building with Podman

### NextGen BMI Forcing (`Dockerfile.bmi-forcings`)

Build the image directly using `Dockerfile.bmi-forcings`. Following NOAA-OWP/WRES conventions, use `--format docker` to ensure standard OCI/Docker compatibility:

```bash
podman build \
  --ulimit nofile=65535:65535 \
  --format docker \
  -f Dockerfile.bmi-forcings \
  -t local/ngen-bmi-forcing:podman-test \
  .
```

*Note: The Dockerfile uses BuildKit syntax (`--mount=type=cache`) for pip caching. Modern Podman (via Buildah $\ge$ 1.24) natively resolves cache mounts locally without requiring a Docker daemon. The `--ulimit nofile=65535:65535` flag ensures sufficient file descriptors are available during package installations.*

---

## Smoke Verification

### 1. Test Entrypoint & Bash Execution
```bash
podman run --rm local/ngen-bmi-forcing:podman-test -c "echo 'Entrypoint functional' && /bin/bash --version"
```

### 2. Verify Python Environment & Dependencies
Test that `NextGen_Forcings_Engine` and `ewts` are installed and importable:
```bash
podman run --rm local/ngen-bmi-forcing:podman-test -c "python --version && python -c 'import NextGen_Forcings_Engine, ewts; print(\"Packages healthy:\", NextGen_Forcings_Engine.__version__)'"
```

### 3. Verify Provenance Metadata
```bash
podman run --rm local/ngen-bmi-forcing:podman-test -c "cat /ngen-app/ngen-bmi-forcing_git_info.json && test -s /ngen-app/ngen-bmi-forcing_git_info.json"
```

---

## CI / Automation

* **Workflow:** `.github/workflows/podman-smoke.yml`
* **Triggers:** Manual (`workflow_dispatch`) and automated checks on pull requests modifying container/source files (`Dockerfile.bmi-forcings`, `pyproject.toml`, `NextGen_Forcings_Engine_BMI/**`, `Forcing_Extraction_Scripts/**`, `ESMF_Mesh_Domain_Configuration_Production/**`).
* **Runner Environment:** Pinned to `ubuntu-24.04`.
* **Registry Policy:** By default, builds remain local to the runner. When `push_images=true` is dispatched, only `:podman-test` and `:<sha>-podman-test` tags are published to GHCR under `ghcr.io/<repo>/ngen-bmi-forcing`. Production aliases (`:latest`, release tags) are never touched.
