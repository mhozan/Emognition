#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Build the Emognition standalone (one-folder bundle) with PyInstaller.
#
# Usage:  scripts/build_executable.sh
# Output: dist/emognition/emognition   (a folder; zip it to distribute)
#
# Run this on EACH target OS to get that OS's binary -- PyInstaller does not
# cross-compile (a Linux build runs on Linux only, etc.).
set -euo pipefail

cd "$(dirname "$0")/.."

PY=".venv/bin/python"
[ -x "$PY" ] || { echo "No .venv found. See README setup."; exit 1; }

echo "Building Emognition standalone with PyInstaller..."
"$PY" -m PyInstaller --noconfirm emognition.spec

echo
echo "Built: dist/emognition"
du -sh dist/emognition || true
echo "Verify the bundle (headless) with:"
echo "    ./dist/emognition/emognition --selfcheck"
