#!/bin/bash

# Description: Deploys Pi-hole and configures DNS records.
#   - Installs Docker and Docker Compose plugin from Docker's official repository (if not already installed)
#   - Deploys Pi-hole containers
#
# Requires:
#   - A .env file with the following variables:
#       FTLCONF_dns_upstreams: DNS servers separated by semicolon
#       FTLCONF_webserver_api_password: Password for the Pi-hole web interface
#       HOST_IP: IP address of the Raspberry Pi 3B+ host
#       HOSTNAME: Hostname for the Pi-hole container
#       PIHOLE_IP: Static IP address for the Pi-hole container
#       TZ: Timezone (e.g., "Asia/Kolkata")

set -e

# Get the default route interface
# This assumes the default route is set on the interface you want to use
# You may need to adjust this if your network setup is different
PARENT_INTERFACE=$(ip route | grep default | awk '{print $5}')

# Check if the .env file exists
if [[ ! -f .env ]]; then
  echo ".env file not found!"
  exit 1
fi

# Load environment variables from .env
echo "Loading environment variables from .env"
set -a
. .env
set +a

# Ensure script is run with sudo
if [[ "$EUID" -ne 0 ]]; then
  echo "Please run this script with sudo."
  exit 1
fi

# Validate required environment variables
required_vars=(FTLCONF_dns_upstreams FTLCONF_webserver_api_password TZ)
for var in "${required_vars[@]}"; do
    if [[ -z "${!var}" ]]; then
        echo "Missing required variable: $var"
        exit 1
    fi
done

# Check Docker and Compose plugin
if command -v docker &>/dev/null && docker compose version &>/dev/null; then
  echo "Docker and Docker Compose plugin already installed — skipping installation steps [1-4]."
else
  echo "[1/6] Updating system packages"
  apt update && apt full-upgrade -y

  echo "[2/6] Setting up Docker repository"
  apt install -y ca-certificates curl gnupg lsb-release
  mkdir -p /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/$(. /etc/os-release; echo "$ID")/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg

  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$(. /etc/os-release; echo "$ID") \
    $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

  apt update

  echo "[3/6] Installing Docker Engine and Docker Compose plugin"
  apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

  echo "[4/6] Verifying Docker installation"
  docker --version
  docker compose version
fi

echo "[5/6] Creating docker-compose.yml"
cat > docker-compose.yml <<EOF
version: "3.8"

services:
    pihole:
        image: pihole/pihole:2025.04.0
        container_name: pihole
        hostname: "${HOSTNAME}"
        restart: unless-stopped
        environment:
            FTLCONF_dns_upstreams: "${FTLCONF_dns_upstreams}"
            FTLCONF_webserver_api_password: "${FTLCONF_webserver_api_password}"
            TZ: "${TZ}"
        volumes:
            - "/etc/pihole:/etc/pihole:rw"
        ports:
            - "${PIHOLE_IP}:53:53/tcp"
            - "${PIHOLE_IP}:53:53/udp"
            - "${PIHOLE_IP}:80:80/tcp"
            - "${PIHOLE_IP}:443:443/tcp"
        networks:
            pihole_network:
                ipv4_address: "${PIHOLE_IP}"

networks:
    pihole_network:
        name: pihole_network
        driver: macvlan
        driver_opts:
          parent: "${PARENT_INTERFACE}"
        ipam:
          config:
            - subnet: 192.168.1.0/24
              gateway: 192.168.1.1
EOF

echo "[6/6] Starting services via Docker Compose"
docker compose up -d

echo "Setup completed successfully!"