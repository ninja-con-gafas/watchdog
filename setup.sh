#!/bin/bash

set -e

# Check if the `.env` file exists
if [[ ! -f .env ]]; then
  echo ".env file not found!"
  exit 1
fi

# Check if the `99-custom-dns.conf` file exists
if [[ ! -f 99-custom-dns.conf ]]; then
  echo "99-custom-dns.conf file not found!"
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
required_vars=(FTLCONF_dns_upstreams FTLCONF_webserver_api_password HOST_IP HOSTNAME PIHOLE_IP PIHOLE_MAC TZ)
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

echo "[5/6] Creating custom DNS records"
mkdir -p /etc/dnsmasq.d/
cp ./99-custom-dns.conf /etc/dnsmasq.d/

echo "[6/6] Starting services via Docker Compose"
docker compose up -d

echo "Setup completed successfully!"