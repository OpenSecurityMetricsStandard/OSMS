#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Creates the release bundle + SHA-256 checksums for a tagged OSMS release.
# Run from the repo root:   bash tools/make_checksums.sh v0.9.0
#
# Output (attach all three to the GitHub release):
#   release/osms-<tag>-catalog.zip   normative artifacts, frozen
#   release/SHA256SUMS.txt           checksum of the bundle  -> users verify with: sha256sum -c SHA256SUMS.txt
#   release/MANIFEST-SHA256.txt      per-file record (paths relative to repo root) for the audit trail
#
# Optional signature (after GPG/SSH signing is set up):
#   gpg --armor --detach-sign release/SHA256SUMS.txt   -> attach SHA256SUMS.txt.asc as well
set -euo pipefail
TAG="${1:?usage: make_checksums.sh vX.Y.Z}"
OUT="release"; mkdir -p "$OUT"
ZIP="$OUT/osms-$TAG-catalog.zip"; rm -f "$ZIP"
FILES=""
for f in catalog schema LICENSE LICENSE-CODE NOTICE README.md CHANGELOG.md REVIEW_PROCESS.md; do
  [ -e "$f" ] && FILES="$FILES $f"
done
# shellcheck disable=SC2086
zip -qr "$ZIP" $FILES
( cd "$OUT" && sha256sum "$(basename "$ZIP")" > SHA256SUMS.txt )
find catalog schema -type f \( -name '*.yaml' -o -name '*.yml' -o -name '*.json' \) -print0 \
  | sort -z | xargs -0 sha256sum > "$OUT/MANIFEST-SHA256.txt"
echo "-> $ZIP"
echo "-> $OUT/SHA256SUMS.txt"
echo "-> $OUT/MANIFEST-SHA256.txt"
