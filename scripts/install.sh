#!/usr/bin/env bash
# =============================================================================
# FILE PURPOSE:
# This is the 1-click SDK installation script.
# It unpacks the pre-built 'timeguard-pvm-sdk.tar.gz' archive into '/opt/timeguard-pvm'
# and creates the global system symlink '/usr/local/bin/timeguard-python' so you can
# run TimeGuard from any terminal directory.
# Run it with:
#   bash scripts/install.sh
# =============================================================================

# Exit immediately if a command exits with a non-zero status (-e),
# treat unset variables as an error (-u), and propagate pipeline errors (-o pipefail)
set -euo pipefail

# Determine the absolute directory where this installer script resides
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Define potential locations for the SDK tarball
# Check same directory first, then parent directory, then user home
if [ -f "${SCRIPT_DIR}/timeguard-pvm-sdk.tar.gz" ]; then
    TARBALL="${SCRIPT_DIR}/timeguard-pvm-sdk.tar.gz"
elif [ -f "${SCRIPT_DIR}/../timeguard-pvm-sdk.tar.gz" ]; then
    TARBALL="${SCRIPT_DIR}/../timeguard-pvm-sdk.tar.gz"
elif [ -f "${HOME}/pvm-timeguard/timeguard-pvm-sdk.tar.gz" ]; then
    TARBALL="${HOME}/pvm-timeguard/timeguard-pvm-sdk.tar.gz"
else
    echo "Error: timeguard-pvm-sdk.tar.gz not found!" >&2
    echo "Searched locations:" >&2
    echo "  - ${SCRIPT_DIR}/timeguard-pvm-sdk.tar.gz" >&2
    echo "  - ${SCRIPT_DIR}/../timeguard-pvm-sdk.tar.gz" >&2
    echo "  - ${HOME}/pvm-timeguard/timeguard-pvm-sdk.tar.gz" >&2
    exit 1
fi

echo "============================================================"
echo "Installing TimeGuard-PVM SDK"
echo "Package: ${TARBALL}"
echo "Target:  /opt/timeguard-pvm"
echo "============================================================"

# Step 1: Ensure destination directory exists and extract the archive
echo "[1/3] Extracting TimeGuard-PVM runtime into /opt/timeguard-pvm..."
sudo mkdir -p /opt
sudo tar -xzf "$TARBALL" -C /opt

# Step 2: Establish the global executable symlink in /usr/local/bin
echo "[2/3] Linking /usr/local/bin/timeguard-python..."
sudo mkdir -p /usr/local/bin
sudo ln -sf /opt/timeguard-pvm/bin/python3.16 /usr/local/bin/timeguard-python

# Step 3: Run quick verification check
echo "[3/3] Verifying runtime execution..."
/usr/local/bin/timeguard-python -c "import sys; print(f'Verification Successful: {sys.version}')"

echo ""
echo "============================================================"
echo "TimeGuard-PVM successfully installed!"
echo "Run 'timeguard-python --version' to test."
echo "============================================================"
