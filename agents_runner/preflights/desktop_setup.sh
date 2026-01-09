#!/usr/bin/env bash
set -euo pipefail

echo "[desktop/setup][INFO] Configuring desktop environment for Docker image"

# Create base directories with proper permissions
echo "[desktop/setup][INFO] Creating base directories..."
mkdir -p /tmp/agents-runner-desktop
mkdir -p /tmp/agents-artifacts
chmod 1777 /tmp/agents-runner-desktop
chmod 1777 /tmp/agents-artifacts

# Discover and save noVNC path
echo "[desktop/setup][INFO] Discovering noVNC web root..."
NOVNC_WEB=""
for candidate in "/usr/share/webapps/novnc" "/usr/share/novnc" "/usr/share/noVNC"; do
  if [ -d "${candidate}" ]; then
    NOVNC_WEB="${candidate}"
    break
  fi
done

if [ -z "${NOVNC_WEB}" ]; then
  echo "[desktop/setup][ERROR] noVNC web root not found in expected locations" >&2
  echo "[desktop/setup][ERROR] Searched: /usr/share/webapps/novnc, /usr/share/novnc, /usr/share/noVNC" >&2
  exit 1
fi

echo "[desktop/setup][INFO] Found noVNC at: ${NOVNC_WEB}"
echo "[desktop/setup][INFO] Saving noVNC path to /etc/default/novnc-path..."
sudo mkdir -p /etc/default
echo "NOVNC_WEB=${NOVNC_WEB}" | sudo tee /etc/default/novnc-path > /dev/null
sudo chmod 644 /etc/default/novnc-path

# Set environment defaults
echo "[desktop/setup][INFO] Setting environment defaults in /etc/profile.d/desktop-env.sh..."
sudo mkdir -p /etc/profile.d
sudo tee /etc/profile.d/desktop-env.sh > /dev/null <<'EOF'
# Desktop environment defaults
export DISPLAY="${DISPLAY:-:1}"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp/xdg-$(id -un)}"
EOF
sudo chmod 644 /etc/profile.d/desktop-env.sh

echo "[desktop/setup][INFO] Desktop environment setup complete"
echo "[desktop/setup][INFO] noVNC path: ${NOVNC_WEB}"
