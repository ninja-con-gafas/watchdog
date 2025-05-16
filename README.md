# Raspberry Pi Microserver Gateway: Secure Access & Service Routing

This project configures a **Raspberry Pi 3B+** as a lightweight and secure **gateway node** for self-hosted infrastructure. Acting as a front-facing control plane, the Pi manages **network access**, **DNS resolution**, **conditional reverse proxy routing**, and **power state orchestration** for a Proxmox-based private cloud setup.

> All access to internal services is strictly gated through a **VPN** tunnel using **WireGuard**, enhancing security while maintaining accessibility.

---

## System Architecture Overview

- **Host Hardware**: Raspberry Pi 3B+
- **Container Runtime**: Docker with Docker Compose
- **Network Access**: VPN-only (WireGuard)

This setup is designed for **headless operation** and remote administration over a secure tunnel, enabling clean, modular service deployment using containers.

---

## Component Matrix

| Functionality      | Tool / Technology             | Hosted On      |
|--------------------|-------------------------------|----------------|
| Operating System   | Raspberry Pi OS Lite (64-bit) | Raspberry Pi   |
| Conditional Routing| **OpenResty (Nginx + Lua)**   | Raspberry Pi   |
| VPN Server         | **WireGuard**                 | Raspberry Pi   |
| DNS Resolver       | **Pi-hole**                   | Raspberry Pi   |
| Wake-on-LAN (WoL)  | `wakeonlan` CLI               | Raspberry Pi   |
| Proxmox Monitoring | TCP Port Check + Lua Logic    | Raspberry Pi   |
| Remote Shutdown    | Key-authenticated SSH         | Pi → Proxmox   |

---

## Access Control Model

All services hosted under the private cloud infrastructure are **completely isolated from the public internet**. Access is strictly controlled via:

- **Local LAN (intranet)** through the Raspberry Pi
- **Remote access** via **WireGuard VPN**, which tunnels into the local network

There are no ports open to the internet — ensuring a **zero-trust model** by default.

---

## Service Discovery & Conditional Reverse Proxy

### OpenResty (Nginx + Lua)
- Uses **Lua scripting** inside Nginx to determine if Proxmox is reachable on port `8006`.
- If **Proxmox is available**, requests are **proxied directly** to its hosted services (e.g., Grafana, Prometheus).
- If **Proxmox is offline**, requests are routed to a local middleware (`proxmox-gatekeeper`) running on the Pi.
- This ensures high availability of a control interface while minimizing Proxmox’s active uptime.

### Pi-hole (DNS Resolver & Blocker)
- Resolves container services using meaningful domain names (e.g., `grafana.lan`, `prometheus.lan`).
- Optionally blocks ads and telemetry requests across all clients on the VPN and LAN.
- Provides DNS usage analytics and logs.

---

## Additional Features

- **Wake-on-LAN**: Uses `wakeonlan` CLI to remotely boot Proxmox nodes on demand.
- **Conditional Access**: Access to internal services is dependent on the real-time availability of Proxmox.
- **Remote Shutdown**: Uses SSH (with key-based auth) from the Pi to issue shutdown commands to Proxmox nodes, saving power during inactivity.

---

## Use Case & Purpose

This project addresses the need for a **lightweight edge controller** in home-lab environments where:

- Public exposure of self-hosted services is undesirable.
- There's a need for **secure, VPN-tunneled access** to a Proxmox-hosted cloud.
- Services require **clean routing**, **private DNS resolution**, and **power management** through a single point of control.

The Raspberry Pi operates as a **service orchestrator** and **network access controller**, empowering safe, remote administration of a private infrastructure.

---

## Getting Started

The stack is containerized and can be easily deployed using Docker Compose. To deploy the entire stack on your preferred infrastructure, follow the instructions given below:

1. Clone the repository.
2. Create a `.env` file in the root directory before running `setup.sh`:
    ```bash
    # Pi-hole Configurations
    FTLCONF_dns_upstreams="" # DNS servers used by Pi-hole for upstream resolution (semicolon separated)
    FTLCONF_webserver_api_password="" # Password for accessing the Pi-hole admin web interface
    HOST_IP="" # IP address of the Raspberry Pi 3B+ host
    HOSTNAME="" # Hostname for the Pi-hole container
    PARENT_INTERFACE="" # Pi-hole network interface, defaults to `$(ip route | grep default | awk '{print $5}')` if not set
    PIHOLE_IP="" # Static IP address for the Pi-hole container
    PIHOLE_MAC="" # MAC address for the Pi-hole container
    PROXMOX_IP="" # Static IP address of Proxmox hypervisor host
    PROXMOX_MAC="" # MAC address of Proxmox hypervisor host
    PROXMOX_PORT="" # Port of Proxmox Hypervisor, defaults to `8006` if not set 
    TZ="" # Your Timezone
    ```
3. Create a `99-custom-dns.conf` file with custom DNS records:
    - Each entry should be on a new line and the DNS records should be in the given format `address=/<DOMAIN_NAME>/<IP_ADDRESS>`
4. Create a `services.json` file with services for conditional routing:
    - The file should be a valid JSON object where each key is a service hostname and the value is an object defining the target address.

    ```json
    {
        "service.hostname": {"target": "<IP_ADDRESS>:<PORT>"},
        ...
    }
    ```
    - The keys must match the exact hostname used in requests.
    - The `target` value specifies the backend IP and port for that service.
5. Run the setup script with **_super-user_** privilege:
    ```bash
    sudo ./setup.sh
    ```

This script will:

- Install Docker and Docker Compose
- Configure environment variables
- Launch all defined services

---
