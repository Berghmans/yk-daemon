#!/usr/bin/env python3
"""Windows Service wrapper for YubiKey Daemon.

This module provides Windows service functionality allowing the daemon
to run as a background Windows service that can be managed via Services.msc
and automatically start on system boot.

Uses multiprocessing.Process and registers python.exe directly for proper
virtual environment support.
"""

import logging
import os
import sys
import time

from yk_daemon.config import ConfigurationError, load_config
from yk_daemon.daemon import setup_logging

# Only import Windows-specific modules on Windows
if sys.platform == "win32":
    try:
        import multiprocessing

        import win32event
        import win32service
        import win32serviceutil

        try:
            import servicemanager

            SERVICEMANAGER_AVAILABLE = True
        except ImportError:
            servicemanager = None
            SERVICEMANAGER_AVAILABLE = False

        WINDOWS_SERVICE_AVAILABLE = True
    except ImportError:
        WINDOWS_SERVICE_AVAILABLE = False
        SERVICEMANAGER_AVAILABLE = False
        multiprocessing = None
        win32serviceutil = None
        win32service = None
        win32event = None
        servicemanager = None
else:
    WINDOWS_SERVICE_AVAILABLE = False
    SERVICEMANAGER_AVAILABLE = False
    multiprocessing = None
    win32serviceutil = None
    win32service = None
    win32event = None
    servicemanager = None

logger = logging.getLogger(__name__)


def run_daemon_process() -> None:
    """Run daemon in a separate process (called via multiprocessing)."""
    try:
        # Load configuration
        config = load_config("config.json")

        # Setup logging
        setup_logging(config, debug=False)
        logger.info("YubiKey Daemon process starting...")

        # Import and start daemon components
        from yk_daemon.daemon import shutdown_event, start_rest_api, start_socket_server
        from yk_daemon.notifications import create_notifier_from_config
        from yk_daemon.yubikey import YubiKeyInterface

        # Initialize components
        notifier = create_notifier_from_config(config.notifications)
        yubikey = YubiKeyInterface(notifier=notifier)

        # Start servers
        rest_thread = None
        socket_server = None

        if config.rest_api.enabled:
            rest_thread = start_rest_api(config, yubikey)

        if config.socket.enabled:
            socket_server = start_socket_server(config, yubikey)

        logger.info("Daemon started successfully")

        # Wait for shutdown signal (process will be terminated by service)
        while not shutdown_event.is_set():
            shutdown_event.wait(timeout=1.0)

        # Cleanup
        logger.info("Daemon shutting down...")

        if socket_server and socket_server.is_running():
            socket_server.stop()

        if rest_thread and rest_thread.is_alive():
            rest_thread.join(timeout=2.0)

        if notifier:
            notifier.cleanup()

        logger.info("Daemon stopped")

    except (ConfigurationError, Exception) as e:
        logger.error(f"Daemon process error: {e}", exc_info=True)


if WINDOWS_SERVICE_AVAILABLE:

    class YubiKeyDaemonService(win32serviceutil.ServiceFramework):  # type: ignore
        """Windows Service class for YubiKey Daemon.

        Uses multiprocessing.Process and registers python.exe directly
        for proper virtual environment support.
        """

        # Service configuration
        _svc_name_ = "YubiKeyDaemonService"
        _svc_display_name_ = "YubiKey Daemon Service"
        _svc_description_ = (
            "Bridges YubiKey OATH-TOTP functionality to WSL and other local applications "
            "through REST API and TCP socket interfaces."
        )

        # Use python.exe from virtual environment instead of pythonservice.exe
        _exe_name_ = sys.executable  # Points to venv's python.exe
        _exe_args_ = f'-u -E "{os.path.abspath(__file__)}"'

        proc = None

        def __init__(self, args: list) -> None:
            """Initialize the service.

            Args:
                args: Service arguments
            """
            win32serviceutil.ServiceFramework.__init__(self, args)  # type: ignore

        def SvcStop(self) -> None:
            """Handle service stop request."""
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)  # type: ignore

            # Terminate the daemon process
            if self.proc:
                self.proc.terminate()
                self.proc.join(timeout=10.0)

        def SvcRun(self) -> None:
            """Service run method - starts daemon process."""
            # Start daemon in separate process
            self.proc = multiprocessing.Process(target=run_daemon_process)  # type: ignore
            self.proc.start()

            # Report running
            self.ReportServiceStatus(win32service.SERVICE_RUNNING)  # type: ignore

            # Wait for process to finish
            self.SvcDoRun()

            # Report stopping
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)  # type: ignore

        def SvcDoRun(self) -> None:
            """Wait for daemon process to finish."""
            if self.proc:
                self.proc.join()

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
            print(f"Using Python: {sys.executable}")
            print(f"Script: {os.path.abspath(__file__)}")

            # Register python.exe directly instead of pythonservice.exe
            win32serviceutil.InstallService(  # type: ignore
                self.service_class_string,
                self.service_name,
                self.service_display_name,
                startType=win32service.SERVICE_AUTO_START,  # type: ignore
                exeName=sys.executable,  # Use venv's python.exe
                exeArgs=f'-u -E "{os.path.abspath(__file__)}"',  # Script to run
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


def start() -> None:
    """Entry point for service startup.

    Detects how the script is being called:
    - No args (len==1): Service manager startup - use servicemanager
    - --fg: Foreground mode - run daemon directly
    - Other args: Command-line service management
    """
    if not WINDOWS_SERVICE_AVAILABLE:
        print("ERROR: Windows service functionality is not available")
        print("This requires Windows and the pywin32 package to be installed")
        sys.exit(1)

    if len(sys.argv) == 1:
        # Called by Windows Service Manager
        # This is the path when the service actually starts
        if SERVICEMANAGER_AVAILABLE:
            try:
                import win32traceutil  # noqa: F401 - enables debug output
            except ImportError:
                pass  # win32traceutil is optional

            servicemanager.Initialize()  # type: ignore
            servicemanager.PrepareToHostSingle(YubiKeyDaemonService)  # type: ignore
            servicemanager.StartServiceCtrlDispatcher()  # type: ignore
        else:
            # Fallback if servicemanager not available
            win32serviceutil.HandleCommandLine(YubiKeyDaemonService)  # type: ignore

    elif "--fg" in sys.argv:
        # Foreground mode - run daemon directly (for testing)
        print("Running in foreground mode...")
        run_daemon_process()

    else:
        # Command-line service management (install/remove/start/stop)
        win32serviceutil.HandleCommandLine(YubiKeyDaemonService)  # type: ignore


if __name__ == "__main__":
    # Protect multiprocessing entry point
    if multiprocessing:
        multiprocessing.freeze_support()

    try:
        start()
    except (SystemExit, KeyboardInterrupt):
        raise
    except Exception:
        import traceback

        traceback.print_exc()
