#!/bin/bash

set -e

# Script to configure Proxmox API user, token, and permissions for remote shutdown
#
# This script:
# 1. Creates a Proxmox user 'gatekeeper' in the 'pve' realm.
# 2. Creates a custom role 'gatekeeper' with 'Sys.PowerMgmt' only.
# 3. Creates a group 'gatekeeper' and assigns the role to it.
# 4. Adds the user to the group.
# 5. Generates and outputs a token and secret for API usage.
#
# Must be run directly on the Proxmox host with root privileges.

# Configuration
USERNAME="gatekeeper"
REALM="pve"
ROLE="gatekeeper"
GROUP="gatekeeper"
TOKEN_ID="shutdown"
FULL_USER="${USERNAME}@${REALM}"
FULL_TOKEN="${FULL_USER}!${TOKEN_ID}"
PRIVILEGES="Sys.PowerMgmt"

# Check for root privileges
if [[ "$EUID" -ne 0 ]]; then
  echo "Please run this script with sudo or as root."
  exit 1
fi

echo "[1/7] Checking and creating user '${FULL_USER}'"
if ! pveum user list | cat | grep "${FULL_USER}"; then
  pveum user add "${FULL_USER}" --comment "Remote shutdown user"
  echo "User created."
else
  echo "User already exists."
fi

echo "[2/7] Checking and creating role '${ROLE}'"
if ! pveum role list | cat | grep "${ROLE}"; then
  pveum role add "${ROLE}" --privs "${PRIVILEGES}"
  echo "Role created with privilege: ${PRIVILEGES}"
else
  echo "Role already exists."
fi

echo "[3/7] Checking and creating group '${GROUP}'"
if ! pveum group list | cat |grep "${GROUP}"; then
  pveum group add "${GROUP}" --comment "Automation group for shutdown control"
  echo "Group created."
else
  echo "Group already exists."
fi

echo "[4/7] Assigning role '${ROLE}' to group '${GROUP}' at '/'"
if ! pveum acl list | cat | grep "/.*${GROUP}.*${ROLE}"; then
  pveum acl modify / --group "${GROUP}" --role "${ROLE}"
  echo "Role assigned to group."
else
  echo "Role already assigned."
fi

echo "[5/7] Adding user '${FULL_USER}' to group '${GROUP}'"
if ! pveum group list | cat | grep -q "${FULL_USER}"; then
  pveum user modify "${FULL_USER}" --group "${GROUP}"
  echo "User added to group."
else
  echo "User already in group."
fi

echo "[6/7] Generating API token '${FULL_TOKEN}'"
if ! pveum user token list "${FULL_USER}" | cat | grep "${TOKEN_ID}"; then
  TOKEN_DATA=$(pveum user token add "${FULL_USER}" "${TOKEN_ID}" --privsep 0 --output-format json)
  TOKEN_SECRET=$(echo "${TOKEN_DATA}" | grep -Po '"value"\s*:\s*"\K[^"]+')
  echo "Token created."
else
  echo "Token already exists. Cannot regenerate secret. Delete and recreate manually if needed."
  exit 1
fi

echo "[7/7] Setup complete."

echo
echo "-------------------------- Proxmox API Token Credentials --------------------------"
echo "User:       ${FULL_USER}"
echo "Token ID:   ${TOKEN_ID}"
echo "Token Name: ${FULL_TOKEN}"
echo "Token:     ${TOKEN_SECRET}"
echo "-----------------------------------------------------------------------------------"
echo "Save the token securely. It will not be retrievable again."
echo "You can now use this token for API calls to manage shutdown operations."