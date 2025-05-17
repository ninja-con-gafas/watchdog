"""
A Streamlit application to check Proxmox availability and optionally send Wake-on-LAN signal.

Parameters:
    Loaded from environment variables:
        - PROXMOX_IP (str): Static IP address of Proxmox hypervisor host
        - PROXMOX_MAC (str): MAC address of Proxmox hypervisor host
        - PROXMOX_PORT (int): TCP port for Proxmox web UI
Returns:
    Streamlit UI based on Proxmox availability

Raises:
    Displays error messages for unreachable hosts or failed WoL attempts
"""

from os import getenv
from requests import Response, post
from socket import create_connection, timeout as socket_timeout
from streamlit import  button, error, expander, info, markdown, set_page_config, success, text_input, title
from urllib.parse import urljoin
from wakeonlan import send_magic_packet

# Load environment variables
PROXMOX_IP: str = getenv("PROXMOX_IP")
PROXMOX_MAC: str = getenv("PROXMOX_MAC")
PROXMOX_PORT: int = int(getenv("PROXMOX_PORT"))

def is_proxmox_up(ip: str, port: int, timeout: float = 2.0) -> bool:
    """
    Check if the Proxmox host is reachable on a specific TCP port.

    Parameters:
        ip (str): IP address of the Proxmox host to be checked.
        port (int): TCP port number for Proxmox web UI.
        timeout (float, optional): Timeout in seconds for the connection attempt. Default is 2.0 seconds.

    Returns:
        bool: True if the host is reachable on the given port, False otherwise.

    Raises:
        OSError: Raised internally by the socket library if an unexpected I/O error occurs.
        ConnectionRefusedError: Raised if the port is closed or access is denied.
        socket.timeout: Raised if the connection attempt exceeds the specified timeout.
    """

    try:
        with create_connection((ip, port), timeout=timeout):
            return True
    except (socket_timeout, ConnectionRefusedError, OSError):
        return False

def render_header():
    """
    Render the standard header for the Streamlit UI. Modifies the Streamlit page layout and inserts a title and description.

    Parameters:
        None

    Returns:
        None
    """

    set_page_config(page_title="Proxmox Gatekeeper", page_icon="🛡️", layout="centered")
    title("Proxmox Gatekeeper")
    markdown("This service ensures Proxmox is up before routing traffic to it.")

def render_shutdown_ui(ip: str):
    """
    Render the shutdown UI for Proxmox via API token authentication.

    Parameters:
        ip (str): IP address of the Proxmox host.

    Returns:
        None

    Raises:
        Displays error messages in UI on failure.
    """

    with expander("Shut Down Proxmox"):
        markdown("Enter your **Proxmox API token credentials** to perform a shutdown.")

        node_name: str = text_input("Node Name")
        token_id: str = text_input("API Token ID in the form `user@realm!tokenname`")
        token_secret: str = text_input("API Token Secret", type="password")

        if all([node_name, token_id, token_secret]) and button("Send Shutdown Request"):
            if shutdown_proxmox_with_token(ip, node_name, token_id, token_secret):
                success("Shutdown command sent successfully!")
            else:
                error("Shutdown request failed. Check credentials and try again.")

from urllib.parse import urljoin
from requests import post, Response
from streamlit import error

def shutdown_proxmox_with_token(proxmox_ip: str, node_name: str, token_id: str, token_secret: str) -> bool:
    """
    Send a shutdown request to the Proxmox host using the API token.

    Parameters:
        proxmox_ip (str): IP address of the Proxmox host.
        node_name (str): The name of the Proxmox node.
        token_id (str): Token identifier in the form `user@realm!tokenname`.
        token_secret (str): Token secret string.

    Returns:
        bool: True if shutdown request is successfully sent, False otherwise.

    Raises:
        Displays UI error messages for API call failures.
    """

    url_base = f"https://{proxmox_ip}:8006/api2/json/"
    shutdown_url = urljoin(url_base, f"nodes/{node_name}/status")
    headers = {"Authorization": f"PVEAPIToken={token_id}={token_secret}"}
    data = {"command": "shutdown"}

    try:
        response: Response = post(shutdown_url, headers=headers, data=data, verify=False, timeout=5)
        if response.status_code == 200:
            return True
        else:
            error(f"Shutdown failed: {response.status_code} - {response.text}")
            return False
    except Exception as ex:
        error(f"Error contacting Proxmox API: {ex}")
        return False
    
def wake_proxmox(mac: str) -> None:
    """
    Send a Wake-on-LAN (WoL) magic packet to the Proxmox host.

    Parameters:
        mac (str): The MAC address of the Proxmox system to wake.
    Returns:
        None

    Raises:
        ValueError: If the MAC address is invalid.
        RuntimeError: If sending the WoL packet fails due to an internal socket error.
    """

    send_magic_packet(mac)

def main():
    render_header()

    if is_proxmox_up(PROXMOX_IP, PROXMOX_PORT):
        success(f"Proxmox is up at {PROXMOX_IP}:{PROXMOX_PORT}")
        render_shutdown_ui(PROXMOX_IP)
    else:
        error(f"Proxmox is currently **unavailable** at {PROXMOX_IP}:{PROXMOX_PORT}")
        if button("Wake Proxmox"):
            try:
                wake_proxmox(PROXMOX_MAC)
                success("Wake-on-LAN signal sent successfully!")
            except Exception as e:
                error(f"Failed to send WoL packet: {e}")

        info("Refresh the page to recheck Proxmox status.")


if __name__ == "__main__":
    main()
