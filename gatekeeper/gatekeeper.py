"""Streamlit interface for power orchestration and server reachability management across multi-node fleets."""

import json
from os import chmod
from pathlib import Path
from requests import Response, post
from streamlit import  button, error, expander, file_uploader, info, markdown, query_params, set_page_config, success, text_input, title, write
from socket import create_connection, timeout as socket_timeout
from subprocess import CalledProcessError, run
from tempfile import NamedTemporaryFile, gettempdir
from typing import Any, Dict, Optional
from urllib.parse import urljoin
from wakeonlan import send_magic_packet

CONFIGURATION_FILE_PATH: Path = Path("/etc/openresty/services.json")
DEFAULT_SOCKET_TIMEOUT_SECONDS: float = 2.0
SSH_EXECUTION_TIMEOUT_SECONDS: int = 5
HTTP_REQUEST_TIMEOUT_SECONDS: int = 5
PERMISSIONS_USER_READ_WRITE: int = 0o600


def load_services_configuration(file_path: Path) -> Dict[str, Any]:
	"""
	Load and parse the centralized JSON configuration file for nodes and routes.

	Parameters
		file_path (Path): File path pointing to the services JSON configuration file.

	Returns
		Dict[str, Any]: Dictionary containing 'nodes' and 'routes' mappings.

	Raises
		FileNotFoundError: If the specified configuration file does not exist.
		ValueError: If the file contents cannot be parsed as valid JSON.
	"""
	if not file_path.exists():
		raise FileNotFoundError(f"Configuration file does not exist at path: {file_path}")

	with open(file_path, mode="r", encoding="utf-8") as file_stream:
		configuration_data: Dict[str, Any] = json.load(file_stream)
		return configuration_data


def is_server_up(ip: str, port: int, timeout: float = 2.0) -> bool:
    """
    Check if the server is reachable on a specific TCP port.

    Parameters:
        ip (str): IP address of the server to be checked.
        port (int): TCP port number for server web UI.
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
        mac (str): The MAC address of the server system to wake.
    Returns:
        None

    Raises:
        ValueError: If the MAC address is invalid.
        RuntimeError: If sending the WoL packet fails due to an internal socket error.
    """

    send_magic_packet(mac)


def render_linux_shutdown_ui(server_ip: str) -> None:
	"""
	Render UI components for SSH key upload and Linux shutdown command execution.

	Parameters
		server_ip (str): IP address of target Linux machine.

	Returns
		None
	"""
	with expander("Shut Down Server"):
		markdown("Upload your **private SSH key** to perform a shutdown.")
		ssh_key_file = file_uploader("Upload private SSH key")
		ssh_username: str = "gatekeeper"

		if ssh_key_file and button("Send Shutdown Command"):
			temporary_directory: str = gettempdir()
			with NamedTemporaryFile(
				mode="w",
				dir=temporary_directory,
				prefix="ssh_key_",
				delete=True,
			) as key_file:
				key_file.write(ssh_key_file.getvalue().decode("utf-8"))
				key_file.flush()
				chmod(key_file.name, PERMISSIONS_USER_READ_WRITE)

				if shutdown_linux_with_ssh(server_ip, ssh_username, key_file.name):
					success("Shutdown command executed successfully.")
				else:
					error("Shutdown failed. Verify SSH configuration.")


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



def render_fleet_dashboard(node_records: Dict[str, Any]) -> None:
	"""
	Render fallback fleet dashboard listing all configured nodes and their basic metadata.

	Parameters
		node_records (Dict[str, Any]): Dictionary of node definitions from services configuration.

	Returns
		None
	"""
	set_page_config(page_title="Gatekeeper", page_icon="🛡️", layout="centered")
	title("Gatekeeper")
	markdown("This service ensures server is up before routing traffic to it.")

def main() -> None:
	"""
	Main application entry point for Streamlit UI execution. Parses node context and renders state controls.

	Returns
		None
	"""
	try:
		configuration_data: Dict[str, Any] = load_services_configuration(CONFIGURATION_FILE_PATH)
	except (FileNotFoundError, ValueError) as configuration_error:
		error(f"Configuration failure: {configuration_error}")
		return

	nodes_dictionary: Dict[str, Any] = configuration_data.get("nodes", {})
	query_parameters: Dict[str, Any] = query_params
	target_node_key: Optional[str] = query_parameters.get("node")

	if not target_node_key or target_node_key not in nodes_dictionary:
		render_fleet_dashboard(nodes_dictionary)
		return

	selected_node: Dict[str, Any] = nodes_dictionary[target_node_key]
	ip_address: str = str(selected_node.get("ip", ""))
	mac_address: str = str(selected_node.get("mac", ""))
	health_port: int = int(selected_node.get("health_port", 80))
	node_type: str = str(selected_node.get("type", "linux")).lower()

	set_page_config(page_title=f"Gatekeeper: {target_node_key}", page_icon="🛡️")
	title(f"Gatekeeper: {target_node_key}")

	if is_server_up(ip_address, health_port, DEFAULT_SOCKET_TIMEOUT_SECONDS):
		success(f"Node **{target_node_key}** ({ip_address}) is **ONLINE**.")
		if node_type == "proxmox":
			render_proxmox_shutdown_ui(ip_address, health_port)
		elif node_type == "linux":
			render_linux_shutdown_ui(ip_address)
		elif node_type == "windows":
			info("Windows host active. Please manage shutdown via RDP or VNC.")
	else:
		error(f"Node **{target_node_key}** ({ip_address}) is **OFFLINE**.")
		if button("Wake Server"):
			try:
				wake_server(mac_address)
				success("Wake-on-LAN magic packet transmitted successfully.")
			except Exception as wake_error:
				error(f"Failed to transmit WoL packet: {wake_error}")

		info("Refresh the page to recheck server status.")


if __name__ == "__main__":
	main()