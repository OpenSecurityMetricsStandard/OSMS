#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Build only; no tag creation, upload or publication.
set -euo pipefail
python3 tools/build_release_bundle.py "${1:?usage: make_checksums.sh vX.Y.Z-draft}"
