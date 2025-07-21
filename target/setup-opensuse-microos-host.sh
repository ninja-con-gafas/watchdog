#!/bin/bash

# Script to configure a restricted SSH user 'gatekeeper' for remote shutdown.
#
# Performs the following steps:
# 1. Creates the user 'gatekeeper' if not already present.
# 2. Sets up a command-restricted SSH key to allow only 'shutdown now'.
# 3. Restricts shell access and disables unnecessary SSH capabilities.
# 4. Grants passwordless shutdown rights to 'gatekeeper' using sudoers.
#
# Must be run with root privileges.

set -euo pipefail

# Check for root privileges
if [[ "$EUID" -ne 0 ]]; then
  echo "Please run this script with sudo or as root."
  exit 1
fi

USERNAME="gatekeeper"
AUTHORIZED_KEYS_DIR="/home/${USERNAME}/.ssh"
AUTHORIZED_KEYS_FILE="${AUTHORIZED_KEYS_DIR}/authorized_keys"
SUDOERS_FILE="/etc/sudoers.d/gatekeeper-shutdown"

# Function: Print error message and exit
abort() {
  echo "Error: $*" >&2
  exit 1
}

echo "[1/4] Reading SSH public key for command-restricted access"
read -rp "Paste the public SSH key to authorise for shutdown-only access: " SSH_KEY
SSH_KEY="$(echo "${SSH_KEY}" | tr -d '\r\n')"

RESTRICTED_KEY="command=\"sudo /sbin/shutdown now\",no-pty,no-agent-forwarding,no-X11-forwarding ${SSH_KEY}"

# Sanity check for public key format
if ! echo "${SSH_KEY}" | grep -qE '^ssh-(rsa|ed25519|ecdsa) '; then
  abort "Invalid SSH public key format."
fi

transactional-update run bash -eux <<EOT
echo "[2/4] Checking if user '${USERNAME}' exists"
if ! id "${USERNAME}" &>/dev/null; then
  echo "Creating system user '${USERNAME}'"
  useradd --system --create-home --shell /bin/bash "${USERNAME}" || abort "Failed to create user '${USERNAME}'"
else
  echo "User '${USERNAME}' already exists."
fi

echo "[3/4] Configuring SSH authorized_keys with command restriction"
mkdir -p "${AUTHORIZED_KEYS_DIR}"
chmod u=rwx,go= "${AUTHORIZED_KEYS_DIR}"
touch "${AUTHORIZED_KEYS_FILE}"
chmod u=rw,go= "${AUTHORIZED_KEYS_FILE}"
chown -R "${USERNAME}:${USERNAME}" "${AUTHORIZED_KEYS_DIR}"

# Append restricted key if not already present
if ! grep -Fq "${SSH_KEY}" "${AUTHORIZED_KEYS_FILE}"; then
  echo "${RESTRICTED_KEY}" >> "${AUTHORIZED_KEYS_FILE}"
  echo "SSH key added with sudo-prefixed shutdown command restriction."
else
  echo "SSH key already configured."
fi

echo "[4/4] Configuring sudoers for passwordless shutdown"
echo "${USERNAME} ALL=(ALL) NOPASSWD: /sbin/shutdown" > "${SUDOERS_FILE}"
chmod u=rw,g=r,o= "${SUDOERS_FILE}"

# Validate the sudoers file before applying
if ! visudo -c -f "${SUDOERS_FILE}"; then
  abort "Syntax error in sudoers file: ${SUDOERS_FILE}"
fi
EOT

echo "Setup complete. User '${USERNAME}' can now shut down the system via restricted SSH."
echo "Reboot to apply changes."
sleep 10
reboot