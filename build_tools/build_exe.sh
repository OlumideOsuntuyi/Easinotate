#!/usr/bin/env bash
# ============================================================
#   Easinotate - Linux / macOS build script
# ============================================================
#   Run from the project root:
#       bash build_tools/build_exe.sh
# ============================================================

set -euo pipefail

# cd to project root (parent of the script's directory)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/.."

echo
echo "=== Easinotate build ==="
echo

if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 not found on PATH. Install Python 3.9+ and try again." >&2
    exit 1
fi

echo "[1/4] Installing build dependencies..."
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements-dev.txt

echo
echo "[2/4] Cleaning previous build artifacts..."
rm -rf build dist

echo
echo "[3/4] Running PyInstaller..."
python3 -m PyInstaller --clean build_tools/easinotate.spec

echo
echo "[4/4] Done."
echo

if [[ -f dist/Easinotate ]]; then
    echo "SUCCESS: dist/Easinotate"
    ls -lh dist/Easinotate
elif [[ -d dist/Easinotate.app ]]; then
    echo "SUCCESS: dist/Easinotate.app"
    ls -ld dist/Easinotate.app
else
    echo "WARNING: expected dist/Easinotate not found."
    ls -la dist/ || true
fi
