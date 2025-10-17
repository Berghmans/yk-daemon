"""YubiKey OATH-TOTP interface module.

This module provides a high-level interface to YubiKey OATH-TOTP operations
using the yubikey-manager library.
"""

import logging
from enum import Enum
from typing import Any

from ykman.device import list_all_devices
from yubikit.core.smartcard import SmartCardConnection
from yubikit.oath import OathSession

logger = logging.getLogger(__name__)


class YubiKeyError(Exception):
    """Base exception for YubiKey-related errors."""

    pass


class DeviceNotFoundError(YubiKeyError):
    """Raised when no YubiKey device is found."""

    pass


class DeviceRemovedError(YubiKeyError):
    """Raised when YubiKey is removed during operation."""

    pass


class TouchTimeoutError(YubiKeyError):
    """Raised when user doesn't touch YubiKey in time."""

    pass


class AccountNotFoundError(YubiKeyError):
    """Raised when requested OATH account is not found."""

    pass


class YubiKeyStatus(Enum):
    """YubiKey device status."""

    NOT_CONNECTED = "not_connected"
    CONNECTED = "connected"
    BUSY = "busy"


class YubiKeyInterface:
    """High-level interface for YubiKey OATH-TOTP operations."""

    def __init__(self) -> None:
        """Initialize the YubiKey interface."""
        self._device: Any = None
        self._connection: Any = None
        self._oath_session: OathSession | None = None
        logger.info("YubiKey interface initialized")

    def detect_device(self) -> bool:
        """Detect if a YubiKey is connected.

        Returns:
            bool: True if YubiKey is detected, False otherwise.
        """
        try:
            devices = list(list_all_devices())
            if not devices:
                logger.debug("No YubiKey devices detected")
                return False

            logger.info(f"YubiKey device detected: {devices[0]}")
            return True
        except Exception as e:
            logger.error(f"Error detecting YubiKey: {e}")
            return False

    def get_status(self) -> YubiKeyStatus:
        """Get current YubiKey status.

        Returns:
            YubiKeyStatus: Current device status.
        """
        if self.detect_device():
            return YubiKeyStatus.CONNECTED
        return YubiKeyStatus.NOT_CONNECTED

    def _connect(self) -> None:
        """Establish connection to YubiKey device.

        Raises:
            DeviceNotFoundError: If no YubiKey is found.
        """
        try:
            devices = list(list_all_devices())
            if not devices:
                raise DeviceNotFoundError("No YubiKey device found")

            device, device_info = devices[0]
            self._device = device
            self._connection = device.open_connection(SmartCardConnection)
            self._oath_session = OathSession(self._connection)

            logger.info(f"Connected to YubiKey: {device_info}")
        except DeviceNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to connect to YubiKey: {e}")
            raise DeviceNotFoundError(f"Failed to connect to YubiKey: {e}") from e

    def _disconnect(self) -> None:
        """Disconnect from YubiKey device."""
        if self._connection:
            try:
                self._connection.close()
                logger.debug("Disconnected from YubiKey")
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")
            finally:
                self._connection = None
                self._oath_session = None
                self._device = None

    def list_accounts(self) -> list[str]:
        """List all OATH accounts on the YubiKey.

        Returns:
            list[str]: List of account names.

        Raises:
            DeviceNotFoundError: If no YubiKey is found.
            DeviceRemovedError: If device is removed during operation.
        """
        try:
            self._connect()

            if not self._oath_session:
                raise DeviceNotFoundError("OATH session not initialized")

            credentials = self._oath_session.list_credentials()
            account_names = [cred.name for cred in credentials]

            logger.info(f"Found {len(account_names)} OATH accounts")
            logger.debug(f"Accounts: {account_names}")

            return account_names

        except DeviceNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error listing accounts: {e}")
            raise DeviceRemovedError(f"Device error while listing accounts: {e}") from e
        finally:
            self._disconnect()

    def generate_totp(
        self, account: str | None = None, require_touch: bool = True
    ) -> dict[str, str] | str:
        """Generate TOTP code for an account.

        Args:
            account: Account name. If None, returns all accounts (touch required for each).
            require_touch: Whether to require physical touch (default: True).

        Returns:
            dict[str, str] | str: Dictionary of account:code pairs if account is None,
                                  or single code string if account is specified.

        Raises:
            DeviceNotFoundError: If no YubiKey is found.
            DeviceRemovedError: If device is removed during operation.
            AccountNotFoundError: If specified account is not found.
            TouchTimeoutError: If user doesn't touch YubiKey in time.
        """
        try:
            self._connect()

            if not self._oath_session:
                raise DeviceNotFoundError("OATH session not initialized")

            # Get all credentials
            credentials = self._oath_session.list_credentials()

            if not credentials:
                logger.warning("No OATH credentials found on YubiKey")
                return {} if account is None else ""

            # If specific account requested, filter to that account
            if account:
                matching_creds = [c for c in credentials if c.name == account]
                if not matching_creds:
                    available = [c.name for c in credentials]
                    raise AccountNotFoundError(
                        f"Account '{account}' not found. Available: {available}"
                    )
                credentials = matching_creds

            # Generate codes
            result: dict[str, str] = {}

            try:
                # First, try calculate_all() for credentials that don't require touch
                codes = self._oath_session.calculate_all()

                # Process each credential
                for cred in credentials:
                    if cred in codes and codes[cred] is not None:
                        # Code available from calculate_all (no touch required)
                        code_value = codes[cred]
                        if code_value is not None and hasattr(code_value, "value"):
                            result[cred.name] = code_value.value
                        elif code_value is not None:
                            result[cred.name] = str(code_value)
                    else:
                        # Credential requires touch - calculate individually
                        logger.debug(f"Calculating code with touch for: {cred.name}")
                        code = self._oath_session.calculate_code(cred)
                        if code is not None and hasattr(code, "value"):
                            result[cred.name] = code.value
                        elif code is not None:
                            result[cred.name] = str(code)

                logger.info(f"Generated TOTP codes for {len(result)} accounts")

                # Return single code or dictionary
                if account:
                    return result.get(account, "")
                return result

            except Exception as e:
                error_msg = str(e).lower()
                if "touch" in error_msg or "timeout" in error_msg:
                    raise TouchTimeoutError(
                        "YubiKey touch timeout - user did not touch device in time"
                    ) from e
                raise

        except (DeviceNotFoundError, AccountNotFoundError, TouchTimeoutError):
            raise
        except Exception as e:
            logger.error(f"Error generating TOTP: {e}")
            raise DeviceRemovedError(f"Device error while generating TOTP: {e}") from e
        finally:
            self._disconnect()

    def get_device_info(self) -> dict[str, Any]:
        """Get YubiKey device information.

        Returns:
            dict[str, Any]: Device information including serial, version, etc.

        Raises:
            DeviceNotFoundError: If no YubiKey is found.
        """
        try:
            devices = list(list_all_devices())
            if not devices:
                raise DeviceNotFoundError("No YubiKey device found")

            device, device_info = devices[0]

            info = {
                "name": str(device_info.name) if hasattr(device_info, "name") else "Unknown",
                "serial": (str(device_info.serial) if hasattr(device_info, "serial") else None),
                "version": (str(device_info.version) if hasattr(device_info, "version") else None),
                "transport": (
                    str(device_info.transport) if hasattr(device_info, "transport") else None
                ),
            }

            logger.info(f"Device info retrieved: {info}")
            return info

        except DeviceNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error getting device info: {e}")
            raise DeviceNotFoundError(f"Failed to get device info: {e}") from e
