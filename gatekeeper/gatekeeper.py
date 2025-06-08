"""
A Streamlit application to check server availability and optionally send Wake-on-LAN signal.

Parameters:
    Loaded from environment variables:
        - SERVER_IP (str): Static IP address of server
        - SERVER_MAC (str): MAC address of server
        - SERVER_PORT (int): TCP port for server web UI
Returns:
    Streamlit UI based on server availability

Raises:
    Displays error messages for unreachable hosts or failed WoL attempts
"""

from os import chmod, getenv
from requests import Response, post
from socket import create_connection, timeout as socket_timeout
from streamlit import  button, error, expander, file_uploader, info, markdown, set_page_config, success, text_input, title
from subprocess import run, CalledProcessError
from tempfile import gettempdir, NamedTemporaryFile
from urllib.parse import urljoin
from wakeonlan import send_magic_packet

# Load environment variables
IS_PROXMOX: bool = getenv("IS_PROXMOX").strip().lower() in {"true"}
SERVER_IP: str = getenv("SERVER_IP")
SERVER_MAC: str = getenv("SERVER_MAC")
SERVER_PORT: int = int(getenv("SERVER_PORT"))

def is_server_up(ip: str, port: int, timeout: float = 2.0) -> bool:
    """
    Check if the server is reachable on a specific TCP port.

    Parameters:
        ip (str): IP address of the server to be checked.
        port (int): TCP port number for Server web UI.
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

    set_page_config(page_title="Gatekeeper", page_icon="🛡️", layout="centered")
    title("Gatekeeper")
    markdown("This service ensures server is up before routing traffic to it.")

def render_generic_shutdown_ui(ip: str, port: int):
    """
    Render the generic shutdown UI for server via SSH with key based authentication.

    Parameters:
        ip (str): IP address of the server.
        port (int): TCP port for server web UI.

    Returns:
        None

    Raises:
        Displays error messages in UI on failure.
    """

    with expander("Shut Down Generic Server"):
        markdown("Upload your **private SSH key** to perform a shutdown.")

        ssh_key_file = file_uploader("Upload your private SSH key")
        ssh_user: str = "gatekeeper"

        if ssh_key_file and button("Send Shutdown Command"):
            temp_dir = gettempdir()
            with NamedTemporaryFile(mode="w", dir=temp_dir, prefix="ssh_key_", delete=True) as temp_key_file:
                temp_key_file.write(ssh_key_file.getvalue().decode("utf-8"))
                temp_key_file.flush()
                chmod(temp_key_file.name, 0o600) # chmod u=rw,go= (read/write for user only)

                if shutdown_linux_with_ssh(ip, ssh_user, temp_key_file.name):
                    success("Shutdown command sent successfully!")
                else:
                    error("Shutdown failed. Verify that the SSH setup is correctly configured.")

def render_proxmox_shutdown_ui(ip: str, port: int):
    """
    Render the shutdown UI for Proxmox via API token authentication.

    Parameters:
        ip (str): IP address of the Proxmox host.
        port (int): TCP port for Proxmox API.

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
            if shutdown_proxmox_with_token(ip, port, node_name, token_id, token_secret):
                success("Shutdown command sent successfully!")
            else:
                error("Shutdown request failed. Check credentials and try again.")

def shutdown_linux_with_ssh(server_ip: str, username: str, key_path: str) -> bool:
    """
    Perform a shutdown of the server via SSH using a restricted key.

    Parameters:
        server_ip (str): IP address of the server to shut down.
        username (str): The SSH username (should be 'gatekeeper').
        key_path (str): Path to the SSH private key.

    Returns:
        bool: True if the shutdown command succeeds, False otherwise.

    Raises:
        Displays UI error messages for SSH execution issues.
    """

    ssh_command = [
        "ssh",
        "-i", key_path,
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        f"{username}@{server_ip}",
        "sudo shutdown now"
    ]

    try:
        result = run(ssh_command, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return True
        else:
            error(f"SSH error ({result.returncode}): {result.stderr.strip()}")
            return False
    except FileNotFoundError:
        error("SSH command not found. Ensure OpenSSH is installed on your system.")
        return False
    except CalledProcessError as e:
        error(f"SSH command failed: {e}")
        return False
    except socket_timeout:
        error("Connection timed out.")
        return False
    except Exception as ex:
        error(f"Unexpected error: {ex}")
        return False

def shutdown_proxmox_with_token(server_ip: str, server_port: int, node_name: str, token_id: str, token_secret: str) -> bool:
    """
    Send a shutdown request to the Proxmox host using the API token.

    Parameters:
        server_ip (str): IP address of the Proxmox host.
        server_port (int): TCP port for Proxmox API.
        node_name (str): The name of the Proxmox node.
        token_id (str): Token identifier in the form `user@realm!tokenname`.
        token_secret (str): Token secret string.

    Returns:
        bool: True if shutdown request is successfully sent, False otherwise.

    Raises:
        Displays UI error messages for API call failures.
    """

    url_base = f"https://{server_ip}:{server_port}/api2/json/"
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
    
def wake_server(mac: str) -> None:
    """
    Send a Wake-on-LAN (WoL) magic packet to the server.

    Parameters:
        mac (str): The MAC address of the Server system to wake.
    Returns:
        None

    Raises:
        ValueError: If the MAC address is invalid.
        RuntimeError: If sending the WoL packet fails due to an internal socket error.
    """

    send_magic_packet(mac)

def main():
    render_header()

    if is_server_up(SERVER_IP, SERVER_PORT):
        success(f"Server is up at {SERVER_IP}:{SERVER_PORT}")
        if IS_PROXMOX:
            render_proxmox_shutdown_ui(SERVER_IP, SERVER_PORT)
        else:
           render_generic_shutdown_ui(SERVER_IP, SERVER_PORT)
    else:
        error(f"Server is currently **unavailable** at {SERVER_IP}:{SERVER_PORT}")
        if button("Wake Server"):
            try:
                wake_server(SERVER_MAC)
                success("Wake-on-LAN signal sent successfully!")
            except Exception as e:
                error(f"Failed to send WoL packet: {e}")

        info("Refresh the page to recheck Server status.")


if __name__ == "__main__":
    main()
