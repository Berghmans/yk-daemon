"""TCP socket server for low-latency TOTP requests.

This module provides a simple line-based protocol for YubiKey TOTP operations
over a TCP socket connection.

Protocol:
- Commands end with '\n'
- Responses: 'OK <data>\n' or 'ERROR <message>\n'
- Commands:
  - GET_TOTP\n → OK 123456\n (returns first account's TOTP)
  - GET_TOTP <account>\n → OK 123456\n (returns specific account's TOTP)
  - LIST_ACCOUNTS\n → OK GitHub,AWS,Google\n (returns comma-separated list)
"""

import logging
import socket
import threading
from typing import Any

from src.yubikey import (
    AccountNotFoundError,
    DeviceNotFoundError,
    DeviceRemovedError,
    TouchTimeoutError,
    YubiKeyInterface,
)

logger = logging.getLogger(__name__)


class SocketServer:
    """TCP socket server for YubiKey TOTP operations."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5001,
        yubikey_interface: YubiKeyInterface | None = None,
    ) -> None:
        """Initialize the socket server.

        Args:
            host: Host to bind to (default: 127.0.0.1)
            port: Port to listen on (default: 5001)
            yubikey_interface: YubiKey interface instance (optional)
        """
        self.host = host
        self.port = port
        self.yubikey = yubikey_interface or YubiKeyInterface()
        self._server_socket: socket.socket | None = None
        self._running = False
        self._server_thread: threading.Thread | None = None
        self._client_threads: list[threading.Thread] = []
        self._lock = threading.Lock()
        logger.info(f"Socket server initialized on {host}:{port}")

    def start(self) -> None:
        """Start the socket server in a background thread."""
        if self._running:
            logger.warning("Socket server is already running")
            return

        self._running = True
        self._server_thread = threading.Thread(target=self._run_server, daemon=True)
        self._server_thread.start()
        logger.info(f"Socket server started on {self.host}:{self.port}")

    def stop(self) -> None:
        """Stop the socket server and close all connections."""
        if not self._running:
            logger.warning("Socket server is not running")
            return

        logger.info("Stopping socket server...")
        self._running = False

        # Close server socket to unblock accept()
        if self._server_socket:
            try:
                self._server_socket.close()
            except Exception as e:
                logger.warning(f"Error closing server socket: {e}")
            finally:
                self._server_socket = None

        # Wait for server thread to finish
        if self._server_thread:
            self._server_thread.join(timeout=2.0)
            self._server_thread = None

        # Wait for client threads to finish
        with self._lock:
            for thread in self._client_threads:
                if thread.is_alive():
                    thread.join(timeout=1.0)
            self._client_threads.clear()

        logger.info("Socket server stopped")

    def _run_server(self) -> None:
        """Main server loop that accepts client connections."""
        try:
            # Create server socket
            self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_socket.bind((self.host, self.port))
            self._server_socket.listen(5)

            logger.info(f"Socket server listening on {self.host}:{self.port}")

            while self._running:
                try:
                    # Accept client connection with timeout to allow graceful shutdown
                    self._server_socket.settimeout(1.0)
                    client_socket, client_address = self._server_socket.accept()
                    logger.info(f"Client connected from {client_address}")

                    # Handle client in separate thread
                    client_thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, client_address),
                        daemon=True,
                    )
                    client_thread.start()

                    # Track client thread and clean up finished threads
                    with self._lock:
                        self._client_threads.append(client_thread)
                        self._client_threads = [t for t in self._client_threads if t.is_alive()]

                except TimeoutError:
                    # Timeout is expected, allows us to check _running flag
                    continue
                except OSError as e:
                    if self._running:
                        logger.error(f"Socket error while accepting connections: {e}")
                    break

        except Exception as e:
            logger.error(f"Server error: {e}")
        finally:
            if self._server_socket:
                try:
                    self._server_socket.close()
                except Exception:
                    pass
                self._server_socket = None
            logger.info("Server socket closed")

    def _handle_client(self, client_socket: socket.socket, client_address: Any) -> None:
        """Handle a client connection.

        Args:
            client_socket: Client socket connection
            client_address: Client address tuple (host, port)
        """
        try:
            with client_socket:
                # Set receive timeout
                client_socket.settimeout(30.0)

                # Receive and process commands
                buffer = ""
                while self._running:
                    try:
                        # Receive data
                        data = client_socket.recv(1024).decode("utf-8")
                        if not data:
                            # Client closed connection
                            break

                        buffer += data

                        # Process complete commands (ending with \n)
                        while "\n" in buffer:
                            command, buffer = buffer.split("\n", 1)
                            command = command.strip()

                            if command:
                                logger.debug(f"Received command from {client_address}: {command}")
                                response = self._process_command(command)
                                logger.debug(f"Sending response to {client_address}: {response}")
                                client_socket.sendall((response + "\n").encode("utf-8"))

                    except TimeoutError:
                        logger.debug(f"Client {client_address} timeout")
                        break
                    except Exception as e:
                        logger.error(f"Error handling client {client_address}: {e}")
                        try:
                            error_response = f"ERROR Internal server error: {e}"
                            client_socket.sendall((error_response + "\n").encode("utf-8"))
                        except Exception:
                            pass
                        break

        except Exception as e:
            logger.error(f"Client handler error for {client_address}: {e}")
        finally:
            logger.info(f"Client disconnected: {client_address}")

    def _process_command(self, command: str) -> str:
        """Process a client command and return response.

        Args:
            command: Command string (without trailing newline)

        Returns:
            Response string (without trailing newline)
        """
        try:
            # Parse command
            parts = command.split(None, 1)  # Split on first whitespace
            if not parts:
                return "ERROR Empty command"

            cmd = parts[0].upper()

            if cmd == "LIST_ACCOUNTS":
                # List all accounts
                accounts = self.yubikey.list_accounts()
                if not accounts:
                    return "OK"
                return f"OK {','.join(accounts)}"

            elif cmd == "GET_TOTP":
                # Get TOTP for account or first account
                account = parts[1] if len(parts) > 1 else None

                if account:
                    # Get TOTP for specific account
                    code = self.yubikey.generate_totp(account)
                    if isinstance(code, str):
                        return f"OK {code}"
                    else:
                        return "ERROR Unexpected response type"
                else:
                    # Get TOTP for first account
                    result = self.yubikey.generate_totp()
                    if isinstance(result, dict):
                        if not result:
                            return "ERROR No accounts found"
                        # Return first account's code
                        first_code = next(iter(result.values()))
                        return f"OK {first_code}"
                    else:
                        return "ERROR Unexpected response type"

            else:
                return f"ERROR Unknown command: {cmd}"

        except DeviceNotFoundError as e:
            logger.warning(f"YubiKey not found: {e}")
            return f"ERROR YubiKey not connected: {e}"

        except AccountNotFoundError as e:
            logger.warning(f"Account not found: {e}")
            return f"ERROR Account not found: {e}"

        except TouchTimeoutError as e:
            logger.warning(f"Touch timeout: {e}")
            return f"ERROR Touch timeout: {e}"

        except DeviceRemovedError as e:
            logger.error(f"Device removed: {e}")
            return f"ERROR Device error: {e}"

        except Exception as e:
            logger.error(f"Error processing command '{command}': {e}")
            return f"ERROR Internal error: {e}"

    def is_running(self) -> bool:
        """Check if the server is running.

        Returns:
            bool: True if server is running, False otherwise
        """
        return self._running
