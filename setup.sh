#!/bin/bash

set -e

# Ensure script is run with sudo
if [[ "$EUID" -ne 0 ]]; then
  echo "Please run this script with sudo."
  exit 1
fi

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

# Check if the `services.json` file exists
if [[ ! -f services.json ]]; then
  echo "services.json file not found!"
  exit 1
fi

# Load environment variables from .env
echo "Loading environment variables from .env"
set -a
. .env
if [[ -z "$IS_PROXMOX" ]]; then
  IS_PROXMOX=false
  echo "Using default IS_PROXMOX: $IS_PROXMOX"
  echo "If this is not correct, please set it in the .env file."
  echo -e "\nIS_PROXMOX=\"$IS_PROXMOX\"" >> .env
  export IS_PROXMOX
fi
if [[ -z "$PARENT_INTERFACE" ]]; then
  PARENT_INTERFACE="$(ip route | awk '/default/ {print $5; exit}')"
  echo "Using default PARENT_INTERFACE: $PARENT_INTERFACE"
  echo "If this is not correct, please set it in the .env file."
  echo -e "\nPARENT_INTERFACE=\"$PARENT_INTERFACE\"" >> .env
  export PARENT_INTERFACE
fi
if [[ -z "$SERVER_PORT" ]]; then
  SERVER_PORT=22
  echo "Using default SERVER_PORT: $SERVER_PORT"
  echo "If this is not correct, please set it in the .env file."
  echo -e "\nSERVER_PORT=\"$SERVER_PORT\"" >> .env
  export SERVER_PORT
fi
set +a

# Validate required environment variables
required_vars=(FTLCONF_dns_upstreams FTLCONF_webserver_api_password HOST_IP HOSTNAME PIHOLE_IP PIHOLE_MAC SERVER_IP SERVER_MAC TZ)
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
  echo "[1/7] Updating system packages"
  apt update && apt full-upgrade -y

  echo "[2/7] Setting up Docker repository"
  apt install -y ca-certificates curl gnupg lsb-release
  mkdir -p /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/$(. /etc/os-release; echo "$ID")/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg

  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$(. /etc/os-release; echo "$ID") \
    $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

  apt update

  echo "[3/7] Installing Docker Engine and Docker Compose plugin"
  apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

  echo "[4/7] Verifying Docker installation"
  docker --version
  docker compose version
fi

echo "[5/7] Configuring custom DNS records"
mkdir -p /etc/dnsmasq.d/
cp ./99-custom-dns.conf /etc/dnsmasq.d/

echo "[6/7] Configuring reverse proxy"
mkdir -p /etc/openresty/ /usr/local/openresty/nginx/conf/
cp ./reverse-proxy/routes.lua /etc/openresty/
cp ./services.json /etc/openresty/
cp ./reverse-proxy/nginx.conf /usr/local/openresty/nginx/conf/

echo "[7/7] Starting services via Docker Compose"
docker compose up --build -d

echo "Setup completed successfully!"