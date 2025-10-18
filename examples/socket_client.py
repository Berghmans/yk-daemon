#!/usr/bin/env python3
"""Example client for YubiKey Daemon TCP Socket Server.

This script demonstrates how to interact with the TCP socket server
using the simple line-based protocol to retrieve TOTP codes.

Protocol:
- Commands end with '\\n'
- Responses: 'OK <data>\\n' or 'ERROR <message>\\n'
- Commands:
  - GET_TOTP\\n → OK 123456\\n (returns first account's TOTP)
  - GET_TOTP <account>\\n → OK 123456\\n (returns specific account's TOTP)
  - LIST_ACCOUNTS\\n → OK GitHub,AWS,Google\\n (returns comma-separated list)

Usage:
    python examples/socket_client.py [--host HOST] [--port PORT] [--account ACCOUNT]
"""

import argparse
import socket
import sys


def send_command(host: str, port: int, command: str, timeout: float = 30.0) -> str:
    """Send a command to the socket server and receive response.

    Args:
        host: Server host
        port: Server port
        command: Command to send (without trailing newline)
        timeout: Socket timeout in seconds

    Returns:
        Response string (without trailing newline)

    Raises:
        ConnectionError: If unable to connect to server
        socket.timeout: If operation times out
    """
    try:
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
    except ConnectionRefusedError:
        raise ConnectionError(
            f"Could not connect to socket server at {host}:{port}. "
            "Make sure the YubiKey Daemon socket server is running."
        ) from None
    except TimeoutError:
        raise TimeoutError(
            f"Operation timed out after {timeout} seconds. "
            "The server may be waiting for YubiKey touch."
        ) from None


def parse_response(response: str) -> tuple[bool, str]:
    """Parse a server response.

    Args:
        response: Response string from server

    Returns:
        Tuple of (success: bool, data/error_message: str)
    """
    if response.startswith("OK"):
        # Extract data after "OK "
        data = response[3:] if len(response) > 3 else ""
        return True, data
    elif response.startswith("ERROR"):
        # Extract error message after "ERROR "
        error = response[6:] if len(response) > 6 else "Unknown error"
        return False, error
    else:
        return False, f"Invalid response format: {response}"


def list_accounts(host: str, port: int) -> list[str] | None:
    """List all OATH accounts on YubiKey.

    Args:
        host: Server host
        port: Server port

    Returns:
        List of account names or None on error
    """
    try:
        print("\n📋 Listing accounts...")
        response = send_command(host, port, "LIST_ACCOUNTS", timeout=10.0)
        success, data = parse_response(response)

        if success:
            print(f"✅ Response: {response}")
            if data:
                accounts = data.split(",")
                return accounts
            else:
                print("⚠️  No accounts found on YubiKey")
                return []
        else:
            print(f"❌ Error: {data}")
            return None
    except (TimeoutError, ConnectionError) as e:
        print(f"❌ Error: {e}")
        return None


def get_totp(host: str, port: int, account: str | None = None) -> str | None:
    """Get TOTP code for an account.

    Args:
        host: Server host
        port: Server port
        account: Account name (optional, defaults to first account)

    Returns:
        TOTP code or None on error
    """
    try:
        if account:
            command = f"GET_TOTP {account}"
            print(f"\n🔑 Generating TOTP for account: {account}...")
        else:
            command = "GET_TOTP"
            print("\n🔑 Generating TOTP for default account...")

        print("   (Touch your YubiKey if prompted)")

        response = send_command(host, port, command, timeout=30.0)
        success, data = parse_response(response)

        if success:
            print(f"✅ Response: {response}")
            return data
        else:
            print(f"❌ Error: {data}")
            return None
    except (TimeoutError, ConnectionError) as e:
        print(f"❌ Error: {e}")
        return None


def interactive_mode(host: str, port: int) -> int:
    """Run in interactive mode allowing multiple commands.

    Args:
        host: Server host
        port: Server port

    Returns:
        Exit code
    """
    print("\n" + "=" * 60)
    print("Interactive Mode")
    print("=" * 60)
    print("Commands:")
    print("  list              - List all accounts")
    print("  get               - Get TOTP for first account")
    print("  get <account>     - Get TOTP for specific account")
    print("  quit              - Exit interactive mode")
    print("=" * 60)

    while True:
        try:
            user_input = input("\n> ").strip()

            if not user_input:
                continue

            if user_input.lower() == "quit":
                print("👋 Goodbye!")
                return 0

            if user_input.lower() == "list":
                accounts = list_accounts(host, port)
                if accounts:
                    print(f"\nAccounts ({len(accounts)}):")
                    for i, account in enumerate(accounts, 1):
                        print(f"  {i}. {account}")

            elif user_input.lower().startswith("get"):
                parts = user_input.split(None, 1)
                account_name: str | None = parts[1] if len(parts) > 1 else None
                code = get_totp(host, port, account_name)
                if code:
                    print(f"\n✅ TOTP Code: {code}")

            else:
                print(f"❌ Unknown command: {user_input}")
                print("   Type 'list', 'get [account]', or 'quit'")

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            return 0
        except EOFError:
            print("\n\n👋 Goodbye!")
            return 0


def main() -> int:
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Example client for YubiKey Daemon TCP Socket Server"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Socket server host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5101,
        help="Socket server port (default: 5101)",
    )
    parser.add_argument(
        "--account",
        help="Specific account to get TOTP for (optional)",
    )
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Run in interactive mode",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("YubiKey Daemon Socket Server - Example Client")
    print("=" * 60)
    print(f"Server: {args.host}:{args.port}")
    print("Protocol: Line-based TCP socket")

    # Interactive mode
    if args.interactive:
        return interactive_mode(args.host, args.port)

    # 1. List accounts
    accounts = list_accounts(args.host, args.port)
    if accounts is None:
        return 1

    if not accounts:
        print("\n⚠️  No OATH accounts found on YubiKey")
        return 1

    print(f"\nFound {len(accounts)} account(s):")
    for i, account in enumerate(accounts, 1):
        print(f"  {i}. {account}")

    # 2. Get TOTP
    code = get_totp(args.host, args.port, args.account)

    if code:
        print("\n" + "=" * 60)
        print("✅ SUCCESS")
        print("=" * 60)
        print(f"TOTP Code: {code}")
        print("This code can be used for authentication")
        print("=" * 60)
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
