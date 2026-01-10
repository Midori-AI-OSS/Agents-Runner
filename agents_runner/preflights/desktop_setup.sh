#!/usr/bin/env bash
set -euo pipefail

# Source common log functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/log_common.sh"

log_info desktop setup "Configuring desktop environment for Docker image"

# Create base directories with proper permissions
log_info desktop setup "Creating base directories..."
mkdir -p /tmp/agents-runner-desktop
mkdir -p /tmp/agents-artifacts
chmod 1777 /tmp/agents-runner-desktop
chmod 1777 /tmp/agents-artifacts

# Discover and save noVNC path
log_info desktop setup "Discovering noVNC web root..."
NOVNC_WEB=""
for candidate in "/usr/share/webapps/novnc" "/usr/share/novnc" "/usr/share/noVNC"; do
  if [ -d "${candidate}" ]; then
    NOVNC_WEB="${candidate}"
    break
  fi
done

if [ -z "${NOVNC_WEB}" ]; then
  log_error desktop setup "noVNC web root not found in expected locations" >&2
  log_error desktop setup "Searched: /usr/share/webapps/novnc, /usr/share/novnc, /usr/share/noVNC" >&2
  exit 1
fi

log_info desktop setup "Found noVNC at: ${NOVNC_WEB}"
log_info desktop setup "Saving noVNC path to /etc/default/novnc-path..."
sudo mkdir -p /etc/default
echo "NOVNC_WEB=${NOVNC_WEB}" | sudo tee /etc/default/novnc-path > /dev/null
sudo chmod 644 /etc/default/novnc-path

# Set environment defaults
log_info desktop setup "Setting environment defaults in /etc/profile.d/desktop-env.sh..."
sudo mkdir -p /etc/profile.d
sudo tee /etc/profile.d/desktop-env.sh > /dev/null <<'EOF'
# Desktop environment defaults
export DISPLAY="${DISPLAY:-:1}"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp/xdg-$(id -un)}"
EOF
sudo chmod 644 /etc/profile.d/desktop-env.sh

log_info desktop setup "Desktop environment setup complete"
log_info desktop setup "noVNC path: ${NOVNC_WEB}"
