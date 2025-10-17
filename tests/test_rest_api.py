"""Unit tests for REST API server."""

from unittest.mock import Mock, patch

import pytest
from flask import Flask
from flask.testing import FlaskClient

from yk_daemon.config import RestApiConfig
from yk_daemon.rest_api import create_app
from yk_daemon.yubikey import (
    AccountNotFoundError,
    DeviceNotFoundError,
    DeviceRemovedError,
    TouchTimeoutError,
    YubiKeyStatus,
)


@pytest.fixture
def rest_api_config() -> RestApiConfig:
    """Create a REST API configuration for testing."""
    return RestApiConfig(enabled=True, host="127.0.0.1", port=5000)


@pytest.fixture
def mock_yubikey() -> Mock:
    """Create a mock YubiKey interface."""
    return Mock()


@pytest.fixture
def app(rest_api_config: RestApiConfig, mock_yubikey: Mock) -> Flask:
    """Create Flask app for testing."""
    return create_app(rest_api_config, mock_yubikey)


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    """Create Flask test client."""
    app.config["TESTING"] = True
    return app.test_client()


class TestHealthEndpoint:
    """Test cases for /health endpoint."""

    def test_health_yubikey_connected(self, client: FlaskClient, mock_yubikey: Mock) -> None:
        """Test health check when YubiKey is connected."""
        mock_yubikey.get_status.return_value = YubiKeyStatus.CONNECTED

        response = client.get("/health")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["status"] == "healthy"
        assert data["yubikey_status"] == "connected"
        assert "timestamp" in data

    def test_health_yubikey_not_connected(self, client: FlaskClient, mock_yubikey: Mock) -> None:
        """Test health check when YubiKey is not connected."""
        mock_yubikey.get_status.return_value = YubiKeyStatus.NOT_CONNECTED

        response = client.get("/health")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["status"] == "healthy"
        assert data["yubikey_status"] == "not_connected"
        assert "timestamp" in data

    def test_health_yubikey_busy(self, client: FlaskClient, mock_yubikey: Mock) -> None:
        """Test health check when YubiKey is busy."""
        mock_yubikey.get_status.return_value = YubiKeyStatus.BUSY

        response = client.get("/health")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["yubikey_status"] == "busy"


class TestListAccountsEndpoint:
    """Test cases for /api/accounts endpoint."""

    def test_list_accounts_success(self, client: FlaskClient, mock_yubikey: Mock) -> None:
        """Test listing accounts successfully."""
        mock_yubikey.list_accounts.return_value = [
            "account1@example.com",
            "account2@example.com",
        ]

        response = client.get("/api/accounts")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert len(data["accounts"]) == 2
        assert "account1@example.com" in data["accounts"]
        assert "account2@example.com" in data["accounts"]
        assert data["count"] == 2
        assert "timestamp" in data

    def test_list_accounts_empty(self, client: FlaskClient, mock_yubikey: Mock) -> None:
        """Test listing accounts when no accounts exist."""
        mock_yubikey.list_accounts.return_value = []

        response = client.get("/api/accounts")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["accounts"] == []
        assert data["count"] == 0

    def test_list_accounts_device_not_found(self, client: FlaskClient, mock_yubikey: Mock) -> None:
        """Test listing accounts when YubiKey is not connected."""
        mock_yubikey.list_accounts.side_effect = DeviceNotFoundError("No YubiKey device found")

        response = client.get("/api/accounts")

        assert response.status_code == 503
        data = response.get_json()
        assert data["success"] is False
        assert data["error"] == "YubiKey not connected"
        assert "timestamp" in data

    def test_list_accounts_device_removed(self, client: FlaskClient, mock_yubikey: Mock) -> None:
        """Test listing accounts when YubiKey is removed during operation."""
        mock_yubikey.list_accounts.side_effect = DeviceRemovedError(
            "Device disconnected during operation"
        )

        response = client.get("/api/accounts")

        assert response.status_code == 503
        data = response.get_json()
        assert data["success"] is False
        assert data["error"] == "YubiKey disconnected during operation"

    def test_list_accounts_internal_error(self, client: FlaskClient, mock_yubikey: Mock) -> None:
        """Test listing accounts with internal error."""
        mock_yubikey.list_accounts.side_effect = Exception("Unexpected error")

        response = client.get("/api/accounts")

        assert response.status_code == 500
        data = response.get_json()
        assert data["success"] is False
        assert data["error"] == "Internal server error"


class TestGetDefaultTotpEndpoint:
    """Test cases for /api/totp endpoint."""

    def test_get_default_totp_success(self, client: FlaskClient, mock_yubikey: Mock) -> None:
        """Test getting TOTP for default account successfully."""
        mock_yubikey.list_accounts.return_value = ["default@example.com"]
        mock_yubikey.generate_totp.return_value = "123456"

        response = client.get("/api/totp")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["account"] == "default@example.com"
        assert data["code"] == "123456"
        assert "timestamp" in data

    def test_get_default_totp_no_accounts(self, client: FlaskClient, mock_yubikey: Mock) -> None:
        """Test getting TOTP when no accounts exist."""
        mock_yubikey.list_accounts.return_value = []

        response = client.get("/api/totp")

        assert response.status_code == 404
        data = response.get_json()
        assert data["success"] is False
        assert data["error"] == "No accounts found"

    def test_get_default_totp_device_not_found(
        self, client: FlaskClient, mock_yubikey: Mock
    ) -> None:
        """Test getting TOTP when YubiKey is not connected."""
        mock_yubikey.list_accounts.side_effect = DeviceNotFoundError("No YubiKey device found")

        response = client.get("/api/totp")

        assert response.status_code == 503
        data = response.get_json()
        assert data["success"] is False
        assert data["error"] == "YubiKey not connected"

    def test_get_default_totp_touch_timeout(self, client: FlaskClient, mock_yubikey: Mock) -> None:
        """Test getting TOTP with touch timeout."""
        mock_yubikey.list_accounts.return_value = ["default@example.com"]
        mock_yubikey.generate_totp.side_effect = TouchTimeoutError("Touch timeout")

        response = client.get("/api/totp")

        assert response.status_code == 408
        data = response.get_json()
        assert data["success"] is False
        assert data["error"] == "Touch timeout"

    def test_get_default_totp_device_removed(self, client: FlaskClient, mock_yubikey: Mock) -> None:
        """Test getting TOTP when device is removed during operation."""
        mock_yubikey.list_accounts.return_value = ["default@example.com"]
        mock_yubikey.generate_totp.side_effect = DeviceRemovedError("Device removed")

        response = client.get("/api/totp")

        assert response.status_code == 503
        data = response.get_json()
        assert data["success"] is False
        assert data["error"] == "YubiKey disconnected during operation"

    def test_get_default_totp_internal_error(self, client: FlaskClient, mock_yubikey: Mock) -> None:
        """Test getting TOTP with internal error."""
        mock_yubikey.list_accounts.return_value = ["default@example.com"]
        mock_yubikey.generate_totp.side_effect = Exception("Unexpected error")

        response = client.get("/api/totp")

        assert response.status_code == 500
        data = response.get_json()
        assert data["success"] is False
        assert data["error"] == "Internal server error"


class TestGetTotpForAccountEndpoint:
    """Test cases for /api/totp/<account> endpoint."""

    def test_get_totp_for_account_success(self, client: FlaskClient, mock_yubikey: Mock) -> None:
        """Test getting TOTP for specific account successfully."""
        mock_yubikey.generate_totp.return_value = "654321"

        response = client.get("/api/totp/test@example.com")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["account"] == "test@example.com"
        assert data["code"] == "654321"
        assert "timestamp" in data

    def test_get_totp_for_account_with_special_chars(
        self, client: FlaskClient, mock_yubikey: Mock
    ) -> None:
        """Test getting TOTP for account with special characters."""
        mock_yubikey.generate_totp.return_value = "111111"

        response = client.get("/api/totp/user+tag@example.com")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["account"] == "user+tag@example.com"

    def test_get_totp_for_account_not_found(self, client: FlaskClient, mock_yubikey: Mock) -> None:
        """Test getting TOTP for non-existent account."""
        mock_yubikey.generate_totp.side_effect = AccountNotFoundError(
            "Account 'nonexistent@example.com' not found"
        )

        response = client.get("/api/totp/nonexistent@example.com")

        assert response.status_code == 404
        data = response.get_json()
        assert data["success"] is False
        assert data["error"] == "Account not found"

    def test_get_totp_for_account_device_not_found(
        self, client: FlaskClient, mock_yubikey: Mock
    ) -> None:
        """Test getting TOTP when YubiKey is not connected."""
        mock_yubikey.generate_totp.side_effect = DeviceNotFoundError("No YubiKey device found")

        response = client.get("/api/totp/test@example.com")

        assert response.status_code == 503
        data = response.get_json()
        assert data["success"] is False
        assert data["error"] == "YubiKey not connected"

    def test_get_totp_for_account_touch_timeout(
        self, client: FlaskClient, mock_yubikey: Mock
    ) -> None:
        """Test getting TOTP with touch timeout."""
        mock_yubikey.generate_totp.side_effect = TouchTimeoutError("Touch timeout")

        response = client.get("/api/totp/test@example.com")

        assert response.status_code == 408
        data = response.get_json()
        assert data["success"] is False
        assert data["error"] == "Touch timeout"

    def test_get_totp_for_account_device_removed(
        self, client: FlaskClient, mock_yubikey: Mock
    ) -> None:
        """Test getting TOTP when device is removed during operation."""
        mock_yubikey.generate_totp.side_effect = DeviceRemovedError("Device removed")

        response = client.get("/api/totp/test@example.com")

        assert response.status_code == 503
        data = response.get_json()
        assert data["success"] is False
        assert data["error"] == "YubiKey disconnected during operation"

    def test_get_totp_for_account_empty_code(self, client: FlaskClient, mock_yubikey: Mock) -> None:
        """Test getting TOTP returns empty code."""
        mock_yubikey.generate_totp.return_value = ""

        response = client.get("/api/totp/test@example.com")

        assert response.status_code == 500
        data = response.get_json()
        assert data["success"] is False
        assert data["error"] == "Failed to generate code"

    def test_get_totp_for_account_internal_error(
        self, client: FlaskClient, mock_yubikey: Mock
    ) -> None:
        """Test getting TOTP with internal error."""
        mock_yubikey.generate_totp.side_effect = Exception("Unexpected error")

        response = client.get("/api/totp/test@example.com")

        assert response.status_code == 500
        data = response.get_json()
        assert data["success"] is False
        assert data["error"] == "Internal server error"


class TestRequestLogging:
    """Test cases for request/response logging."""

    @patch("yk_daemon.rest_api.logger")
    def test_request_logging(
        self, mock_logger: Mock, client: FlaskClient, mock_yubikey: Mock
    ) -> None:
        """Test that requests are logged."""
        mock_yubikey.get_status.return_value = YubiKeyStatus.CONNECTED

        client.get("/health")

        # Check that info was called for request logging
        info_calls = list(mock_logger.info.call_args_list)
        assert any("GET" in str(call) and "/health" in str(call) for call in info_calls)

    @patch("yk_daemon.rest_api.logger")
    def test_response_logging(
        self, mock_logger: Mock, client: FlaskClient, mock_yubikey: Mock
    ) -> None:
        """Test that responses are logged."""
        mock_yubikey.get_status.return_value = YubiKeyStatus.CONNECTED

        client.get("/health")

        # Check that info was called for response logging
        info_calls = list(mock_logger.info.call_args_list)
        assert any("200" in str(call) for call in info_calls)


class TestCreateApp:
    """Test cases for create_app function."""

    def test_create_app_with_config(self, rest_api_config: RestApiConfig) -> None:
        """Test creating app with configuration."""
        app = create_app(rest_api_config)

        assert app is not None
        assert "YUBIKEY" in app.config

    def test_create_app_with_yubikey(
        self, rest_api_config: RestApiConfig, mock_yubikey: Mock
    ) -> None:
        """Test creating app with provided YubiKey interface."""
        app = create_app(rest_api_config, mock_yubikey)

        assert app.config["YUBIKEY"] == mock_yubikey

    def test_create_app_creates_yubikey_if_none(self, rest_api_config: RestApiConfig) -> None:
        """Test creating app creates YubiKey interface if not provided."""
        app = create_app(rest_api_config, None)

        assert app.config["YUBIKEY"] is not None
        assert hasattr(app.config["YUBIKEY"], "get_status")


class TestEndpointIntegration:
    """Integration tests for multiple endpoints."""

    def test_multiple_requests(self, client: FlaskClient, mock_yubikey: Mock) -> None:
        """Test making multiple requests to different endpoints."""
        mock_yubikey.get_status.return_value = YubiKeyStatus.CONNECTED
        mock_yubikey.list_accounts.return_value = ["test@example.com"]
        mock_yubikey.generate_totp.return_value = "123456"

        # Health check
        response1 = client.get("/health")
        assert response1.status_code == 200

        # List accounts
        response2 = client.get("/api/accounts")
        assert response2.status_code == 200

        # Get TOTP
        response3 = client.get("/api/totp/test@example.com")
        assert response3.status_code == 200

    def test_error_recovery(self, client: FlaskClient, mock_yubikey: Mock) -> None:
        """Test that API recovers from errors."""
        # First request fails
        mock_yubikey.list_accounts.side_effect = DeviceNotFoundError("Device not found")
        response1 = client.get("/api/accounts")
        assert response1.status_code == 503

        # Second request succeeds
        mock_yubikey.list_accounts.side_effect = None
        mock_yubikey.list_accounts.return_value = ["test@example.com"]
        response2 = client.get("/api/accounts")
        assert response2.status_code == 200
