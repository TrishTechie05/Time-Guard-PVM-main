#!/usr/bin/env bash
# =============================================================================
# FILE PURPOSE:
# This is the end-to-end build automation script.
# It compiles TimeGuard-PVM completely from source:
#   1. Clones a shallow copy of the CPython repository (if missing).
#   2. Runs 'patch_cpython.py' to inject the C-level monotonic clock checks.
#   3. Runs './configure --prefix=/opt/timeguard-pvm --disable-test-modules'.
#   4. Compiles with all CPU cores ('make -j$(nproc)').
#   5. Installs the runtime via 'sudo make altinstall' to avoid breaking system python.
#   6. Packages the installed runtime into 'timeguard-pvm-sdk.tar.gz' for distribution.
# Run it with:
#   bash scripts/build.sh
# =============================================================================

set -euo pipefail

WORKSPACE_DIR="${HOME}/pvm-timeguard"
CPYTHON_SRC="${WORKSPACE_DIR}/cpython-src"
INSTALL_PREFIX="/opt/timeguard-pvm"
TARBALL_DEST="${WORKSPACE_DIR}/timeguard-pvm-sdk.tar.gz"

echo "============================================================"
echo "Starting TimeGuard-PVM End-to-End Build"
echo "============================================================"

# Step 1: Create isolated build directory
mkdir -p "$WORKSPACE_DIR"
cd "$WORKSPACE_DIR"

# Step 2: Clone shallow CPython if missing
if [ ! -d "$CPYTHON_SRC" ]; then
    echo "[1/6] Cloning CPython source..."
    git clone --depth 1 https://github.com/python/cpython.git cpython-src
else
    echo "[1/6] CPython source already exists at ${CPYTHON_SRC}"
fi

# Step 3: Run the Python patcher script
echo "[2/6] Applying TimeGuard-PVM modifications..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "${SCRIPT_DIR}/patch_cpython.py" "$CPYTHON_SRC"

# Step 4: Configure CPython build
echo "[3/6] Running ./configure for ${INSTALL_PREFIX}..."
cd "$CPYTHON_SRC"
./configure --prefix="$INSTALL_PREFIX" --disable-test-modules

# Step 5: Compile with all CPU cores
echo "[4/6] Compiling CPython with $(nproc) cores..."
make -j"$(nproc)"

# Step 6: Install isolated build into /opt/timeguard-pvm
echo "[5/6] Installing runtime to ${INSTALL_PREFIX}..."
sudo make altinstall

# Step 7: Package SDK tarball
echo "[6/6] Packaging into ${TARBALL_DEST}..."
sudo tar -czf "$TARBALL_DEST" -C /opt timeguard-pvm
sudo chown "$(id -u):$(id -g)" "$TARBALL_DEST"

# Link global command
sudo ln -sf "${INSTALL_PREFIX}/bin/python3.16" /usr/local/bin/timeguard-python

echo "============================================================"
echo "TimeGuard-PVM build and packaging completed successfully!"
echo "Package available at: ${TARBALL_DEST}"
echo "============================================================"
