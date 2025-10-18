#!/usr/bin/env python3
"""Example client for YubiKey Daemon REST API.

This script demonstrates how to interact with the REST API endpoints
to retrieve TOTP codes and manage OATH accounts.

Usage:
    python examples/rest_api_client.py [--host HOST] [--port PORT]
"""

import argparse
import sys
from typing import Any

try:
    import requests  # type: ignore[import-untyped]
except ImportError:
    print("Error: requests library not installed")
    print("Install with: pip install requests")
    sys.exit(1)


def print_response(title: str, response: requests.Response) -> None:
    """Pretty print API response.

    Args:
        title: Title to display
        response: requests Response object
    """
    print(f"\n{'=' * 60}")
    print(f"{title}")
    print(f"{'=' * 60}")
    print(f"Status Code: {response.status_code}")
    print("Response:")

    try:
        data = response.json()
        for key, value in data.items():
            print(f"  {key}: {value}")
    except Exception as e:
        print(f"  Error parsing JSON: {e}")
        print(f"  Raw response: {response.text}")


def check_health(base_url: str) -> dict[str, Any] | None:
    """Check API health and YubiKey status.

    Args:
        base_url: Base URL of the API

    Returns:
        JSON response or None on error
    """
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        print_response("Health Check", response)
        return response.json() if response.status_code == 200 else None
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Error connecting to API: {e}")
        print("\nMake sure the YubiKey Daemon REST API is running:")
        print("  poetry run python -m src.rest_api")
        return None


def list_accounts(base_url: str) -> list[str] | None:
    """List all OATH accounts on YubiKey.

    Args:
        base_url: Base URL of the API

    Returns:
        List of account names or None on error
    """
    try:
        response = requests.get(f"{base_url}/api/accounts", timeout=10)
        print_response("List Accounts", response)

        if response.status_code == 200:
            data = response.json()
            accounts: list[str] = data.get("accounts", [])
            return accounts
        return None
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Error: {e}")
        return None


def get_default_totp(base_url: str) -> str | None:
    """Get TOTP for default (first) account.

    Args:
        base_url: Base URL of the API

    Returns:
        TOTP code or None on error
    """
    try:
        print("\n⏳ Generating TOTP for default account...")
        print("   (Touch your YubiKey if prompted)")

        response = requests.get(f"{base_url}/api/totp", timeout=30)
        print_response("Get Default TOTP", response)

        if response.status_code == 200:
            data = response.json()
            code: str | None = data.get("code")
            return code
        return None
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Error: {e}")
        return None


def get_totp_for_account(base_url: str, account: str) -> str | None:
    """Get TOTP for specific account.

    Args:
        base_url: Base URL of the API
        account: Account name

    Returns:
        TOTP code or None on error
    """
    try:
        print(f"\n⏳ Generating TOTP for account: {account}...")
        print("   (Touch your YubiKey if prompted)")

        response = requests.get(f"{base_url}/api/totp/{account}", timeout=30)
        print_response(f"Get TOTP for {account}", response)

        if response.status_code == 200:
            data = response.json()
            code: str | None = data.get("code")
            return code
        return None
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Error: {e}")
        return None


def main() -> int:
    """Main function."""
    parser = argparse.ArgumentParser(description="Example client for YubiKey Daemon REST API")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="API host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5100,
        help="API port (default: 5100)",
    )
    parser.add_argument(
        "--account",
        help="Specific account to get TOTP for (optional)",
    )
    args = parser.parse_args()

    base_url = f"http://{args.host}:{args.port}"

    print("=" * 60)
    print("YubiKey Daemon REST API - Example Client")
    print("=" * 60)
    print(f"API URL: {base_url}")

    # 1. Check health
    health = check_health(base_url)
    if not health:
        return 1

    yubikey_status = health.get("yubikey_status")
    if yubikey_status == "not_connected":
        print("\n⚠️  Warning: YubiKey is not connected")
        print("   Please connect your YubiKey and try again")
        return 1

    # 2. List accounts
    accounts = list_accounts(base_url)
    if not accounts:
        print("\n⚠️  No OATH accounts found on YubiKey")
        return 1

    # 3. Get TOTP
    if args.account:
        # Get TOTP for specific account
        code = get_totp_for_account(base_url, args.account)
    else:
        # Get TOTP for default account
        code = get_default_totp(base_url)

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
