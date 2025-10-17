"""Unit tests for YubiKey OATH-TOTP interface module."""

from unittest.mock import Mock, patch

import pytest

from yk_daemon.yubikey import (
    AccountNotFoundError,
    DeviceNotFoundError,
    DeviceRemovedError,
    TouchTimeoutError,
    YubiKeyInterface,
    YubiKeyStatus,
)


@pytest.fixture
def yubikey_interface() -> YubiKeyInterface:
    """Create a YubiKey interface instance for testing."""
    return YubiKeyInterface()


@pytest.fixture
def mock_device() -> Mock:
    """Create a mock YubiKey device."""
    device = Mock()
    mock_connection = Mock()
    mock_connection.close = Mock()
    device.open_connection = Mock(return_value=mock_connection)
    # Store connection for test assertions
    device._test_connection = mock_connection
    return device


@pytest.fixture
def mock_device_info() -> Mock:
    """Create mock device info."""
    info = Mock()
    info.name = "YubiKey 5 NFC"
    info.serial = "12345678"
    info.version = "5.4.3"
    info.transport = "USB"
    return info


@pytest.fixture
def mock_credential() -> Mock:
    """Create a mock OATH credential."""
    cred = Mock()
    cred.name = "test@example.com"
    return cred


@pytest.fixture
def mock_code() -> Mock:
    """Create a mock TOTP code."""
    code = Mock()
    code.value = "123456"
    return code


class TestYubiKeyInterface:
    """Test cases for YubiKeyInterface class."""

    def test_init(self, yubikey_interface: YubiKeyInterface) -> None:
        """Test YubiKeyInterface initialization."""
        assert yubikey_interface._device is None
        assert yubikey_interface._connection is None
        assert yubikey_interface._oath_session is None

    @patch("yk_daemon.yubikey.list_all_devices")
    def test_detect_device_found(
        self, mock_list_devices: Mock, yubikey_interface: YubiKeyInterface
    ) -> None:
        """Test device detection when YubiKey is connected."""
        mock_list_devices.return_value = [(Mock(), Mock())]

        result = yubikey_interface.detect_device()

        assert result is True
        mock_list_devices.assert_called_once()

    @patch("yk_daemon.yubikey.list_all_devices")
    def test_detect_device_not_found(
        self, mock_list_devices: Mock, yubikey_interface: YubiKeyInterface
    ) -> None:
        """Test device detection when no YubiKey is connected."""
        mock_list_devices.return_value = []

        result = yubikey_interface.detect_device()

        assert result is False
        mock_list_devices.assert_called_once()

    @patch("yk_daemon.yubikey.list_all_devices")
    def test_detect_device_error(
        self, mock_list_devices: Mock, yubikey_interface: YubiKeyInterface
    ) -> None:
        """Test device detection handles errors gracefully."""
        mock_list_devices.side_effect = Exception("USB error")

        result = yubikey_interface.detect_device()

        assert result is False

    @patch("yk_daemon.yubikey.list_all_devices")
    def test_get_status_connected(
        self, mock_list_devices: Mock, yubikey_interface: YubiKeyInterface
    ) -> None:
        """Test get_status returns CONNECTED when device is present."""
        mock_list_devices.return_value = [(Mock(), Mock())]

        status = yubikey_interface.get_status()

        assert status == YubiKeyStatus.CONNECTED

    @patch("yk_daemon.yubikey.list_all_devices")
    def test_get_status_not_connected(
        self, mock_list_devices: Mock, yubikey_interface: YubiKeyInterface
    ) -> None:
        """Test get_status returns NOT_CONNECTED when device is absent."""
        mock_list_devices.return_value = []

        status = yubikey_interface.get_status()

        assert status == YubiKeyStatus.NOT_CONNECTED

    @patch("yk_daemon.yubikey.OathSession")
    @patch("yk_daemon.yubikey.list_all_devices")
    def test_list_accounts_success(
        self,
        mock_list_devices: Mock,
        mock_oath_session: Mock,
        yubikey_interface: YubiKeyInterface,
        mock_device: Mock,
        mock_device_info: Mock,
    ) -> None:
        """Test listing OATH accounts successfully."""
        mock_list_devices.return_value = [(mock_device, mock_device_info)]

        cred1 = Mock()
        cred1.name = "account1@example.com"
        cred2 = Mock()
        cred2.name = "account2@example.com"

        mock_session_instance = Mock()
        mock_session_instance.list_credentials.return_value = [cred1, cred2]
        mock_oath_session.return_value = mock_session_instance

        accounts = yubikey_interface.list_accounts()

        assert len(accounts) == 2
        assert "account1@example.com" in accounts
        assert "account2@example.com" in accounts
        mock_device._test_connection.close.assert_called_once()

    @patch("yk_daemon.yubikey.list_all_devices")
    def test_list_accounts_no_device(
        self, mock_list_devices: Mock, yubikey_interface: YubiKeyInterface
    ) -> None:
        """Test listing accounts raises error when no device found."""
        mock_list_devices.return_value = []

        with pytest.raises(DeviceNotFoundError, match="No YubiKey device found"):
            yubikey_interface.list_accounts()

    @patch("yk_daemon.yubikey.OathSession")
    @patch("yk_daemon.yubikey.list_all_devices")
    def test_list_accounts_device_removed(
        self,
        mock_list_devices: Mock,
        mock_oath_session: Mock,
        yubikey_interface: YubiKeyInterface,
        mock_device: Mock,
        mock_device_info: Mock,
    ) -> None:
        """Test listing accounts handles device removal during operation."""
        mock_list_devices.return_value = [(mock_device, mock_device_info)]

        mock_session_instance = Mock()
        mock_session_instance.list_credentials.side_effect = Exception("Device disconnected")
        mock_oath_session.return_value = mock_session_instance

        with pytest.raises(DeviceRemovedError, match="Device error while listing accounts"):
            yubikey_interface.list_accounts()

        mock_device._test_connection.close.assert_called_once()

    @patch("yk_daemon.yubikey.OathSession")
    @patch("yk_daemon.yubikey.list_all_devices")
    def test_generate_totp_single_account(
        self,
        mock_list_devices: Mock,
        mock_oath_session: Mock,
        yubikey_interface: YubiKeyInterface,
        mock_device: Mock,
        mock_device_info: Mock,
    ) -> None:
        """Test generating TOTP for a single account."""
        mock_list_devices.return_value = [(mock_device, mock_device_info)]

        cred = Mock()
        cred.name = "test@example.com"

        code = Mock()
        code.value = "123456"

        mock_session_instance = Mock()
        mock_session_instance.list_credentials.return_value = [cred]
        mock_session_instance.calculate_all.return_value = {cred: code}
        mock_oath_session.return_value = mock_session_instance

        result = yubikey_interface.generate_totp("test@example.com")

        assert result == "123456"
        mock_device._test_connection.close.assert_called_once()

    @patch("yk_daemon.yubikey.OathSession")
    @patch("yk_daemon.yubikey.list_all_devices")
    def test_generate_totp_all_accounts(
        self,
        mock_list_devices: Mock,
        mock_oath_session: Mock,
        yubikey_interface: YubiKeyInterface,
        mock_device: Mock,
        mock_device_info: Mock,
    ) -> None:
        """Test generating TOTP for all accounts."""
        mock_list_devices.return_value = [(mock_device, mock_device_info)]

        cred1 = Mock()
        cred1.name = "account1@example.com"
        cred2 = Mock()
        cred2.name = "account2@example.com"

        code1 = Mock()
        code1.value = "123456"
        code2 = Mock()
        code2.value = "654321"

        mock_session_instance = Mock()
        mock_session_instance.list_credentials.return_value = [cred1, cred2]
        mock_session_instance.calculate_all.return_value = {
            cred1: code1,
            cred2: code2,
        }
        mock_oath_session.return_value = mock_session_instance

        result = yubikey_interface.generate_totp()

        assert isinstance(result, dict)
        assert len(result) == 2
        assert result["account1@example.com"] == "123456"
        assert result["account2@example.com"] == "654321"
        mock_device._test_connection.close.assert_called_once()

    @patch("yk_daemon.yubikey.OathSession")
    @patch("yk_daemon.yubikey.list_all_devices")
    def test_generate_totp_account_not_found(
        self,
        mock_list_devices: Mock,
        mock_oath_session: Mock,
        yubikey_interface: YubiKeyInterface,
        mock_device: Mock,
        mock_device_info: Mock,
    ) -> None:
        """Test generating TOTP raises error for non-existent account."""
        mock_list_devices.return_value = [(mock_device, mock_device_info)]

        cred = Mock()
        cred.name = "existing@example.com"

        mock_session_instance = Mock()
        mock_session_instance.list_credentials.return_value = [cred]
        mock_oath_session.return_value = mock_session_instance

        with pytest.raises(
            AccountNotFoundError, match="Account 'nonexistent@example.com' not found"
        ):
            yubikey_interface.generate_totp("nonexistent@example.com")

        mock_device._test_connection.close.assert_called_once()

    @patch("yk_daemon.yubikey.OathSession")
    @patch("yk_daemon.yubikey.list_all_devices")
    def test_generate_totp_touch_timeout(
        self,
        mock_list_devices: Mock,
        mock_oath_session: Mock,
        yubikey_interface: YubiKeyInterface,
        mock_device: Mock,
        mock_device_info: Mock,
    ) -> None:
        """Test generating TOTP raises error on touch timeout."""
        mock_list_devices.return_value = [(mock_device, mock_device_info)]

        cred = Mock()
        cred.name = "test@example.com"

        mock_session_instance = Mock()
        mock_session_instance.list_credentials.return_value = [cred]
        mock_session_instance.calculate_all.side_effect = Exception("Touch timeout")
        mock_oath_session.return_value = mock_session_instance

        with pytest.raises(TouchTimeoutError, match="YubiKey touch timeout"):
            yubikey_interface.generate_totp("test@example.com")

        mock_device._test_connection.close.assert_called_once()

    @patch("yk_daemon.yubikey.OathSession")
    @patch("yk_daemon.yubikey.list_all_devices")
    def test_generate_totp_no_credentials(
        self,
        mock_list_devices: Mock,
        mock_oath_session: Mock,
        yubikey_interface: YubiKeyInterface,
        mock_device: Mock,
        mock_device_info: Mock,
    ) -> None:
        """Test generating TOTP with no credentials on YubiKey."""
        mock_list_devices.return_value = [(mock_device, mock_device_info)]

        mock_session_instance = Mock()
        mock_session_instance.list_credentials.return_value = []
        mock_oath_session.return_value = mock_session_instance

        result = yubikey_interface.generate_totp()

        assert result == {}
        mock_device._test_connection.close.assert_called_once()

    @patch("yk_daemon.yubikey.list_all_devices")
    def test_get_device_info_success(
        self,
        mock_list_devices: Mock,
        yubikey_interface: YubiKeyInterface,
        mock_device: Mock,
        mock_device_info: Mock,
    ) -> None:
        """Test getting device information successfully."""
        mock_list_devices.return_value = [(mock_device, mock_device_info)]

        info = yubikey_interface.get_device_info()

        assert info["name"] == "YubiKey 5 NFC"
        assert info["serial"] == "12345678"
        assert info["version"] == "5.4.3"
        assert info["transport"] == "USB"

    @patch("yk_daemon.yubikey.list_all_devices")
    def test_get_device_info_no_device(
        self, mock_list_devices: Mock, yubikey_interface: YubiKeyInterface
    ) -> None:
        """Test getting device info raises error when no device found."""
        mock_list_devices.return_value = []

        with pytest.raises(DeviceNotFoundError, match="No YubiKey device found"):
            yubikey_interface.get_device_info()

    @patch("yk_daemon.yubikey.OathSession")
    @patch("yk_daemon.yubikey.list_all_devices")
    def test_disconnect_on_error(
        self,
        mock_list_devices: Mock,
        mock_oath_session: Mock,
        yubikey_interface: YubiKeyInterface,
        mock_device: Mock,
        mock_device_info: Mock,
    ) -> None:
        """Test device is disconnected even when errors occur."""
        mock_list_devices.return_value = [(mock_device, mock_device_info)]

        mock_session_instance = Mock()
        mock_session_instance.list_credentials.side_effect = Exception("Test error")
        mock_oath_session.return_value = mock_session_instance

        with pytest.raises(DeviceRemovedError):
            yubikey_interface.list_accounts()

        # Ensure disconnect was called even though an error occurred
        mock_device._test_connection.close.assert_called_once()

    @patch("yk_daemon.yubikey.OathSession")
    @patch("yk_daemon.yubikey.list_all_devices")
    def test_disconnect_handles_close_error(
        self,
        mock_list_devices: Mock,
        mock_oath_session: Mock,
        yubikey_interface: YubiKeyInterface,
        mock_device: Mock,
        mock_device_info: Mock,
    ) -> None:
        """Test disconnect handles errors during device.close() gracefully."""
        mock_list_devices.return_value = [(mock_device, mock_device_info)]

        cred = Mock()
        cred.name = "test@example.com"

        mock_session_instance = Mock()
        mock_session_instance.list_credentials.return_value = [cred]
        mock_oath_session.return_value = mock_session_instance

        # Make close() raise an error
        mock_device._test_connection.close.side_effect = Exception("Close error")

        # Should not raise error, just log warning
        accounts = yubikey_interface.list_accounts()

        assert len(accounts) == 1
        assert "test@example.com" in accounts
