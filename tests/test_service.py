#!/usr/bin/env python3
"""Unit tests for Windows service wrapper functionality."""

import unittest
from unittest.mock import MagicMock, patch


class TestServiceModule(unittest.TestCase):
    """Test service module functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock Windows modules for testing on non-Windows systems
        self.mock_win32service = MagicMock()
        self.mock_win32serviceutil = MagicMock()
        self.mock_win32event = MagicMock()
        self.mock_servicemanager = MagicMock()

        # Patch Windows-specific imports
        modules = {
            "win32service": self.mock_win32service,
            "win32serviceutil": self.mock_win32serviceutil,
            "win32event": self.mock_win32event,
            "servicemanager": self.mock_servicemanager,
            "msvcrt": MagicMock(),  # Mock Windows console module
        }

        self.patchers = []
        for name, module in modules.items():
            patcher = patch.dict("sys.modules", {name: module})
            patcher.start()
            self.patchers.append(patcher)

        # Mock platform detection and Windows service availability
        self.platform_patcher = patch("sys.platform", "win32")
        self.platform_patcher.start()

        # Mock WINDOWS_SERVICE_AVAILABLE in the service module
        self.service_available_patcher = patch("yk_daemon.service.WINDOWS_SERVICE_AVAILABLE", True)
        self.service_available_patcher.start()

    def tearDown(self):
        """Clean up test fixtures."""
        for patcher in self.patchers:
            patcher.stop()
        self.platform_patcher.stop()
        self.service_available_patcher.stop()

    def test_service_class_init(self):
        """Test YubiKeyDaemonService initialization."""
        from yk_daemon.service import YubiKeyDaemonService

        # Mock Windows service framework
        self.mock_win32serviceutil.ServiceFramework = MagicMock()
        self.mock_win32event.CreateEvent.return_value = "mock_event"

        # Create service instance
        service = YubiKeyDaemonService(["test"])

        # Verify service attributes
        self.assertEqual(service._svc_name_, "YubiKeyDaemon")
        self.assertEqual(service._svc_display_name_, "YubiKey Daemon")
        self.assertIn("YubiKey OATH-TOTP", service._svc_description_)
        self.assertTrue(service.is_alive)

    def test_service_class_config_path(self):
        """Test configuration path detection."""
        from yk_daemon.service import YubiKeyDaemonService

        # Mock Windows service framework
        self.mock_win32serviceutil.ServiceFramework = MagicMock()
        self.mock_win32event.CreateEvent.return_value = "mock_event"

        with patch("sys.executable", "/path/to/python.exe"):
            with patch("pathlib.Path.exists", return_value=True):
                service = YubiKeyDaemonService(["test"])
                # Should find config in same directory as executable
                self.assertIn("config.json", service.config_path)

    def test_install_service_success(self):
        """Test successful service installation."""
        from yk_daemon.service import install_service

        # Mock successful installation
        self.mock_win32serviceutil.InstallService.return_value = None

        with patch("builtins.print") as mock_print:
            result = install_service("test_config.json")

        self.assertTrue(result)
        self.mock_win32serviceutil.InstallService.assert_called_once()
        mock_print.assert_called()

    def test_install_service_failure(self):
        """Test service installation failure."""
        from yk_daemon.service import install_service

        # Mock installation failure
        self.mock_win32serviceutil.InstallService.side_effect = Exception("Installation failed")

        with patch("builtins.print") as mock_print:
            result = install_service("test_config.json")

        self.assertFalse(result)
        mock_print.assert_called()

    def test_remove_service_success(self):
        """Test successful service removal."""
        from yk_daemon.service import remove_service

        # Mock successful removal
        self.mock_win32serviceutil.StopService.return_value = None
        self.mock_win32serviceutil.RemoveService.return_value = None

        with patch("builtins.print") as mock_print:
            with patch("time.sleep"):
                result = remove_service()

        self.assertTrue(result)
        self.mock_win32serviceutil.RemoveService.assert_called_once()
        mock_print.assert_called()

    def test_remove_service_failure(self):
        """Test service removal failure."""
        from yk_daemon.service import remove_service

        # Mock removal failure
        self.mock_win32serviceutil.RemoveService.side_effect = Exception("Removal failed")

        with patch("builtins.print") as mock_print:
            result = remove_service()

        self.assertFalse(result)
        mock_print.assert_called()

    def test_start_service_success(self):
        """Test successful service start."""
        from yk_daemon.service import start_service

        # Mock successful start
        self.mock_win32serviceutil.StartService.return_value = None

        with patch("builtins.print") as mock_print:
            result = start_service()

        self.assertTrue(result)
        self.mock_win32serviceutil.StartService.assert_called_once()
        mock_print.assert_called()

    def test_start_service_failure(self):
        """Test service start failure."""
        from yk_daemon.service import start_service

        # Mock start failure
        self.mock_win32serviceutil.StartService.side_effect = Exception("Start failed")

        with patch("builtins.print") as mock_print:
            result = start_service()

        self.assertFalse(result)
        mock_print.assert_called()

    def test_stop_service_success(self):
        """Test successful service stop."""
        from yk_daemon.service import stop_service

        # Mock successful stop
        self.mock_win32serviceutil.StopService.return_value = None

        with patch("builtins.print") as mock_print:
            result = stop_service()

        self.assertTrue(result)
        self.mock_win32serviceutil.StopService.assert_called_once()
        mock_print.assert_called()

    def test_stop_service_failure(self):
        """Test service stop failure."""
        from yk_daemon.service import stop_service

        # Mock stop failure
        self.mock_win32serviceutil.StopService.side_effect = Exception("Stop failed")

        with patch("builtins.print") as mock_print:
            result = stop_service()

        self.assertFalse(result)
        mock_print.assert_called()

    def test_get_service_status(self):
        """Test service status query."""
        from yk_daemon.service import get_service_status

        # Mock service status constants
        self.mock_win32service.SERVICE_RUNNING = 4
        self.mock_win32service.SERVICE_STOPPED = 1

        # Mock status query
        self.mock_win32serviceutil.QueryServiceStatus.return_value = (None, 4)  # SERVICE_RUNNING

        status = get_service_status()

        self.assertEqual(status, "Running")
        self.mock_win32serviceutil.QueryServiceStatus.assert_called_once()

    def test_get_service_status_error(self):
        """Test service status query error."""
        from yk_daemon.service import get_service_status

        # Mock status query failure
        self.mock_win32serviceutil.QueryServiceStatus.side_effect = Exception("Query failed")

        status = get_service_status()

        self.assertIn("Error querying status", status)

    def test_non_windows_platform(self):
        """Test service operations on non-Windows platforms."""
        # Stop the Windows platform mock
        self.platform_patcher.stop()

        with patch("sys.platform", "linux"):
            from yk_daemon.service import (
                install_service,
                remove_service,
                start_service,
                stop_service,
            )

            with patch("builtins.print"):
                # All operations should fail on non-Windows
                self.assertFalse(install_service())
                self.assertFalse(start_service())
                self.assertFalse(stop_service())
                self.assertFalse(remove_service())

        # Restart platform mock for cleanup
        self.platform_patcher = patch("sys.platform", "win32")
        self.platform_patcher.start()


class TestServiceMain(unittest.TestCase):
    """Test service main function and command-line interface."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock Windows modules
        self.mock_win32service = MagicMock()
        self.mock_win32serviceutil = MagicMock()
        self.mock_win32event = MagicMock()
        self.mock_servicemanager = MagicMock()

        modules = {
            "win32service": self.mock_win32service,
            "win32serviceutil": self.mock_win32serviceutil,
            "win32event": self.mock_win32event,
            "servicemanager": self.mock_servicemanager,
        }

        self.patchers = []
        for name, module in modules.items():
            patcher = patch.dict("sys.modules", {name: module})
            patcher.start()
            self.patchers.append(patcher)

        self.platform_patcher = patch("sys.platform", "win32")
        self.platform_patcher.start()

    def tearDown(self):
        """Clean up test fixtures."""
        for patcher in self.patchers:
            patcher.stop()
        self.platform_patcher.stop()

    def test_main_install_command(self):
        """Test main function with --install command."""
        from yk_daemon.service import main

        test_args = ["service.py", "--install", "--config", "test.json"]

        with patch("sys.argv", test_args):
            with patch("yk_daemon.service.install_service", return_value=True) as mock_install:
                with patch("sys.exit") as mock_exit:
                    main()

                mock_install.assert_called_once_with("test.json")
                mock_exit.assert_called_once_with(0)

    def test_main_start_command(self):
        """Test main function with --start command."""
        from yk_daemon.service import main

        test_args = ["service.py", "--start"]

        with patch("sys.argv", test_args):
            with patch("yk_daemon.service.start_service", return_value=True) as mock_start:
                with patch("sys.exit") as mock_exit:
                    main()

                mock_start.assert_called_once()
                mock_exit.assert_called_once_with(0)

    def test_main_stop_command(self):
        """Test main function with --stop command."""
        from yk_daemon.service import main

        test_args = ["service.py", "--stop"]

        with patch("sys.argv", test_args):
            with patch("yk_daemon.service.stop_service", return_value=True) as mock_stop:
                with patch("sys.exit") as mock_exit:
                    main()

                mock_stop.assert_called_once()
                mock_exit.assert_called_once_with(0)

    def test_main_remove_command(self):
        """Test main function with --remove command."""
        from yk_daemon.service import main

        test_args = ["service.py", "--remove"]

        with patch("sys.argv", test_args):
            with patch("yk_daemon.service.remove_service", return_value=True) as mock_remove:
                with patch("sys.exit") as mock_exit:
                    main()

                mock_remove.assert_called_once()
                mock_exit.assert_called_once_with(0)

    def test_main_status_command(self):
        """Test main function with --status command."""
        from yk_daemon.service import main

        test_args = ["service.py", "--status"]

        with patch("sys.argv", test_args):
            with patch(
                "yk_daemon.service.get_service_status", return_value="Running"
            ) as mock_status:
                with patch("builtins.print") as mock_print:
                    with patch("sys.exit") as mock_exit:
                        main()

                mock_status.assert_called_once()
                mock_print.assert_called_with("Service status: Running")
                mock_exit.assert_called_once_with(0)

    def test_main_no_args_windows(self):
        """Test main function with no arguments on Windows."""
        from yk_daemon.service import main

        test_args = ["service.py"]

        with patch("sys.argv", test_args):
            with patch("yk_daemon.service.win32serviceutil.HandleCommandLine") as mock_handle:
                with patch("sys.exit") as mock_exit:
                    main()

                mock_handle.assert_called_once()
                mock_exit.assert_called_once_with(0)

    def test_main_no_args_non_windows(self):
        """Test main function with no arguments on non-Windows."""
        # Stop Windows platform mock
        self.platform_patcher.stop()

        with patch("sys.platform", "linux"):
            from yk_daemon.service import main

            test_args = ["service.py"]

            with patch("sys.argv", test_args):
                with patch("argparse.ArgumentParser.print_help") as mock_help:
                    with patch("sys.exit") as mock_exit:
                        main()

                    mock_help.assert_called_once()
                    mock_exit.assert_called_once_with(1)

        # Restart platform mock
        self.platform_patcher = patch("sys.platform", "win32")
        self.platform_patcher.start()

    def test_main_command_failure(self):
        """Test main function when service command fails."""
        from yk_daemon.service import main

        test_args = ["service.py", "--install"]

        with patch("sys.argv", test_args):
            with patch("yk_daemon.service.install_service", return_value=False) as mock_install:
                with patch("sys.exit") as mock_exit:
                    main()

                mock_install.assert_called_once()
                mock_exit.assert_called_once_with(1)


class TestDaemonServiceIntegration(unittest.TestCase):
    """Test integration between daemon and service modules."""

    def test_daemon_service_arguments(self):
        """Test that daemon module properly handles service arguments."""
        from yk_daemon.daemon import parse_arguments

        # Test that service arguments are recognized
        test_args = ["daemon.py", "--install", "--config", "test.json"]

        with patch("sys.argv", test_args):
            args = parse_arguments()

        self.assertTrue(args.install)
        self.assertEqual(args.config, "test.json")

    def test_daemon_main_service_delegation(self):
        """Test that daemon main function properly delegates to service functions."""
        from yk_daemon.daemon import main

        test_args = ["daemon.py", "--install", "--config", "test.json"]

        with patch("sys.argv", test_args):
            with patch("yk_daemon.service.install_service", return_value=True) as mock_install:
                with patch("sys.exit") as mock_exit:
                    main()

                mock_install.assert_called_once_with("test.json")
                mock_exit.assert_called_once_with(0)

    def test_daemon_main_service_import_error(self):
        """Test daemon main function handles service import errors gracefully."""
        # Mock the import to fail
        with patch.dict("sys.modules", {"yk_daemon.service": None}):
            from yk_daemon.daemon import main

            test_args = ["daemon.py", "--install"]

            with patch("sys.argv", test_args):
                with patch("builtins.print") as mock_print:
                    with patch("sys.exit") as mock_exit:
                        main()

                    mock_print.assert_called()
                    mock_exit.assert_called_once_with(1)


if __name__ == "__main__":
    unittest.main()
