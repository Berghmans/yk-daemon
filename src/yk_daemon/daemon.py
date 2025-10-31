#!/usr/bin/env python3
"""YubiKey Daemon - Main entry point.

This daemon orchestrates all components to bridge YubiKey OATH-TOTP functionality
to WSL and other local applications through REST API and TCP socket interfaces.
"""

import argparse
import logging
import signal
import sys
import threading
from pathlib import Path
from typing import NoReturn

from yk_daemon.config import Config, ConfigurationError, get_default_config_path, load_config
from yk_daemon.notifications import Notifier, create_notifier_from_config
from yk_daemon.rest_api import run_server as run_rest_server
from yk_daemon.socket_server import SocketServer
from yk_daemon.yubikey import YubiKeyInterface

# Global shutdown event for graceful termination
shutdown_event = threading.Event()

# Global references to servers for cleanup
rest_server_thread: threading.Thread | None = None
socket_server: SocketServer | None = None
notifier: Notifier | None = None

logger = logging.getLogger(__name__)


def setup_logging(config: Config, debug: bool = False) -> None:
    """Setup logging configuration.

    Args:
        config: Configuration object with logging settings
        debug: If True, override config and use DEBUG level with console output
    """
    # Determine log level
    log_level = logging.DEBUG if debug else getattr(logging, config.logging.level)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Format for log messages
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    formatter = logging.Formatter(log_format)

    # Console handler (always in debug mode, optional otherwise)
    if debug:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        logger.info("Debug mode enabled - logging to console")

    # File handler (always, unless in debug mode and user prefers console only)
    if not debug or True:  # Always log to file
        try:
            log_file = Path(config.logging.file)
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
            logger.info(f"Logging to file: {log_file.absolute()}")
        except Exception as e:
            logger.error(f"Failed to setup file logging: {e}")
            # Fall back to console only
            if not debug:
                console_handler = logging.StreamHandler(sys.stdout)
                console_handler.setLevel(log_level)
                console_handler.setFormatter(formatter)
                root_logger.addHandler(console_handler)


def signal_handler(signum: int, frame: object) -> None:  # noqa: ARG001
    """Handle shutdown signals (SIGINT, SIGTERM).

    Args:
        signum: Signal number
        frame: Current stack frame (unused)
    """
    signal_name = signal.Signals(signum).name
    logger.info(f"Received signal {signal_name}, initiating graceful shutdown...")
    shutdown_event.set()


def start_rest_api(config: Config, yubikey: YubiKeyInterface) -> threading.Thread:
    """Start REST API server in a separate thread.

    Args:
        config: Configuration object
        yubikey: YubiKey interface instance

    Returns:
        Thread running the REST API server
    """
    logger.info("Starting REST API server...")

    def run_rest() -> None:
        try:
            run_rest_server(config.rest_api, yubikey=yubikey, full_config=config)
        except Exception as e:
            logger.error(f"REST API server error: {e}", exc_info=True)
            shutdown_event.set()

    thread = threading.Thread(target=run_rest, name="RestApiServer", daemon=True)
    thread.start()
    logger.info(f"REST API server thread started on {config.rest_api.host}:{config.rest_api.port}")
    return thread


def start_socket_server(config: Config, yubikey: YubiKeyInterface) -> SocketServer:
    """Start TCP socket server.

    Args:
        config: Configuration object
        yubikey: YubiKey interface instance

    Returns:
        SocketServer instance
    """
    logger.info("Starting socket server...")
    server = SocketServer(
        host=config.socket.host, port=config.socket.port, yubikey_interface=yubikey
    )
    server.start()
    logger.info(f"Socket server started on {config.socket.host}:{config.socket.port}")
    return server


def shutdown_servers() -> None:
    """Shutdown all servers gracefully."""
    global rest_server_thread, socket_server, notifier

    logger.info("Shutting down servers...")

    # Stop socket server
    if socket_server and socket_server.is_running():
        try:
            logger.info("Stopping socket server...")
            socket_server.stop()
            logger.info("Socket server stopped")
        except Exception as e:
            logger.error(f"Error stopping socket server: {e}")

    # REST API server will stop when thread joins (it's checking shutdown_event)
    # Note: Flask doesn't have a clean shutdown mechanism when running in thread
    # The daemon thread will be terminated when main thread exits
    if rest_server_thread and rest_server_thread.is_alive():
        logger.info("Waiting for REST API server thread to finish...")
        # Give it a moment to finish current requests
        rest_server_thread.join(timeout=2.0)
        if rest_server_thread.is_alive():
            logger.warning("REST API server thread did not finish in time")

    # Cleanup notifier
    if notifier:
        try:
            logger.info("Cleaning up notifier...")
            notifier.cleanup()
            logger.info("Notifier cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up notifier: {e}")

    logger.info("All servers shut down")


def run_daemon(config: Config, debug: bool = False) -> NoReturn:
    """Run the daemon with all components.

    Args:
        config: Configuration object
        debug: Debug mode flag

    Raises:
        SystemExit: Always exits with appropriate code
    """
    global rest_server_thread, socket_server, notifier

    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("=" * 60)
    logger.info("YubiKey Daemon starting...")
    logger.info(f"Debug mode: {debug}")
    logger.info(
        f"REST API enabled: {config.rest_api.enabled} ({config.rest_api.host}:{config.rest_api.port})"
    )
    logger.info(
        f"Socket server enabled: {config.socket.enabled} ({config.socket.host}:{config.socket.port})"
    )
    logger.info(
        f"Notifications - Popup: {config.notifications.popup}, Sound: {config.notifications.sound}"
    )
    logger.info("=" * 60)

    try:
        # Initialize notifier
        logger.info("Initializing notifier...")
        notifier = create_notifier_from_config(config.notifications)

        # Initialize YubiKey interface with notifier
        logger.info("Initializing YubiKey interface...")
        yubikey = YubiKeyInterface(notifier=notifier)

        # Check for YubiKey presence
        status = yubikey.get_status()
        logger.info(f"YubiKey status: {status.value}")
        if status.value == "not_connected":
            logger.warning(
                "No YubiKey detected at startup. "
                "The daemon will continue running, but operations will fail until a YubiKey is connected."
            )

        # Start REST API server (if enabled)
        if config.rest_api.enabled:
            rest_server_thread = start_rest_api(config, yubikey)
        else:
            logger.info("REST API server disabled in configuration")

        # Start socket server (if enabled)
        if config.socket.enabled:
            socket_server = start_socket_server(config, yubikey)
        else:
            logger.info("Socket server disabled in configuration")

        # Main loop - wait for shutdown signal
        logger.info("YubiKey Daemon is running. Press Ctrl+C to stop.")
        while not shutdown_event.is_set():
            shutdown_event.wait(timeout=1.0)

        # Shutdown initiated
        logger.info("Shutdown signal received")

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Fatal error in daemon: {e}", exc_info=True)
        sys.exit(1)
    finally:
        shutdown_servers()
        logger.info("YubiKey Daemon stopped")
        sys.exit(0)


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="YubiKey Daemon - Bridge YubiKey OATH-TOTP to WSL and local applications",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Run with default config
  %(prog)s --debug                  # Run in foreground with debug logging
  %(prog)s --config custom.json     # Use custom config file

Windows Service Management:
  %(prog)s --install                # Install as Windows service
  %(prog)s --start                  # Start the Windows service
  %(prog)s --stop                   # Stop the Windows service
  %(prog)s --remove                 # Remove/uninstall the Windows service
        """,
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Run in foreground with debug logging to console",
    )

    parser.add_argument(
        "--config",
        type=str,
        default=None,
        metavar="PATH",
        help="Path to configuration file (default: auto-detect from standard locations)",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )

    # Windows service management arguments
    parser.add_argument(
        "--install",
        action="store_true",
        help="Install as Windows service",
    )

    parser.add_argument(
        "--start",
        action="store_true",
        help="Start the Windows service",
    )

    parser.add_argument(
        "--stop",
        action="store_true",
        help="Stop the Windows service",
    )

    parser.add_argument(
        "--remove",
        action="store_true",
        help="Remove/uninstall the Windows service",
    )

    return parser.parse_args()


def main() -> NoReturn:
    """Main entry point."""
    # Parse arguments first (before logging setup)
    args = parse_arguments()

    # Handle Windows service commands
    if any([args.install, args.start, args.stop, args.remove]):
        # Import service module and delegate to ServiceManager
        try:
            from yk_daemon.service import ServiceManager

            manager = ServiceManager()
            success = True

            if args.install:
                success = manager.install(args.config)
            elif args.start:
                success = manager.start()
            elif args.stop:
                success = manager.stop()
            elif args.remove:
                success = manager.remove()

            sys.exit(0 if success else 1)

        except (ImportError, RuntimeError) as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)

    # Determine config file path
    config_path = args.config if args.config else get_default_config_path()

    # Load configuration
    try:
        config = load_config(config_path)
    except ConfigurationError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Failed to load configuration: {e}", file=sys.stderr)
        sys.exit(1)

    # Setup logging
    setup_logging(config, debug=args.debug)

    # Log startup with absolute path
    abs_config_path = Path(config_path).absolute()
    logger.info(f"Starting YubiKey Daemon (config: {abs_config_path})")

    # Run daemon
    run_daemon(config, debug=args.debug)


if __name__ == "__main__":
    main()
