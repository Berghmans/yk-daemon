"""Configuration management for YubiKey Daemon.

This module handles loading and validating configuration from:
1. Default values (hardcoded)
2. config.json file (if exists)
3. Environment variable overrides

Environment variables follow the pattern: YK_DAEMON_<SECTION>_<KEY>
Examples:
- YK_DAEMON_REST_API_PORT=5100
- YK_DAEMON_SOCKET_PORT=5101
- YK_DAEMON_LOGGING_LEVEL=DEBUG
"""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _get_default_log_path() -> str:
    """Get the default log file path.

    Uses ProgramData on Windows for service compatibility,
    or current directory otherwise.

    Returns:
        Default log file path
    """
    if os.name == "nt":  # Windows
        program_data = os.environ.get("PROGRAMDATA", "C:\\ProgramData")
        log_dir = os.path.join(program_data, "yk-daemon")
        os.makedirs(log_dir, exist_ok=True)
        return os.path.join(log_dir, "yk-daemon.log")
    else:
        # Non-Windows: use current directory
        return "yk-daemon.log"


def _get_default_sound_file_path() -> str:
    """Get the default notification sound file path.

    Uses ProgramData on Windows for service compatibility,
    or current directory otherwise.

    Returns:
        Default notification sound file path
    """
    if os.name == "nt":  # Windows
        program_data = os.environ.get("PROGRAMDATA", "C:\\ProgramData")
        sound_dir = os.path.join(program_data, "yk-daemon")
        return os.path.join(sound_dir, "notification.wav")
    else:
        # Non-Windows: use current directory
        return "notification.wav"


class ConfigurationError(Exception):
    """Raised when configuration is invalid."""

    pass


@dataclass
class RestApiConfig:
    """REST API configuration."""

    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 5100

    def validate(self) -> None:
        """Validate REST API configuration."""
        if not isinstance(self.enabled, bool):
            raise ConfigurationError("rest_api.enabled must be a boolean")
        if not isinstance(self.host, str):
            raise ConfigurationError("rest_api.host must be a string")
        if not isinstance(self.port, int):
            raise ConfigurationError("rest_api.port must be an integer")
        if not (1 <= self.port <= 65535):
            raise ConfigurationError("rest_api.port must be between 1 and 65535")
        if self.host not in ("127.0.0.1", "localhost"):
            logger.warning(
                f"rest_api.host is set to '{self.host}'. "
                "For security, it's recommended to use '127.0.0.1' (localhost only)."
            )


@dataclass
class SocketConfig:
    """Socket server configuration."""

    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 5101

    def validate(self) -> None:
        """Validate socket configuration."""
        if not isinstance(self.enabled, bool):
            raise ConfigurationError("socket.enabled must be a boolean")
        if not isinstance(self.host, str):
            raise ConfigurationError("socket.host must be a string")
        if not isinstance(self.port, int):
            raise ConfigurationError("socket.port must be an integer")
        if not (1 <= self.port <= 65535):
            raise ConfigurationError("socket.port must be between 1 and 65535")
        if self.host not in ("127.0.0.1", "localhost"):
            logger.warning(
                f"socket.host is set to '{self.host}'. "
                "For security, it's recommended to use '127.0.0.1' (localhost only)."
            )


@dataclass
class NotificationsConfig:
    """Notifications configuration."""

    popup: bool = True
    sound: bool = True
    sound_file: str = field(default_factory=lambda: _get_default_sound_file_path())

    def validate(self) -> None:
        """Validate notifications configuration."""
        if not isinstance(self.popup, bool):
            raise ConfigurationError("notifications.popup must be a boolean")
        if not isinstance(self.sound, bool):
            raise ConfigurationError("notifications.sound must be a boolean")
        if not isinstance(self.sound_file, str):
            raise ConfigurationError("notifications.sound_file must be a string")
        # Note: Sound file existence is validated by Notifier class during initialization
        # which has more sophisticated path resolution logic


@dataclass
class LoggingConfig:
    """Logging configuration."""

    level: str = "INFO"
    file: str = field(default_factory=lambda: _get_default_log_path())

    def validate(self) -> None:
        """Validate logging configuration."""
        if not isinstance(self.level, str):
            raise ConfigurationError("logging.level must be a string")
        if not isinstance(self.file, str):
            raise ConfigurationError("logging.file must be a string")

        valid_levels = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        level_upper = self.level.upper()
        if level_upper not in valid_levels:
            raise ConfigurationError(f"logging.level must be one of: {', '.join(valid_levels)}")
        # Normalize to uppercase
        self.level = level_upper


@dataclass
class Config:
    """Main configuration for YubiKey Daemon."""

    rest_api: RestApiConfig = field(default_factory=RestApiConfig)
    socket: SocketConfig = field(default_factory=SocketConfig)
    notifications: NotificationsConfig = field(default_factory=NotificationsConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    def validate(self) -> None:
        """Validate entire configuration."""
        self.rest_api.validate()
        self.socket.validate()
        self.notifications.validate()
        self.logging.validate()

        # Cross-section validation
        if self.rest_api.enabled and self.socket.enabled:
            if self.rest_api.port == self.socket.port and self.rest_api.host == self.socket.host:
                raise ConfigurationError(
                    "rest_api and socket cannot use the same host:port combination"
                )

        if not self.rest_api.enabled and not self.socket.enabled:
            raise ConfigurationError("At least one of rest_api or socket must be enabled")

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary suitable for JSON serialization.

        Returns:
            Dictionary representation of the configuration
        """
        return {
            "rest_api": {
                "enabled": self.rest_api.enabled,
                "host": self.rest_api.host,
                "port": self.rest_api.port,
            },
            "socket": {
                "enabled": self.socket.enabled,
                "host": self.socket.host,
                "port": self.socket.port,
            },
            "notifications": {
                "popup": self.notifications.popup,
                "sound": self.notifications.sound,
                "sound_file": self.notifications.sound_file,
            },
            "logging": {
                "level": self.logging.level,
                "file": self.logging.file,
            },
        }

    def save_to_file(self, file_path: str) -> None:
        """Save configuration to JSON file.

        Args:
            file_path: Path to save configuration file

        Raises:
            OSError: If file cannot be written
        """
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
            f.write("\n")  # Add trailing newline


def load_config(config_file: str = "config.json") -> Config:
    """Load configuration from file and environment variables.

    Priority order (highest to lowest):
    1. Environment variables (YK_DAEMON_*)
    2. config.json file
    3. Default values

    Args:
        config_file: Path to configuration file (default: config.json)

    Returns:
        Validated Config object

    Raises:
        ConfigurationError: If configuration is invalid
    """
    config_dict: dict[str, Any] = {}

    # Step 1: Load from config.json if it exists
    config_path = Path(config_file)
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                file_config = json.load(f)
                if not isinstance(file_config, dict):
                    raise ConfigurationError(
                        f"Configuration file '{config_file}' must contain a JSON object"
                    )
                config_dict = file_config
                logger.info(f"Loaded configuration from {config_file}")
        except json.JSONDecodeError as e:
            raise ConfigurationError(
                f"Failed to parse configuration file '{config_file}': {e}"
            ) from e
        except OSError as e:
            raise ConfigurationError(
                f"Failed to read configuration file '{config_file}': {e}"
            ) from e
    else:
        logger.info(f"Configuration file '{config_file}' not found, using defaults")

    # Step 2: Apply environment variable overrides
    env_overrides = _load_env_overrides()
    config_dict = _merge_configs(config_dict, env_overrides)

    # Step 3: Build Config object from merged dictionary
    config = _build_config_from_dict(config_dict)

    # Step 4: Validate configuration
    config.validate()

    return config


def _load_env_overrides() -> dict[str, Any]:
    """Load configuration overrides from environment variables.

    Environment variables follow the pattern: YK_DAEMON_<SECTION>_<KEY>
    Examples:
        YK_DAEMON_REST_API_ENABLED=false
        YK_DAEMON_REST_API_PORT=5100
        YK_DAEMON_SOCKET_PORT=5101
        YK_DAEMON_LOGGING_LEVEL=DEBUG

    Returns:
        Dictionary with environment variable overrides
    """
    overrides: dict[str, Any] = {}
    prefix = "YK_DAEMON_"

    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue

        # Remove prefix and split into parts
        config_key = key[len(prefix) :]
        parts = config_key.lower().split("_")

        if len(parts) < 2:
            logger.warning(f"Ignoring invalid environment variable: {key}")
            continue

        # Handle multi-word section names (e.g., REST_API -> rest_api)
        # Try to match known sections
        section = None
        key_parts = []

        if parts[0] == "rest" and len(parts) > 1 and parts[1] == "api":
            section = "rest_api"
            key_parts = parts[2:]
        elif parts[0] == "socket":
            section = "socket"
            key_parts = parts[1:]
        elif parts[0] == "notifications":
            section = "notifications"
            key_parts = parts[1:]
        elif parts[0] == "logging":
            section = "logging"
            key_parts = parts[1:]
        else:
            logger.warning(f"Unknown configuration section in environment variable: {key}")
            continue

        if not key_parts:
            logger.warning(f"Missing key name in environment variable: {key}")
            continue

        # Build the nested dictionary
        if section not in overrides:
            overrides[section] = {}

        key_name = "_".join(key_parts)

        # Type conversion for known keys
        typed_value: Any = value
        if key_name in ("enabled", "popup", "sound"):
            # Boolean conversion
            typed_value = value.lower() in ("true", "1", "yes", "on")
        elif key_name in ("port",):
            # Integer conversion
            try:
                typed_value = int(value)
            except ValueError:
                logger.warning(f"Invalid integer value for {key}: '{value}', using as string")

        overrides[section][key_name] = typed_value
        logger.debug(f"Environment override: {section}.{key_name} = {typed_value}")

    return overrides


def _merge_configs(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Merge two configuration dictionaries.

    Args:
        base: Base configuration dictionary
        overrides: Override configuration dictionary

    Returns:
        Merged configuration dictionary
    """
    result = base.copy()

    for key, value in overrides.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recursive merge for nested dictionaries
            result[key] = _merge_configs(result[key], value)
        else:
            result[key] = value

    return result


def _build_config_from_dict(config_dict: dict[str, Any]) -> Config:
    """Build Config object from dictionary.

    Args:
        config_dict: Configuration dictionary

    Returns:
        Config object
    """
    # Build sub-configurations
    rest_api_dict = config_dict.get("rest_api", {})
    rest_api = RestApiConfig(
        enabled=rest_api_dict.get("enabled", RestApiConfig.enabled),
        host=rest_api_dict.get("host", RestApiConfig.host),
        port=rest_api_dict.get("port", RestApiConfig.port),
    )

    socket_dict = config_dict.get("socket", {})
    socket = SocketConfig(
        enabled=socket_dict.get("enabled", SocketConfig.enabled),
        host=socket_dict.get("host", SocketConfig.host),
        port=socket_dict.get("port", SocketConfig.port),
    )

    notifications_dict = config_dict.get("notifications", {})
    notifications = NotificationsConfig(
        popup=notifications_dict.get("popup", NotificationsConfig.popup),
        sound=notifications_dict.get("sound", NotificationsConfig.sound),
        sound_file=notifications_dict.get("sound_file", _get_default_sound_file_path()),
    )

    logging_dict = config_dict.get("logging", {})
    logging_config = LoggingConfig(
        level=logging_dict.get("level", LoggingConfig.level),
        file=logging_dict.get("file", _get_default_log_path()),
    )

    return Config(
        rest_api=rest_api,
        socket=socket,
        notifications=notifications,
        logging=logging_config,
    )
