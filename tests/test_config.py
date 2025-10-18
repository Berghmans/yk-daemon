"""Tests for configuration management module."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from yk_daemon.config import (
    Config,
    ConfigurationError,
    LoggingConfig,
    NotificationsConfig,
    RestApiConfig,
    SocketConfig,
    load_config,
)


class TestRestApiConfig:
    """Tests for RestApiConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = RestApiConfig()
        assert config.enabled is True
        assert config.host == "127.0.0.1"
        assert config.port == 5100

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = RestApiConfig(enabled=False, host="localhost", port=8080)
        assert config.enabled is False
        assert config.host == "localhost"
        assert config.port == 8080

    def test_validate_valid_config(self) -> None:
        """Test validation passes for valid config."""
        config = RestApiConfig()
        config.validate()  # Should not raise

    def test_validate_invalid_enabled_type(self) -> None:
        """Test validation fails for invalid enabled type."""
        config = RestApiConfig()
        config.enabled = "true"  # type: ignore[assignment]  # Intentional for testing validation
        with pytest.raises(ConfigurationError, match="rest_api.enabled must be a boolean"):
            config.validate()

    def test_validate_invalid_host_type(self) -> None:
        """Test validation fails for invalid host type."""
        config = RestApiConfig()
        config.host = 127001  # type: ignore[assignment]  # Intentional for testing validation
        with pytest.raises(ConfigurationError, match="rest_api.host must be a string"):
            config.validate()

    def test_validate_invalid_port_type(self) -> None:
        """Test validation fails for invalid port type."""
        config = RestApiConfig()
        config.port = "5100"  # type: ignore[assignment]  # Intentional for testing validation
        with pytest.raises(ConfigurationError, match="rest_api.port must be an integer"):
            config.validate()

    def test_validate_invalid_port_range_low(self) -> None:
        """Test validation fails for port below valid range."""
        config = RestApiConfig(port=0)
        with pytest.raises(ConfigurationError, match="rest_api.port must be between"):
            config.validate()

    def test_validate_invalid_port_range_high(self) -> None:
        """Test validation fails for port above valid range."""
        config = RestApiConfig(port=65536)
        with pytest.raises(ConfigurationError, match="rest_api.port must be between"):
            config.validate()

    def test_validate_warns_non_localhost_host(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test validation warns for non-localhost host."""
        config = RestApiConfig(host="0.0.0.0")
        config.validate()
        assert "security" in caplog.text.lower()


class TestSocketConfig:
    """Tests for SocketConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = SocketConfig()
        assert config.enabled is True
        assert config.host == "127.0.0.1"
        assert config.port == 5101

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = SocketConfig(enabled=False, host="localhost", port=9090)
        assert config.enabled is False
        assert config.host == "localhost"
        assert config.port == 9090

    def test_validate_valid_config(self) -> None:
        """Test validation passes for valid config."""
        config = SocketConfig()
        config.validate()  # Should not raise

    def test_validate_invalid_port_range(self) -> None:
        """Test validation fails for invalid port."""
        config = SocketConfig(port=100000)
        with pytest.raises(ConfigurationError, match="socket.port must be between"):
            config.validate()


class TestNotificationsConfig:
    """Tests for NotificationsConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = NotificationsConfig()
        assert config.popup is True
        assert config.sound is True
        assert config.sound_file == "notification.wav"

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = NotificationsConfig(popup=False, sound=False, sound_file="custom.wav")
        assert config.popup is False
        assert config.sound is False
        assert config.sound_file == "custom.wav"

    def test_validate_valid_config(self) -> None:
        """Test validation passes for valid config."""
        config = NotificationsConfig()
        config.validate()  # Should not raise

    def test_validate_invalid_popup_type(self) -> None:
        """Test validation fails for invalid popup type."""
        config = NotificationsConfig()
        config.popup = "yes"  # type: ignore[assignment]  # Intentional for testing validation
        with pytest.raises(ConfigurationError, match="notifications.popup must be a boolean"):
            config.validate()

    def test_validate_allows_missing_sound_file(self) -> None:
        """Test validation passes even when sound file doesn't exist.

        File existence is checked by Notifier class during initialization,
        not during config validation.
        """
        config = NotificationsConfig(sound=True, sound_file="nonexistent.wav")
        config.validate()  # Should not raise or warn


class TestLoggingConfig:
    """Tests for LoggingConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = LoggingConfig()
        assert config.level == "INFO"
        assert config.file == "yk-daemon.log"

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = LoggingConfig(level="DEBUG", file="custom.log")
        assert config.level == "DEBUG"
        assert config.file == "custom.log"

    def test_validate_valid_config(self) -> None:
        """Test validation passes for valid config."""
        config = LoggingConfig()
        config.validate()  # Should not raise

    def test_validate_normalizes_level_case(self) -> None:
        """Test validation normalizes log level to uppercase."""
        config = LoggingConfig(level="debug")
        config.validate()
        assert config.level == "DEBUG"

    def test_validate_invalid_level(self) -> None:
        """Test validation fails for invalid log level."""
        config = LoggingConfig(level="INVALID")
        with pytest.raises(ConfigurationError, match="logging.level must be one of"):
            config.validate()

    def test_validate_invalid_level_type(self) -> None:
        """Test validation fails for invalid level type."""
        config = LoggingConfig()
        config.level = 123  # type: ignore[assignment]  # Intentional for testing validation
        with pytest.raises(ConfigurationError, match="logging.level must be a string"):
            config.validate()


class TestConfig:
    """Tests for main Config class."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = Config()
        assert isinstance(config.rest_api, RestApiConfig)
        assert isinstance(config.socket, SocketConfig)
        assert isinstance(config.notifications, NotificationsConfig)
        assert isinstance(config.logging, LoggingConfig)

    def test_validate_valid_config(self) -> None:
        """Test validation passes for valid config."""
        config = Config()
        config.validate()  # Should not raise

    def test_validate_calls_sub_config_validation(self) -> None:
        """Test that validation calls all sub-config validations."""
        config = Config()
        config.rest_api.port = -1
        with pytest.raises(ConfigurationError, match="rest_api.port"):
            config.validate()

    def test_validate_port_conflict(self) -> None:
        """Test validation fails when REST API and socket use same port."""
        config = Config()
        config.rest_api.port = 5100
        config.socket.port = 5100
        with pytest.raises(ConfigurationError, match="cannot use the same host:port combination"):
            config.validate()

    def test_validate_both_disabled(self) -> None:
        """Test validation fails when both REST API and socket are disabled."""
        config = Config()
        config.rest_api.enabled = False
        config.socket.enabled = False
        with pytest.raises(
            ConfigurationError, match="At least one of rest_api or socket must be enabled"
        ):
            config.validate()

    def test_validate_allows_different_ports(self) -> None:
        """Test validation passes when ports are different."""
        config = Config()
        config.rest_api.port = 5100
        config.socket.port = 5101
        config.validate()  # Should not raise


class TestLoadConfig:
    """Tests for load_config function."""

    def test_build_config_with_factory_defaults(self) -> None:
        """Test that _build_config_from_dict works with field(default_factory=...) defaults.

        This test ensures we don't try to access LoggingConfig.file as a class attribute,
        which would fail because it uses default_factory instead of a simple default.
        """
        from yk_daemon.config import _build_config_from_dict

        # Empty dict should use all defaults, including factory defaults
        config = _build_config_from_dict({})
        assert config.logging.level == "INFO"
        assert config.logging.file  # Should have a value from factory
        assert isinstance(config.logging.file, str)

    def test_load_config_no_file_uses_defaults(self, tmp_path: Path) -> None:
        """Test loading config without file uses defaults."""
        os.chdir(tmp_path)
        config = load_config("nonexistent.json")

        assert config.rest_api.enabled is True
        assert config.rest_api.port == 5100
        assert config.socket.enabled is True
        assert config.socket.port == 5101
        assert config.logging.level == "INFO"
        assert config.logging.file  # Ensure log file path is set
        assert config.notifications.popup is True

    def test_load_config_from_file(self, tmp_path: Path) -> None:
        """Test loading config from JSON file."""
        config_file = tmp_path / "config.json"
        config_data = {
            "rest_api": {"enabled": False, "port": 8080},
            "socket": {"port": 9090},
            "logging": {"level": "DEBUG"},
        }
        config_file.write_text(json.dumps(config_data))

        os.chdir(tmp_path)
        config = load_config("config.json")

        assert config.rest_api.enabled is False
        assert config.rest_api.port == 8080
        assert config.socket.port == 9090
        assert config.logging.level == "DEBUG"

    def test_load_config_invalid_json(self, tmp_path: Path) -> None:
        """Test loading config with invalid JSON raises error."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{ invalid json }")

        os.chdir(tmp_path)
        with pytest.raises(ConfigurationError, match="Failed to parse"):
            load_config("config.json")

    def test_load_config_not_json_object(self, tmp_path: Path) -> None:
        """Test loading config that's not a JSON object raises error."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(["not", "an", "object"]))

        os.chdir(tmp_path)
        with pytest.raises(ConfigurationError, match="must contain a JSON object"):
            load_config("config.json")

    def test_load_config_with_env_overrides(self, tmp_path: Path) -> None:
        """Test loading config with environment variable overrides."""
        config_file = tmp_path / "config.json"
        config_data = {"rest_api": {"port": 5100}}
        config_file.write_text(json.dumps(config_data))

        os.chdir(tmp_path)
        with patch.dict(
            os.environ,
            {
                "YK_DAEMON_REST_API_PORT": "8080",
                "YK_DAEMON_SOCKET_ENABLED": "false",
                "YK_DAEMON_LOGGING_LEVEL": "DEBUG",
            },
        ):
            config = load_config("config.json")

        assert config.rest_api.port == 8080
        assert config.socket.enabled is False
        assert config.logging.level == "DEBUG"

    def test_load_config_env_overrides_only(self, tmp_path: Path) -> None:
        """Test loading config with only environment variables."""
        os.chdir(tmp_path)
        with patch.dict(
            os.environ,
            {
                "YK_DAEMON_REST_API_PORT": "9000",
                "YK_DAEMON_REST_API_ENABLED": "true",
                "YK_DAEMON_SOCKET_PORT": "9001",
                "YK_DAEMON_NOTIFICATIONS_POPUP": "false",
            },
        ):
            config = load_config("nonexistent.json")

        assert config.rest_api.port == 9000
        assert config.rest_api.enabled is True
        assert config.socket.port == 9001
        assert config.notifications.popup is False

    def test_load_config_env_boolean_conversion(self, tmp_path: Path) -> None:
        """Test environment variable boolean value conversion."""
        os.chdir(tmp_path)
        test_cases = [
            ("true", True),
            ("TRUE", True),
            ("1", True),
            ("yes", True),
            ("on", True),
            ("false", False),
            ("FALSE", False),
            ("0", False),
            ("no", False),
            ("off", False),
        ]

        for env_value, expected in test_cases:
            with patch.dict(os.environ, {"YK_DAEMON_REST_API_ENABLED": env_value}):
                config = load_config("nonexistent.json")
                assert config.rest_api.enabled == expected

    def test_load_config_env_integer_conversion(self, tmp_path: Path) -> None:
        """Test environment variable integer value conversion."""
        os.chdir(tmp_path)
        with patch.dict(os.environ, {"YK_DAEMON_REST_API_PORT": "12345"}):
            config = load_config("nonexistent.json")
            assert config.rest_api.port == 12345
            assert isinstance(config.rest_api.port, int)

    def test_load_config_validates_result(self, tmp_path: Path) -> None:
        """Test that load_config validates the final configuration."""
        config_file = tmp_path / "config.json"
        config_data = {
            "rest_api": {"enabled": False},
            "socket": {"enabled": False},
        }
        config_file.write_text(json.dumps(config_data))

        os.chdir(tmp_path)
        with pytest.raises(
            ConfigurationError, match="At least one of rest_api or socket must be enabled"
        ):
            load_config("config.json")

    def test_load_config_partial_override(self, tmp_path: Path) -> None:
        """Test that partial config in file/env doesn't lose defaults."""
        config_file = tmp_path / "config.json"
        config_data = {"rest_api": {"port": 8080}}
        config_file.write_text(json.dumps(config_data))

        os.chdir(tmp_path)
        config = load_config("config.json")

        # Custom value from file
        assert config.rest_api.port == 8080
        # Defaults preserved
        assert config.rest_api.enabled is True
        assert config.rest_api.host == "127.0.0.1"
        assert config.socket.port == 5101

    def test_load_config_env_priority_over_file(self, tmp_path: Path) -> None:
        """Test that environment variables have priority over file."""
        config_file = tmp_path / "config.json"
        config_data = {"rest_api": {"port": 5100}}
        config_file.write_text(json.dumps(config_data))

        os.chdir(tmp_path)
        with patch.dict(os.environ, {"YK_DAEMON_REST_API_PORT": "9999"}):
            config = load_config("config.json")

        assert config.rest_api.port == 9999

    def test_load_config_ignores_invalid_env_vars(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that invalid environment variables are ignored."""
        os.chdir(tmp_path)
        with patch.dict(
            os.environ,
            {
                "YK_DAEMON_INVALID_SECTION_KEY": "value",
                "YK_DAEMON": "incomplete",
                "OTHER_ENV_VAR": "ignored",
            },
        ):
            config = load_config("nonexistent.json")

        # Should still load with defaults
        assert config.rest_api.port == 5100
        # Should log warnings
        assert "Ignoring" in caplog.text or "Unknown" in caplog.text
