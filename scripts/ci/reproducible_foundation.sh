#!/usr/bin/env bash
set -euo pipefail

artifact_dir="${1:-artifacts/reproducibility}"

python3 scripts/ci/rebuild_foundation.py --artifact-dir "${artifact_dir}"
