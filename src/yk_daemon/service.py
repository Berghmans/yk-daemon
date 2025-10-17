#!/usr/bin/env python3
"""Windows Service wrapper for YubiKey Daemon.

This module provides Windows service functionality allowing the daemon
to run as a background Windows service that can be managed via Services.msc
and automatically start on system boot.
"""

import logging
import sys
import time
from pathlib import Path
from typing import NoReturn

from yk_daemon.config import Config, ConfigurationError, load_config
from yk_daemon.daemon import setup_logging

# Only import Windows-specific modules on Windows
if sys.platform == "win32":
    try:
        import servicemanager
        import win32event
        import win32service
        import win32serviceutil

        WINDOWS_SERVICE_AVAILABLE = True
    except ImportError:
        WINDOWS_SERVICE_AVAILABLE = False
        # Create placeholder classes for type hints
        win32serviceutil = None
        win32service = None
        win32event = None
        servicemanager = None
else:
    WINDOWS_SERVICE_AVAILABLE = False
    # Create placeholder classes for type hints
    win32serviceutil = None
    win32service = None
    win32event = None
    servicemanager = None

logger = logging.getLogger(__name__)


if WINDOWS_SERVICE_AVAILABLE:

    class YubiKeyDaemonService(win32serviceutil.ServiceFramework):  # type: ignore
        """Windows Service class for YubiKey Daemon."""

        # Service configuration
        _svc_name_ = "YubiKeyDaemon"
        _svc_display_name_ = "YubiKey Daemon"
        _svc_description_ = (
            "Bridges YubiKey OATH-TOTP functionality to WSL and other local applications "
            "through REST API and TCP socket interfaces."
        )

        def __init__(self, args: list) -> None:
            """Initialize the service.

            Args:
                args: Service arguments
            """
            if not WINDOWS_SERVICE_AVAILABLE:
                raise RuntimeError("Windows service functionality is not available")

            win32serviceutil.ServiceFramework.__init__(self, args)  # type: ignore
            self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)  # type: ignore
            self.is_alive = True
            self.config_path = self._get_config_path()

        def _get_config_path(self) -> str:
            """Get the configuration file path.

            Returns:
                Path to the configuration file
            """
            # Try to get config path from service registry or use default
            # For now, use a default path relative to service executable
            try:
                # Get the directory where the service is installed
                service_dir = Path(sys.executable).parent
                config_path = service_dir / "config.json"
                if config_path.exists():
                    return str(config_path)
            except Exception:
                pass

            # Fallback to default
            return "config.json"

        def SvcStop(self) -> None:
            """Handle service stop request."""
            try:
                self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)  # type: ignore
                logger.info("Service stop requested")
                win32event.SetEvent(self.hWaitStop)  # type: ignore
                self.is_alive = False
            except Exception as e:
                logger.error(f"Error during service stop: {e}")

        def SvcDoRun(self) -> None:
            """Main service execution method."""
            try:
                # Log service start
                servicemanager.LogMsg(  # type: ignore
                    servicemanager.EVENTLOG_INFORMATION_TYPE,  # type: ignore
                    servicemanager.PYS_SERVICE_STARTED,  # type: ignore
                    (self._svc_name_, ""),
                )
                logger.info("YubiKey Daemon service starting...")

                # Load configuration
                try:
                    config = load_config(self.config_path)
                    logger.info(f"Configuration loaded from: {self.config_path}")
                except ConfigurationError as e:
                    error_msg = f"Configuration error: {e}"
                    logger.error(error_msg)
                    servicemanager.LogErrorMsg(error_msg)  # type: ignore
                    return
                except Exception as e:
                    error_msg = f"Failed to load configuration: {e}"
                    logger.error(error_msg)
                    servicemanager.LogErrorMsg(error_msg)  # type: ignore
                    return

                # Setup logging for service mode
                setup_logging(config, debug=False)
                logger.info("Logging configured for service mode")

                # Run the daemon in a separate thread to allow service control
                import threading

                daemon_thread = threading.Thread(
                    target=self._run_daemon_wrapper, args=(config,), name="DaemonMain", daemon=False
                )
                daemon_thread.start()

                # Wait for stop signal or daemon thread to finish
                while self.is_alive and daemon_thread.is_alive():
                    # Wait for stop event with timeout
                    result = win32event.WaitForSingleObject(self.hWaitStop, 1000)  # type: ignore
                    if result == win32event.WAIT_OBJECT_0:  # type: ignore
                        # Stop event was signaled
                        logger.info("Service stop event received")
                        break

                # Signal daemon to stop
                logger.info("Stopping daemon...")
                from yk_daemon.daemon import shutdown_event

                shutdown_event.set()

                # Wait for daemon thread to finish
                daemon_thread.join(timeout=10.0)
                if daemon_thread.is_alive():
                    logger.warning("Daemon thread did not finish within timeout")

                logger.info("YubiKey Daemon service stopped")
                servicemanager.LogMsg(  # type: ignore
                    servicemanager.EVENTLOG_INFORMATION_TYPE,  # type: ignore
                    servicemanager.PYS_SERVICE_STOPPED,  # type: ignore
                    (self._svc_name_, ""),
                )

            except Exception as e:
                error_msg = f"Service execution error: {e}"
                logger.error(error_msg, exc_info=True)
                servicemanager.LogErrorMsg(error_msg)  # type: ignore

        def _run_daemon_wrapper(self, config: Config) -> None:
            """Wrapper to run daemon with proper exception handling.

            Args:
                config: Configuration object
            """
            try:
                # Import here to avoid circular imports
                from yk_daemon.daemon import run_daemon

                run_daemon(config, debug=False)
            except SystemExit:
                # run_daemon calls sys.exit(), which is expected
                logger.info("Daemon exited normally")
            except Exception as e:
                logger.error(f"Daemon execution error: {e}", exc_info=True)
                self.is_alive = False
else:
    # Create a placeholder class for non-Windows systems
    class YubiKeyDaemonService:  # type: ignore
        """Placeholder service class for non-Windows systems."""

        _svc_name_ = "YubiKeyDaemon"
        _svc_display_name_ = "YubiKey Daemon"
        _svc_description_ = "Not available on non-Windows systems"


def install_service(config_path: str = "config.json") -> bool:
    """Install the Windows service.

    Args:
        config_path: Path to configuration file

    Returns:
        True if installation successful, False otherwise
    """
    if not WINDOWS_SERVICE_AVAILABLE:
        print("ERROR: Windows service functionality is not available")
        print("This requires Windows and the pywin32 package to be installed")
        return False

    try:
        # Get the path to the current Python executable (for logging purposes)
        python_exe = sys.executable

        # Service installation parameters
        service_class = YubiKeyDaemonService
        service_name = service_class._svc_name_
        service_display_name = service_class._svc_display_name_

        # Build service class string
        service_class_string = f"{service_class.__module__}.{service_class.__name__}"

        print(f"Installing Windows service: {service_display_name}")
        print(f"Service name: {service_name}")
        print(f"Service class: {service_class_string}")
        print(f"Python executable: {python_exe}")
        print(f"Config path: {config_path}")

        # Install the service
        # The correct signature is: InstallService(serviceClassString, serviceName, displayName, startType)
        win32serviceutil.InstallService(  # type: ignore
            service_class_string,
            service_name,
            service_display_name,
            startType=win32service.SERVICE_AUTO_START,  # type: ignore
        )

        print(f"Service '{service_display_name}' installed successfully")
        print("The service will start automatically on system boot")
        print("You can also start it manually using:")
        print(f"  sc start {service_name}")
        print(f"  or: net start {service_name}")
        print("  or: python -m yk_daemon.service --start")
        return True

    except Exception as e:
        print(f"ERROR: Failed to install service: {e}")
        return False


def remove_service() -> bool:
    """Remove/uninstall the Windows service.

    Returns:
        True if removal successful, False otherwise
    """
    if not WINDOWS_SERVICE_AVAILABLE:
        print("ERROR: Windows service functionality is not available")
        return False

    try:
        service_name = YubiKeyDaemonService._svc_name_
        service_display_name = YubiKeyDaemonService._svc_display_name_

        print(f"Removing Windows service: {service_display_name}")

        # Stop the service first if it's running
        try:
            win32serviceutil.StopService(service_name)  # type: ignore
            print("Service stopped")
            time.sleep(2)  # Give it time to stop
        except Exception:
            # Service might not be running, continue with removal
            pass

        # Remove the service
        win32serviceutil.RemoveService(service_name)  # type: ignore
        print(f"Service '{service_display_name}' removed successfully")
        return True

    except Exception as e:
        print(f"ERROR: Failed to remove service: {e}")
        return False


def start_service() -> bool:
    """Start the Windows service.

    Returns:
        True if start successful, False otherwise
    """
    if not WINDOWS_SERVICE_AVAILABLE:
        print("ERROR: Windows service functionality is not available")
        return False

    try:
        service_name = YubiKeyDaemonService._svc_name_
        service_display_name = YubiKeyDaemonService._svc_display_name_

        print(f"Starting Windows service: {service_display_name}")
        win32serviceutil.StartService(service_name)  # type: ignore
        print(f"Service '{service_display_name}' started successfully")
        return True

    except Exception as e:
        print(f"ERROR: Failed to start service: {e}")
        return False


def stop_service() -> bool:
    """Stop the Windows service.

    Returns:
        True if stop successful, False otherwise
    """
    if not WINDOWS_SERVICE_AVAILABLE:
        print("ERROR: Windows service functionality is not available")
        return False

    try:
        service_name = YubiKeyDaemonService._svc_name_
        service_display_name = YubiKeyDaemonService._svc_display_name_

        print(f"Stopping Windows service: {service_display_name}")
        win32serviceutil.StopService(service_name)  # type: ignore
        print(f"Service '{service_display_name}' stopped successfully")
        return True

    except Exception as e:
        print(f"ERROR: Failed to stop service: {e}")
        return False


def get_service_status() -> str:
    """Get the current status of the Windows service.

    Returns:
        String describing the service status
    """
    if not WINDOWS_SERVICE_AVAILABLE:
        return "Windows service functionality is not available"

    try:
        service_name = YubiKeyDaemonService._svc_name_
        status = win32serviceutil.QueryServiceStatus(service_name)  # type: ignore
        status_code = status[1]

        status_map = {
            win32service.SERVICE_STOPPED: "Stopped",  # type: ignore
            win32service.SERVICE_START_PENDING: "Start Pending",  # type: ignore
            win32service.SERVICE_STOP_PENDING: "Stop Pending",  # type: ignore
            win32service.SERVICE_RUNNING: "Running",  # type: ignore
            win32service.SERVICE_CONTINUE_PENDING: "Continue Pending",  # type: ignore
            win32service.SERVICE_PAUSE_PENDING: "Pause Pending",  # type: ignore
            win32service.SERVICE_PAUSED: "Paused",  # type: ignore
        }

        return status_map.get(status_code, f"Unknown ({status_code})")

    except Exception as e:
        return f"Error querying status: {e}"


def main() -> NoReturn:
    """Main entry point for service module."""
    import argparse

    parser = argparse.ArgumentParser(
        description="YubiKey Daemon Windows Service Management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --install         # Install as Windows service
  %(prog)s --start           # Start the Windows service
  %(prog)s --stop            # Stop the Windows service
  %(prog)s --remove          # Remove/uninstall the Windows service
  %(prog)s --status          # Show service status
        """,
    )

    parser.add_argument("--install", action="store_true", help="Install as Windows service")

    parser.add_argument("--start", action="store_true", help="Start the Windows service")

    parser.add_argument("--stop", action="store_true", help="Stop the Windows service")

    parser.add_argument(
        "--remove", action="store_true", help="Remove/uninstall the Windows service"
    )

    parser.add_argument("--status", action="store_true", help="Show Windows service status")

    parser.add_argument(
        "--config",
        type=str,
        default="config.json",
        metavar="PATH",
        help="Path to configuration file (used during installation)",
    )

    args = parser.parse_args()

    # Ensure Windows service functionality is available
    if any([args.install, args.start, args.stop, args.remove, args.status]):
        if not WINDOWS_SERVICE_AVAILABLE:
            print("ERROR: Windows service functionality is not available")
            print("This requires Windows and the pywin32 package to be installed")
            sys.exit(1)

    success = True

    if args.install:
        success &= install_service(args.config)
    elif args.start:
        success &= start_service()
    elif args.stop:
        success &= stop_service()
    elif args.remove:
        success &= remove_service()
    elif args.status:
        status = get_service_status()
        print(f"Service status: {status}")
    else:
        # No arguments provided, try to run as service
        if WINDOWS_SERVICE_AVAILABLE:
            # This is called when Windows starts the service
            win32serviceutil.HandleCommandLine(YubiKeyDaemonService)  # type: ignore
        else:
            parser.print_help()
            sys.exit(1)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
