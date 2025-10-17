#!/usr/bin/env python3
"""Simple script to list YubiKey OATH accounts and generate TOTP codes."""

import logging
import sys

from yk_daemon.yubikey import (
    AccountNotFoundError,
    DeviceNotFoundError,
    TouchTimeoutError,
    YubiKeyInterface,
)

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def main() -> None:
    """Main function."""
    print("YubiKey OATH-TOTP Generator")
    print("=" * 40)

    yk = YubiKeyInterface()

    # Check if YubiKey is connected
    print("\n[1/3] Checking for YubiKey...")
    if not yk.detect_device():
        print("❌ No YubiKey detected. Please connect your YubiKey and try again.")
        sys.exit(1)

    print("✓ YubiKey detected")

    # Get device info
    try:
        info = yk.get_device_info()
        print(f"   Device: {info.get('name', 'Unknown')}")
        if info.get("serial"):
            print(f"   Serial: {info['serial']}")
        if info.get("version"):
            print(f"   Version: {info['version']}")
    except Exception as e:
        print(f"   (Could not read device info: {e})")

    # List accounts
    print("\n[2/3] Listing OATH accounts...")
    try:
        accounts = yk.list_accounts()

        if not accounts:
            print("❌ No OATH accounts found on YubiKey")
            sys.exit(0)

        print(f"✓ Found {len(accounts)} account(s):\n")
        for idx, account in enumerate(accounts, 1):
            print(f"   {idx}. {account}")

    except DeviceNotFoundError:
        print("❌ YubiKey not found or disconnected")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error listing accounts: {e}")
        sys.exit(1)

    # Get TOTP code
    print("\n[3/3] Generate TOTP code")
    print("-" * 40)

    # Prompt user for account selection
    while True:
        try:
            choice = input(f"\nEnter account number (1-{len(accounts)}) or 'q' to quit: ").strip()

            if choice.lower() == "q":
                print("\nBye!")
                sys.exit(0)

            account_idx = int(choice) - 1
            if 0 <= account_idx < len(accounts):
                selected_account = accounts[account_idx]
                break
            else:
                print(f"Please enter a number between 1 and {len(accounts)}")
        except ValueError:
            print("Please enter a valid number or 'q' to quit")

    print(f"\nGenerating TOTP code for: {selected_account}")
    print("👆 Please touch your YubiKey when it blinks...")

    try:
        code = yk.generate_totp(selected_account)

        print("\n" + "=" * 40)
        print(f"✓ TOTP Code: {code}")
        print("=" * 40)
        print("\n💡 Tip: This code is valid for ~30 seconds")

    except TouchTimeoutError:
        print("\n❌ Touch timeout - you didn't touch the YubiKey in time")
        print("   Please try again and touch the key when it blinks")
        sys.exit(1)
    except AccountNotFoundError as e:
        print(f"\n❌ Account not found: {e}")
        sys.exit(1)
    except DeviceNotFoundError:
        print("\n❌ YubiKey disconnected during operation")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error generating code: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Bye!")
        sys.exit(0)
