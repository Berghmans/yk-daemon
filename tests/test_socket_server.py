"""Unit tests for TCP socket server module."""

import socket
import time
from collections.abc import Generator
from unittest.mock import Mock

import pytest

from yk_daemon.socket_server import SocketServer
from yk_daemon.yubikey import (
    AccountNotFoundError,
    DeviceNotFoundError,
    DeviceRemovedError,
    TouchTimeoutError,
    YubiKeyInterface,
)


@pytest.fixture
def mock_yubikey() -> Mock:
    """Create a mock YubiKey interface."""
    mock_yk = Mock(spec=YubiKeyInterface)
    return mock_yk


@pytest.fixture
def socket_server(mock_yubikey: Mock) -> SocketServer:
    """Create a socket server instance with mock YubiKey."""
    # Use a random available port for testing
    server = SocketServer(host="127.0.0.1", port=0, yubikey_interface=mock_yubikey)
    return server


@pytest.fixture
def running_server(mock_yubikey: Mock) -> Generator[SocketServer, None, None]:
    """Create and start a socket server instance."""
    server = SocketServer(host="127.0.0.1", port=0, yubikey_interface=mock_yubikey)
    server.start()

    # Wait for server to start
    time.sleep(0.1)

    # Get the actual port the server bound to
    # We need to access the socket to get the bound port
    if server._server_socket:
        server.port = server._server_socket.getsockname()[1]

    yield server

    server.stop()


def send_command(host: str, port: int, command: str, timeout: float = 2.0) -> str:
    """Helper function to send a command and receive response.

    Args:
        host: Server host
        port: Server port
        command: Command to send
        timeout: Socket timeout in seconds

    Returns:
        Response string (without trailing newline)
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
        client_socket.settimeout(timeout)
        client_socket.connect((host, port))
        client_socket.sendall((command + "\n").encode("utf-8"))

        # Receive response
        response = b""
        while b"\n" not in response:
            chunk = client_socket.recv(1024)
            if not chunk:
                break
            response += chunk

        return response.decode("utf-8").strip()


class TestSocketServer:
    """Test cases for SocketServer class."""

    def test_init(self, mock_yubikey: Mock) -> None:
        """Test SocketServer initialization."""
        server = SocketServer(host="127.0.0.1", port=5001, yubikey_interface=mock_yubikey)

        assert server.host == "127.0.0.1"
        assert server.port == 5001
        assert server.yubikey == mock_yubikey
        assert not server.is_running()

    def test_init_default_yubikey(self) -> None:
        """Test SocketServer initialization with default YubiKey interface."""
        server = SocketServer(host="127.0.0.1", port=5001)

        assert isinstance(server.yubikey, YubiKeyInterface)

    def test_start_stop(self, socket_server: SocketServer) -> None:
        """Test starting and stopping the server."""
        assert not socket_server.is_running()

        socket_server.start()
        time.sleep(0.1)
        assert socket_server.is_running()

        socket_server.stop()
        time.sleep(0.1)
        assert not socket_server.is_running()

    def test_start_already_running(self, running_server: SocketServer) -> None:
        """Test starting a server that is already running."""
        assert running_server.is_running()

        # Starting again should not cause issues
        running_server.start()
        assert running_server.is_running()

    def test_stop_not_running(self, socket_server: SocketServer) -> None:
        """Test stopping a server that is not running."""
        assert not socket_server.is_running()

        # Stopping should not cause issues
        socket_server.stop()
        assert not socket_server.is_running()

    def test_list_accounts_success(self, running_server: SocketServer, mock_yubikey: Mock) -> None:
        """Test LIST_ACCOUNTS command with accounts."""
        mock_yubikey.list_accounts.return_value = ["GitHub", "AWS", "Google"]

        response = send_command(running_server.host, running_server.port, "LIST_ACCOUNTS")

        assert response == "OK GitHub,AWS,Google"
        mock_yubikey.list_accounts.assert_called_once()

    def test_list_accounts_empty(self, running_server: SocketServer, mock_yubikey: Mock) -> None:
        """Test LIST_ACCOUNTS command with no accounts."""
        mock_yubikey.list_accounts.return_value = []

        response = send_command(running_server.host, running_server.port, "LIST_ACCOUNTS")

        assert response == "OK"
        mock_yubikey.list_accounts.assert_called_once()

    def test_list_accounts_device_not_found(
        self, running_server: SocketServer, mock_yubikey: Mock
    ) -> None:
        """Test LIST_ACCOUNTS command when device is not found."""
        mock_yubikey.list_accounts.side_effect = DeviceNotFoundError("No YubiKey device found")

        response = send_command(running_server.host, running_server.port, "LIST_ACCOUNTS")

        assert response.startswith("ERROR YubiKey not connected:")

    def test_get_totp_specific_account(
        self, running_server: SocketServer, mock_yubikey: Mock
    ) -> None:
        """Test GET_TOTP command for a specific account."""
        mock_yubikey.generate_totp.return_value = "123456"

        response = send_command(running_server.host, running_server.port, "GET_TOTP GitHub")

        assert response == "OK 123456"
        mock_yubikey.generate_totp.assert_called_once_with("GitHub")

    def test_get_totp_first_account(self, running_server: SocketServer, mock_yubikey: Mock) -> None:
        """Test GET_TOTP command without account (returns first)."""
        mock_yubikey.generate_totp.return_value = {"GitHub": "123456", "AWS": "654321"}

        response = send_command(running_server.host, running_server.port, "GET_TOTP")

        assert response == "OK 123456"
        mock_yubikey.generate_totp.assert_called_once_with()

    def test_get_totp_no_accounts(self, running_server: SocketServer, mock_yubikey: Mock) -> None:
        """Test GET_TOTP command when no accounts exist."""
        mock_yubikey.generate_totp.return_value = {}

        response = send_command(running_server.host, running_server.port, "GET_TOTP")

        assert response == "ERROR No accounts found"

    def test_get_totp_account_not_found(
        self, running_server: SocketServer, mock_yubikey: Mock
    ) -> None:
        """Test GET_TOTP command for non-existent account."""
        mock_yubikey.generate_totp.side_effect = AccountNotFoundError("Account 'Unknown' not found")

        response = send_command(running_server.host, running_server.port, "GET_TOTP Unknown")

        assert response.startswith("ERROR Account not found:")

    def test_get_totp_touch_timeout(self, running_server: SocketServer, mock_yubikey: Mock) -> None:
        """Test GET_TOTP command when touch times out."""
        mock_yubikey.generate_totp.side_effect = TouchTimeoutError("Touch timeout")

        response = send_command(running_server.host, running_server.port, "GET_TOTP GitHub")

        assert response.startswith("ERROR Touch timeout:")

    def test_get_totp_device_removed(
        self, running_server: SocketServer, mock_yubikey: Mock
    ) -> None:
        """Test GET_TOTP command when device is removed during operation."""
        mock_yubikey.generate_totp.side_effect = DeviceRemovedError("Device disconnected")

        response = send_command(running_server.host, running_server.port, "GET_TOTP GitHub")

        assert response.startswith("ERROR Device error:")

    def test_unknown_command(self, running_server: SocketServer, mock_yubikey: Mock) -> None:
        """Test handling of unknown command."""
        response = send_command(running_server.host, running_server.port, "INVALID_COMMAND")

        assert response.startswith("ERROR Unknown command:")

    def test_empty_command(self, running_server: SocketServer, mock_yubikey: Mock) -> None:
        """Test handling of empty command."""
        # Empty command is skipped (no response), just verify server is still working
        mock_yubikey.list_accounts.return_value = ["GitHub"]

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            client_socket.settimeout(2.0)
            client_socket.connect((running_server.host, running_server.port))

            # Send empty command (only newline)
            client_socket.sendall(b"\n")

            # Send a real command to verify connection is still working
            client_socket.sendall(b"LIST_ACCOUNTS\n")

            # Should only receive response for the valid command
            response = client_socket.recv(1024).decode("utf-8").strip()
            assert response == "OK GitHub"

    def test_case_insensitive_commands(
        self, running_server: SocketServer, mock_yubikey: Mock
    ) -> None:
        """Test that commands are case-insensitive."""
        mock_yubikey.list_accounts.return_value = ["GitHub"]

        # Test lowercase
        response = send_command(running_server.host, running_server.port, "list_accounts")
        assert response == "OK GitHub"

        # Test mixed case
        mock_yubikey.list_accounts.return_value = ["AWS"]
        response = send_command(running_server.host, running_server.port, "List_Accounts")
        assert response == "OK AWS"

    def test_multiple_commands_same_connection(
        self, running_server: SocketServer, mock_yubikey: Mock
    ) -> None:
        """Test sending multiple commands on the same connection."""
        mock_yubikey.list_accounts.return_value = ["GitHub", "AWS"]
        mock_yubikey.generate_totp.return_value = "123456"

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            client_socket.settimeout(2.0)
            client_socket.connect((running_server.host, running_server.port))

            # Send first command
            client_socket.sendall(b"LIST_ACCOUNTS\n")
            response1 = client_socket.recv(1024).decode("utf-8").strip()
            assert response1 == "OK GitHub,AWS"

            # Send second command
            client_socket.sendall(b"GET_TOTP GitHub\n")
            response2 = client_socket.recv(1024).decode("utf-8").strip()
            assert response2 == "OK 123456"

    def test_concurrent_connections(self, running_server: SocketServer, mock_yubikey: Mock) -> None:
        """Test handling multiple concurrent client connections."""
        mock_yubikey.list_accounts.return_value = ["GitHub"]

        # Create multiple client connections
        def client_task() -> str:
            return send_command(running_server.host, running_server.port, "LIST_ACCOUNTS")

        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(client_task) for _ in range(5)]
            results = [f.result() for f in futures]

        # All clients should get the same response
        for result in results:
            assert result == "OK GitHub"

    def test_client_disconnect(self, running_server: SocketServer, mock_yubikey: Mock) -> None:
        """Test server handles client disconnect gracefully."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            client_socket.settimeout(2.0)
            client_socket.connect((running_server.host, running_server.port))
            # Close without sending anything

        # Server should still be running
        assert running_server.is_running()

        # And should accept new connections
        mock_yubikey.list_accounts.return_value = ["GitHub"]
        response = send_command(running_server.host, running_server.port, "LIST_ACCOUNTS")
        assert response == "OK GitHub"

    def test_command_with_whitespace(
        self, running_server: SocketServer, mock_yubikey: Mock
    ) -> None:
        """Test commands with extra whitespace."""
        mock_yubikey.generate_totp.return_value = "123456"

        # Test command with leading/trailing spaces
        response = send_command(running_server.host, running_server.port, "  GET_TOTP GitHub  ")

        assert response == "OK 123456"

    def test_account_name_with_spaces(
        self, running_server: SocketServer, mock_yubikey: Mock
    ) -> None:
        """Test GET_TOTP command with account name containing spaces."""
        mock_yubikey.generate_totp.return_value = "123456"

        response = send_command(
            running_server.host, running_server.port, "GET_TOTP My Account Name"
        )

        assert response == "OK 123456"
        mock_yubikey.generate_totp.assert_called_once_with("My Account Name")

    def test_protocol_newline_handling(
        self, running_server: SocketServer, mock_yubikey: Mock
    ) -> None:
        """Test protocol correctly handles newline-delimited commands."""
        mock_yubikey.list_accounts.return_value = ["GitHub"]

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            client_socket.settimeout(2.0)
            client_socket.connect((running_server.host, running_server.port))

            # Send multiple commands in one packet
            client_socket.sendall(b"LIST_ACCOUNTS\nLIST_ACCOUNTS\n")

            # Should receive two responses
            all_data = b""
            # Read until we get both responses
            for _ in range(5):  # Max 5 recv attempts
                chunk = client_socket.recv(1024)
                all_data += chunk
                if all_data.count(b"\n") >= 2:
                    break

            response = all_data.decode("utf-8")
            assert response.count("OK GitHub") == 2

    def test_server_shutdown_closes_connections(
        self, running_server: SocketServer, mock_yubikey: Mock
    ) -> None:
        """Test that stopping the server closes active client connections."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            client_socket.settimeout(2.0)
            client_socket.connect((running_server.host, running_server.port))

            # Stop server
            running_server.stop()
            time.sleep(0.2)

            # Connection should be closed - either sending or receiving should fail
            connection_closed = False
            try:
                client_socket.sendall(b"LIST_ACCOUNTS\n")
                # Even if send succeeds, recv should fail or return empty
                response = client_socket.recv(1024)
                if not response:
                    connection_closed = True
            except OSError:
                connection_closed = True

            assert connection_closed, "Expected connection to be closed after server shutdown"

    def test_get_totp_account_with_special_chars(
        self, running_server: SocketServer, mock_yubikey: Mock
    ) -> None:
        """Test GET_TOTP with account names containing special characters."""
        mock_yubikey.generate_totp.return_value = "123456"

        response = send_command(
            running_server.host, running_server.port, "GET_TOTP user@example.com"
        )

        assert response == "OK 123456"
        mock_yubikey.generate_totp.assert_called_once_with("user@example.com")
