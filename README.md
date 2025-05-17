# Watchdog: A Secure Raspberry Pi Microserver Gateway for Private Cloud

A lightweight, containerized gateway for home-lab and private cloud environments, built for the Raspberry Pi 3B+. Watchdog acts as a front-facing control panel that provides secure, VPN-gated access, DNS resolution, conditional reverse proxy routing, and power state orchestration for Proxmox-based infrastructure.

---

## Features
- **Zero-trust access**: All services are only accessible via WireGuard VPN or local LAN (intranet).
- **Conditional reverse proxy**: OpenResty (Nginx + Lua) dynamically routes requests based on Proxmox availability.
- **Private DNS**: Pi-hole resolves internal service names and blocks advertisement and telemetry.
- **Wake-on-LAN & Power Management**: Remotely boot or shutdown Proxmox nodes from the Pi.
- **Headless, containerized deployment**: All services run in Docker containers for easy management.

---

## System Architecture Overview

- **Host Hardware**: Raspberry Pi 3B+
- **Container Runtime**: Docker with Docker Compose
- **Network Access**: VPN-only (WireGuard) or intranet

This setup is designed for **headless operation** and remote administration over a secure tunnel, enabling clean, modular service deployment using containers.

---

## Component Matrix

| Functionality               | Tool and Technology                     | Hosted On      |
|-----------------------------|-----------------------------------------|----------------|
| Operating System            | Raspberry Pi OS Lite (64-bit)           | Raspberry Pi   |
| Conditional Routing         | OpenResty (Nginx + Lua)                 | Raspberry Pi   |
| VPN Server                  | WireGuard                               | Raspberry Pi   |
| DNS Resolver                | Pi-hole                                 | Raspberry Pi   |
| Proxmox Power Orchestration | Wake-on-LAN, TCP Port Check & Streamlit | Raspberry Pi   |
| Remote Shutdown             | Proxmox API with Token authenticated    | Raspberry Pi   |

---

## How It Works
- **DNS**: Pi-hole resolves internal service names.
- **Reverse Proxy**: OpenResty uses Lua to check if Proxmox is up:
  - If **up**: Requests are forwarded to Proxmox or mapped services.
  - If **down**: Requests are routed to the Gatekeeper for status and Wake-on-LAN.
- **Wake-on-LAN**: Gatekeeper lets you wake Proxmox nodes if they're offline.
- **Remote Shutdown**: Pi uses Proxmox API with token-based authentication to securely shut down nodes.

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

## Setting Up Proxmox API Token for Remote Shutdown

To enable Remote Shutdown via the Proxmox API securely, create a Proxmox user with least privilege and generate an API token:

1. **Log in to Proxmox Web UI** as administrator.

2. **Create a dedicated API user**:
   - Navigate to **Datacenter > Permissions > Users**.
   - Click **Add**.
   - Enter username.
   - Select authentication realm (PVE is recommended).

3. **Generate an API token for the user**:
   - Navigate to **Datacenter > Permissions > API Tokens**.
   - Select the user.
   - Click **Add**.
   - Provide token ID.
   - Save the token and copy the **token ID** and **secret** securely.

4. **Create a custom role with only power control privileges**:
   - Navigate to **Datacenter > Permissions > Roles**.
   - Click **Add**.
   - Set a name.
   - Select only the `Sys.PowerMgmt` privilege.
   - Save the role.

5. **Create a group for automation users**:
   - Navigate to **Datacenter > Permissions > Groups**.
   - Click **Add** and name it.

6. **Assign the role to the group**:
   - Navigate to **Datacenter > Permissions**.
   - Click **Add**.
   - Set the path, group and role as created in previous steps.
   - Save the assignment.

7. **Add the user to the group**:
   - Navigate to **Datacenter > Permissions > Groups**.
   - Edit the group and add the user.