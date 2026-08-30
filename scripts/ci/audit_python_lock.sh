#!/usr/bin/env bash
set -euo pipefail

requirements_file="$(mktemp -t wp01-python-audit.XXXXXX)"
trap 'rm -f "${requirements_file}"' EXIT

uv export \
  --quiet \
  --frozen \
  --all-packages \
  --all-groups \
  --no-emit-workspace \
  --no-emit-local \
  --no-hashes \
  --output-file "${requirements_file}"
uv run pip-audit --strict --desc --requirement "${requirements_file}"
