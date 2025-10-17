"""Integration tests for YubiKey Daemon main entry point."""

import logging
import signal
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src import daemon as yk_daemon  # noqa: E402
from src.config import (  # noqa: E402
    Config,
    LoggingConfig,
    NotificationsConfig,
    RestApiConfig,
    SocketConfig,
)


class TestLoggingSetup:
    """Test logging configuration."""

    def test_setup_logging_debug_mode(self, tmp_path: Path) -> None:
        """Test logging setup in debug mode."""
        config = Config(logging=LoggingConfig(level="INFO", file=str(tmp_path / "test.log")))

        yk_daemon.setup_logging(config, debug=True)

        # Check root logger level
        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

        # Check that console handler was added
        console_handlers = [h for h in root_logger.handlers if isinstance(h, logging.StreamHandler)]
        assert len(console_handlers) > 0

    def test_setup_logging_production_mode(self, tmp_path: Path) -> None:
        """Test logging setup in production mode."""
        log_file = tmp_path / "daemon.log"
        config = Config(logging=LoggingConfig(level="INFO", file=str(log_file)))

        yk_daemon.setup_logging(config, debug=False)

        # Check root logger level
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO

        # Log file should be created
        test_logger = logging.getLogger("test")
        test_logger.info("Test message")
        assert log_file.exists()


class TestSignalHandler:
    """Test signal handling."""

    def test_signal_handler_sets_shutdown_event(self) -> None:
        """Test that signal handler sets shutdown event."""
        # Reset shutdown event
        yk_daemon.shutdown_event.clear()

        # Call signal handler
        yk_daemon.signal_handler(signal.SIGINT, None)

        # Check that shutdown event is set
        assert yk_daemon.shutdown_event.is_set()

        # Reset for other tests
        yk_daemon.shutdown_event.clear()


class TestServerManagement:
    """Test server start/stop functionality."""

    def test_start_rest_api(self) -> None:
        """Test starting REST API server."""
        with patch.object(yk_daemon, "run_rest_server") as mock_run_rest:
            # Make mock block until shutdown event is set
            def mock_server(*args: object, **kwargs: object) -> None:
                yk_daemon.shutdown_event.wait()

            mock_run_rest.side_effect = mock_server

            config = Config(rest_api=RestApiConfig(host="127.0.0.1", port=5000))
            yubikey = MagicMock()

            # Reset shutdown event
            yk_daemon.shutdown_event.clear()

            # Start server
            thread = yk_daemon.start_rest_api(config, yubikey)

            # Give thread a moment to start
            time.sleep(0.05)

            # Check thread is running
            assert thread.is_alive()
            assert thread.name == "RestApiServer"

            # Cleanup
            yk_daemon.shutdown_event.set()
            thread.join(timeout=1.0)

    def test_start_socket_server(self) -> None:
        """Test starting socket server."""
        with patch.object(yk_daemon, "SocketServer") as mock_socket_class:
            mock_server = MagicMock()
            mock_socket_class.return_value = mock_server

            config = Config(socket=SocketConfig(host="127.0.0.1", port=5001))
            yubikey = MagicMock()

            # Start server
            _server = yk_daemon.start_socket_server(config, yubikey)

            # Check server was created and started
            mock_socket_class.assert_called_once_with(
                host="127.0.0.1", port=5001, yubikey_interface=yubikey
            )
            mock_server.start.assert_called_once()

    def test_shutdown_servers(self) -> None:
        """Test graceful shutdown of servers."""
        # Setup mocks
        mock_socket_instance = MagicMock()
        mock_socket_instance.is_running.return_value = True
        yk_daemon.socket_server = mock_socket_instance

        mock_notifier_instance = MagicMock()
        yk_daemon.notifier = mock_notifier_instance

        # Call shutdown
        yk_daemon.shutdown_servers()

        # Verify shutdown calls
        mock_socket_instance.stop.assert_called_once()
        mock_notifier_instance.cleanup.assert_called_once()

        # Cleanup
        yk_daemon.socket_server = None
        yk_daemon.notifier = None


class TestArgumentParsing:
    """Test command-line argument parsing."""

    def test_parse_arguments_defaults(self) -> None:
        """Test default argument values."""
        with patch("sys.argv", ["yk-daemon.py"]):
            args = yk_daemon.parse_arguments()
            assert args.debug is False
            assert args.config == "config.json"

    def test_parse_arguments_debug_flag(self) -> None:
        """Test --debug flag."""
        with patch("sys.argv", ["yk-daemon.py", "--debug"]):
            args = yk_daemon.parse_arguments()
            assert args.debug is True

    def test_parse_arguments_custom_config(self) -> None:
        """Test --config argument."""
        with patch("sys.argv", ["yk-daemon.py", "--config", "custom.json"]):
            args = yk_daemon.parse_arguments()
            assert args.config == "custom.json"

    def test_parse_arguments_combined(self) -> None:
        """Test multiple arguments together."""
        with patch("sys.argv", ["yk-daemon.py", "--debug", "--config", "/path/to/config.json"]):
            args = yk_daemon.parse_arguments()
            assert args.debug is True
            assert args.config == "/path/to/config.json"


class TestMainFunction:
    """Test main entry point."""

    def test_main_with_debug(self) -> None:
        """Test main function in debug mode."""
        with (
            patch.object(yk_daemon, "run_daemon") as mock_run_daemon,
            patch.object(yk_daemon, "setup_logging") as mock_setup_logging,
            patch.object(yk_daemon, "load_config") as mock_load_config,
            patch("sys.argv", ["yk-daemon.py", "--debug"]),
        ):
            # Setup mocks
            mock_config = Config()
            mock_load_config.return_value = mock_config

            # Prevent actual daemon run
            mock_run_daemon.side_effect = SystemExit(0)

            # Call main and expect SystemExit
            with pytest.raises(SystemExit) as exc_info:
                yk_daemon.main()

            assert exc_info.value.code == 0

            # Verify calls
            mock_load_config.assert_called_once_with("config.json")
            mock_setup_logging.assert_called_once_with(mock_config, debug=True)
            mock_run_daemon.assert_called_once_with(mock_config, debug=True)

    def test_main_config_error(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test main function with configuration error."""
        from src.config import ConfigurationError

        with (
            patch.object(yk_daemon, "load_config") as mock_load_config,
            patch("sys.argv", ["yk-daemon.py"]),
        ):
            mock_load_config.side_effect = ConfigurationError("Invalid config")

            # Call main and expect SystemExit
            with pytest.raises(SystemExit) as exc_info:
                yk_daemon.main()

            assert exc_info.value.code == 1

            # Check error message
            captured = capsys.readouterr()
            assert "Configuration error" in captured.err


class TestDaemonRun:
    """Test daemon run functionality."""

    def test_run_daemon_with_both_servers(self) -> None:
        """Test running daemon with both servers enabled."""
        with (
            patch.object(yk_daemon, "YubiKeyInterface") as mock_yubikey_class,
            patch.object(yk_daemon, "create_notifier_from_config") as mock_create_notifier,
            patch.object(yk_daemon, "start_rest_api") as mock_start_rest,
            patch.object(yk_daemon, "start_socket_server") as mock_start_socket,
            patch.object(yk_daemon, "shutdown_servers") as mock_shutdown,
        ):
            # Setup mocks
            mock_notifier = MagicMock()
            mock_create_notifier.return_value = mock_notifier

            mock_yubikey = MagicMock()
            mock_yubikey.get_status.return_value = MagicMock(value="connected")
            mock_yubikey_class.return_value = mock_yubikey

            mock_rest_thread = MagicMock()
            mock_start_rest.return_value = mock_rest_thread

            mock_socket_server = MagicMock()
            mock_start_socket.return_value = mock_socket_server

            config = Config(
                rest_api=RestApiConfig(enabled=True),
                socket=SocketConfig(enabled=True),
                notifications=NotificationsConfig(popup=True, sound=True),
            )

            # Reset and set shutdown event after short delay
            yk_daemon.shutdown_event.clear()

            def trigger_shutdown() -> None:
                time.sleep(0.1)
                yk_daemon.shutdown_event.set()

            shutdown_thread = threading.Thread(target=trigger_shutdown)
            shutdown_thread.start()

            # Run daemon (will exit when shutdown event is set)
            with pytest.raises(SystemExit) as exc_info:
                yk_daemon.run_daemon(config, debug=True)

            assert exc_info.value.code == 0

            # Verify initialization
            mock_create_notifier.assert_called_once()
            mock_yubikey_class.assert_called_once_with(notifier=mock_notifier)

            # Verify servers were started
            mock_start_rest.assert_called_once()
            mock_start_socket.assert_called_once()

            # Verify shutdown was called
            mock_shutdown.assert_called_once()

            shutdown_thread.join()

    def test_run_daemon_rest_only(self) -> None:
        """Test running daemon with only REST API enabled."""
        with (
            patch.object(yk_daemon, "YubiKeyInterface") as mock_yubikey_class,
            patch.object(yk_daemon, "create_notifier_from_config") as mock_create_notifier,
            patch.object(yk_daemon, "start_rest_api") as mock_start_rest,
            patch.object(yk_daemon, "shutdown_servers") as mock_shutdown,
        ):
            # Setup mocks
            mock_notifier = MagicMock()
            mock_create_notifier.return_value = mock_notifier

            mock_yubikey = MagicMock()
            mock_yubikey.get_status.return_value = MagicMock(value="connected")
            mock_yubikey_class.return_value = mock_yubikey

            mock_rest_thread = MagicMock()
            mock_start_rest.return_value = mock_rest_thread

            config = Config(
                rest_api=RestApiConfig(enabled=True),
                socket=SocketConfig(enabled=False),
            )

            # Reset and set shutdown event after short delay
            yk_daemon.shutdown_event.clear()

            def trigger_shutdown() -> None:
                time.sleep(0.1)
                yk_daemon.shutdown_event.set()

            shutdown_thread = threading.Thread(target=trigger_shutdown)
            shutdown_thread.start()

            # Run daemon
            with pytest.raises(SystemExit) as exc_info:
                yk_daemon.run_daemon(config, debug=True)

            assert exc_info.value.code == 0

            # Verify REST API was started
            mock_start_rest.assert_called_once()

            # Verify shutdown was called
            mock_shutdown.assert_called_once()

            shutdown_thread.join()

    def test_run_daemon_yubikey_not_connected(self) -> None:
        """Test daemon startup when YubiKey is not connected."""
        with (
            patch.object(yk_daemon, "YubiKeyInterface") as mock_yubikey_class,
            patch.object(yk_daemon, "create_notifier_from_config") as mock_create_notifier,
        ):
            # Setup mocks
            mock_notifier = MagicMock()
            mock_create_notifier.return_value = mock_notifier

            mock_yubikey = MagicMock()
            mock_yubikey.get_status.return_value = MagicMock(value="not_connected")
            mock_yubikey_class.return_value = mock_yubikey

            config = Config(
                rest_api=RestApiConfig(enabled=False), socket=SocketConfig(enabled=False)
            )

            # Reset and set shutdown event immediately
            yk_daemon.shutdown_event.clear()
            yk_daemon.shutdown_event.set()

            # Run daemon (should start but warn about no YubiKey)
            with pytest.raises(SystemExit):
                yk_daemon.run_daemon(config, debug=True)

            # Verify YubiKey status was checked
            mock_yubikey.get_status.assert_called_once()
