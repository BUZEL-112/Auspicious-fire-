#!/usr/bin/env bash
# ==============================================================================
# Fetch the curated demo wardrobe release and install it into the repository.
#
# Downloads the pinned GitHub Release asset, verifies its SHA-256, and replaces:
#   data/demo_wardrobe/{images,store,sources.json,ATTRIBUTION.md}
#   tests/dummy/dummy_wardrobes.json
#   data/store_catalog.json
#
# Nothing is changed unless the download and checksum both succeed. The repository
# already ships the same files, so a failed fetch leaves a working demo in place.
#
# Usage (from anywhere inside the repo):  bash scripts/fetch_demo_wardrobe.sh
# ==============================================================================
set -euo pipefail

RELEASE_TAG="demo-wardrobe-v1"
ASSET_NAME="demo-wardrobe-v1.zip"
ASSET_SHA256="85ef13783edc28ac0ee1393ee953ac81b659f93b563b685b00c433c8aa26e009"
ASSET_URL="https://github.com/BUZEL-112/Auspicious-fire-/releases/download/${RELEASE_TAG}/${ASSET_NAME}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

echo "Fetching ${RELEASE_TAG} from ${ASSET_URL}"
if command -v curl &>/dev/null; then
    curl -fsSL --retry 3 -o "$WORK_DIR/$ASSET_NAME" "$ASSET_URL"
else
    wget -q -O "$WORK_DIR/$ASSET_NAME" "$ASSET_URL"
fi

ACTUAL_SHA256="$(sha256sum "$WORK_DIR/$ASSET_NAME" | cut -d' ' -f1)"
if [ "$ACTUAL_SHA256" != "$ASSET_SHA256" ]; then
    echo "ERROR: checksum mismatch for ${ASSET_NAME}" >&2
    echo "  expected ${ASSET_SHA256}" >&2
    echo "  actual   ${ACTUAL_SHA256}" >&2
    echo "Keeping the demo wardrobe already in the repository." >&2
    exit 1
fi
echo "Checksum OK."

python3 -m zipfile -e "$WORK_DIR/$ASSET_NAME" "$WORK_DIR/extract"
SRC="$WORK_DIR/extract/demo-wardrobe"
for required in images store sources.json ATTRIBUTION.md dummy_wardrobes.json store_catalog.json; do
    if [ ! -e "$SRC/$required" ]; then
        echo "ERROR: release asset is missing '${required}'. Nothing was changed." >&2
        exit 1
    fi
done

DEST="$REPO_ROOT/data/demo_wardrobe"
mkdir -p "$DEST"
rm -rf "$DEST/images" "$DEST/store"
cp -r "$SRC/images" "$SRC/store" "$DEST/"
cp "$SRC/sources.json" "$SRC/ATTRIBUTION.md" "$DEST/"
cp "$SRC/dummy_wardrobes.json" "$REPO_ROOT/tests/dummy/dummy_wardrobes.json"
cp "$SRC/store_catalog.json" "$REPO_ROOT/data/store_catalog.json"

echo "Installed ${RELEASE_TAG}: $(ls "$DEST/images" | wc -l) photos, $(ls "$DEST/store" | wc -l) silhouettes."
