#!/usr/bin/env python3
"""Windows Service wrapper for YubiKey Daemon.

This module provides Windows service functionality allowing the daemon
to run as a background Windows service that can be managed via Services.msc
and automatically start on system boot.
"""

import logging
import sys
import threading
import time

from yk_daemon.config import ConfigurationError, load_config
from yk_daemon.daemon import setup_logging

# Only import Windows-specific modules on Windows
if sys.platform == "win32":
    try:
        import win32event
        import win32service
        import win32serviceutil

        WINDOWS_SERVICE_AVAILABLE = True
    except ImportError:
        WINDOWS_SERVICE_AVAILABLE = False
        win32serviceutil = None
        win32service = None
        win32event = None
else:
    WINDOWS_SERVICE_AVAILABLE = False
    win32serviceutil = None
    win32service = None
    win32event = None

logger = logging.getLogger(__name__)


if WINDOWS_SERVICE_AVAILABLE:

    class YubiKeyDaemonService(win32serviceutil.ServiceFramework):  # type: ignore
        """Windows Service class for YubiKey Daemon."""

        # Service configuration
        _svc_name_ = "YubiKeyDaemonService"
        _svc_display_name_ = "YubiKey Daemon Service"
        _svc_description_ = (
            "Bridges YubiKey OATH-TOTP functionality to WSL and other local applications "
            "through REST API and TCP socket interfaces."
        )

        def __init__(self, args: list) -> None:
            """Initialize the service.

            Args:
                args: Service arguments
            """
            win32serviceutil.ServiceFramework.__init__(self, args)  # type: ignore
            self.stop_event = win32event.CreateEvent(None, 0, 0, None)  # type: ignore
            self.is_alive = True

        def SvcStop(self) -> None:
            """Handle service stop request."""
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)  # type: ignore
            logger.info("Service stop requested")
            win32event.SetEvent(self.stop_event)  # type: ignore
            self.is_alive = False

        def SvcDoRun(self) -> None:
            """Main service execution method."""
            try:
                # Report service as running to avoid timeout
                self.ReportServiceStatus(win32service.SERVICE_RUNNING)  # type: ignore
                logger.info("YubiKey Daemon service starting...")

                # Load configuration
                try:
                    config = load_config("config.json")
                    logger.info("Configuration loaded successfully")
                except ConfigurationError as e:
                    logger.error(f"Configuration error: {e}")
                    return
                except Exception as e:
                    logger.error(f"Failed to load configuration: {e}")
                    return

                # Setup logging for service mode
                setup_logging(config, debug=False)
                logger.info("Logging configured for service mode")

                # Import daemon here to avoid circular imports
                from yk_daemon.daemon import run_daemon, shutdown_event

                # Run the daemon in a separate thread
                daemon_thread = threading.Thread(
                    target=run_daemon, args=(config, False), name="DaemonMain", daemon=False
                )
                daemon_thread.start()
                logger.info("Daemon thread started")

                # Wait for stop signal or daemon thread to finish
                while self.is_alive and daemon_thread.is_alive():
                    result = win32event.WaitForSingleObject(self.stop_event, 1000)  # type: ignore
                    if result == win32event.WAIT_OBJECT_0:  # type: ignore
                        logger.info("Service stop event received")
                        break

                # Signal daemon to stop
                logger.info("Stopping daemon...")
                shutdown_event.set()

                # Wait for daemon thread to finish
                daemon_thread.join(timeout=10.0)
                if daemon_thread.is_alive():
                    logger.warning("Daemon thread did not finish within timeout")

                logger.info("YubiKey Daemon service stopped")

            except Exception as e:
                logger.error(f"Service execution error: {e}", exc_info=True)

else:
    # Create a placeholder class for non-Windows systems
    class YubiKeyDaemonService:  # type: ignore
        """Placeholder service class for non-Windows systems."""

        _svc_name_ = "YubiKeyDaemonService"
        _svc_display_name_ = "YubiKey Daemon Service"
        _svc_description_ = "Not available on non-Windows systems"


class ServiceManager:
    """Manages Windows service operations.

    This class encapsulates all Windows service management operations,
    providing a clean OOP interface for installing, removing, starting,
    stopping, and querying Windows services.
    """

    def __init__(self) -> None:
        """Initialize service manager.

        Raises:
            RuntimeError: If Windows service functionality is not available
        """
        if not WINDOWS_SERVICE_AVAILABLE:
            raise RuntimeError(
                "Windows service functionality is not available. "
                "This requires Windows and the pywin32 package."
            )

        self.service_class = YubiKeyDaemonService
        self.service_name = self.service_class._svc_name_
        self.service_display_name = self.service_class._svc_display_name_
        self.service_class_string = f"{self.service_class.__module__}.{self.service_class.__name__}"

    def install(self, config_path: str = "config.json") -> bool:
        """Install the Windows service.

        Args:
            config_path: Path to configuration file (informational only)

        Returns:
            True if installation successful, False otherwise
        """
        try:
            print(f"Installing Windows service: {self.service_display_name}")
            print(f"Service name: {self.service_name}")
            print(f"Config path: {config_path}")

            win32serviceutil.InstallService(  # type: ignore
                self.service_class_string,
                self.service_name,
                self.service_display_name,
                startType=win32service.SERVICE_AUTO_START,  # type: ignore
            )

            print(f"Service '{self.service_display_name}' installed successfully")
            print("The service will start automatically on system boot")
            print("You can start it manually using:")
            print(f"  sc start {self.service_name}")
            print(f'  or: net start "{self.service_display_name}"')
            return True

        except Exception as e:
            print(f"ERROR: Failed to install service: {e}")
            return False

    def remove(self) -> bool:
        """Remove/uninstall the Windows service.

        Returns:
            True if removal successful, False otherwise
        """
        try:
            print(f"Removing Windows service: {self.service_display_name}")

            # Stop the service first if it's running
            try:
                win32serviceutil.StopService(self.service_name)  # type: ignore
                print("Service stopped")
                time.sleep(2)  # Give it time to stop
            except Exception:
                # Service might not be running, continue with removal
                pass

            # Remove the service
            win32serviceutil.RemoveService(self.service_name)  # type: ignore
            print(f"Service '{self.service_display_name}' removed successfully")
            return True

        except Exception as e:
            print(f"ERROR: Failed to remove service: {e}")
            return False

    def start(self) -> bool:
        """Start the Windows service.

        Returns:
            True if start successful, False otherwise
        """
        try:
            print(f"Starting Windows service: {self.service_display_name}")
            win32serviceutil.StartService(self.service_name)  # type: ignore
            print(f"Service '{self.service_display_name}' started successfully")
            return True

        except Exception as e:
            print(f"ERROR: Failed to start service: {e}")
            return False

    def stop(self) -> bool:
        """Stop the Windows service.

        Returns:
            True if stop successful, False otherwise
        """
        try:
            print(f"Stopping Windows service: {self.service_display_name}")
            win32serviceutil.StopService(self.service_name)  # type: ignore
            print(f"Service '{self.service_display_name}' stopped successfully")
            return True

        except Exception as e:
            print(f"ERROR: Failed to stop service: {e}")
            return False

    def status(self) -> str:
        """Get the current status of the Windows service.

        Returns:
            String describing the service status
        """
        try:
            status = win32serviceutil.QueryServiceStatus(self.service_name)  # type: ignore
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


if __name__ == "__main__":
    # Standard pywin32 service entry point
    # Windows Service Manager calls this when starting the service
    if WINDOWS_SERVICE_AVAILABLE:
        win32serviceutil.HandleCommandLine(YubiKeyDaemonService)  # type: ignore
    else:
        print("ERROR: Windows service functionality is not available")
        print("This requires Windows and the pywin32 package to be installed")
        sys.exit(1)
