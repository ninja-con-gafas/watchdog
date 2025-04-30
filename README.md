# Raspberry Pi Microserver Gateway: Secure Access & Service Routing

This project configures a **Raspberry Pi 3B+** as a lightweight and secure **gateway node** for self-hosted infrastructure. Acting as a front-facing control plane, the Pi manages **network access**, **DNS resolution**, **reverse proxy routing**, and **power state orchestration** for a Proxmox-based private cloud setup.

> All access to internal services is strictly gated through a **VPN** tunnel using **WireGuard**, enhancing security while maintaining accessibility.

---

## System Architecture Overview

- **Host Hardware**: Raspberry Pi 3B+
- **Container Runtime**: Docker with Docker Compose
- **Network Access**: VPN-only (WireGuard)

This setup is designed for **headless operation** and remote administration over a secure tunnel, enabling clean, modular service deployment using containers.

---

## Component Matrix

| Functionality      | Tool / Technology            | Hosted On      |
|--------------------|------------------------------|----------------|
| Operating System   | Raspberry Pi OS Lite (64-bit)| Raspberry Pi   |
| Reverse Proxy      | **Traefik**                  | Raspberry Pi   |
| VPN Server         | **WireGuard**                | Raspberry Pi   |
| DNS Resolver       | **Pi-hole**                  | Raspberry Pi   |
| Wake-on-LAN (WoL)  | `wakeonlan` CLI              | Raspberry Pi   |
| Proxmox Monitoring | Proxmox API (Idle detection) | Raspberry Pi   |
| Remote Shutdown    | Key-authenticated SSH        | Pi → Proxmox   |

---

## Access Control Model

All services hosted under the private cloud infrastructure are **completely isolated from the public internet**. Access is strictly controlled via:

- **Local LAN (intranet)** through the Raspberry Pi
- **Remote access** via **WireGuard VPN**, which tunnels into the local network

There are no ports open to the internet — ensuring a **zero-trust model** by default.

---

## Service Discovery & Reverse Proxy

### Traefik (Dynamic Reverse Proxy)
- Automatically detects running containers via Docker labels.
- Routes traffic to backend services with minimal configuration.
- Exposes a **web dashboard** (VPN-only) to monitor health, routing rules, and certificates (if enabled).

### Pi-hole (DNS Resolver & Blocker)
- Resolves container services using meaningful domain names (e.g., `grafana.local`, `node-red.local`).
- Optionally blocks ads and telemetry requests across all clients on the VPN and LAN.
- Provides DNS usage analytics and logs.

---

## Additional Features

- **Wake-on-LAN**: Uses `wakeonlan` CLI to remotely boot Proxmox nodes on demand.
- **Idle Detection**: Queries Proxmox APIs to determine resource idleness for automated decisions.
- **Remote Shutdown**: Uses SSH (with key-based auth) from the Pi to issue shutdown commands to Proxmox nodes, saving power during inactivity.

---

## Use Case & Purpose

This project addresses the need for a **lightweight edge controller** in home-lab environments where:

- Public exposure of self-hosted services is undesirable.
- There's a need for **secure, VPN-tunneled access** to a Proxmox-hosted cloud.
- Services require **clean routing**, **private DNS resolution**, and **power management** through a single point of control.
- The user desires **network observability** (via Pi-hole) and dynamic service handling (via Traefik) — without the bloat of a full x86 server.

The Raspberry Pi operates as a **service orchestrator** and **network access controller**, empowering safe, remote administration of a private infrastructure.

---

## Getting Started

The stack is containerized and can be easily deployed using Docker Compose. To deploy the entire stack on your preferred, follow the instructions below:

1. Clone this repository.
2. Create a `.env` file in the root directory before running `setup.sh`:
    ```bash
    # Pi-hole Configurations
    FTLCONF_dns_upstreams="" #DNS servers used by Pi-hole for upstream resolution (semicolon separated)
    FTLCONF_webserver_api_password="" # Password for accessing the Pi-hole admin web interface
    TZ= "" # Your Timezone
    ```
3. Run the setup script with **_super-user_** privilage:
    ```bash
    sudo ./setup.sh
    ```

This script will:

- Install Docker and Docker Compose
- Configure environment variables
- Launch all defined services in isolated containers
---