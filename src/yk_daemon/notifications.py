"""Notifications module for YubiKey Daemon.

This module provides Windows popup notifications and sound alerts when YubiKey
touch is required. Both popup and sound can be independently enabled/disabled
through configuration.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Import notification libraries with error handling
_PLYER_AVAILABLE = False
_PYGAME_AVAILABLE = False

try:
    from plyer import notification as plyer_notification

    _PLYER_AVAILABLE = True
except ImportError:
    logger.warning("plyer not available - popup notifications will be disabled")

try:
    import pygame

    _PYGAME_AVAILABLE = True
except ImportError:
    logger.warning("pygame not available - sound notifications will be disabled")


class NotificationError(Exception):
    """Raised when notification fails."""

    pass


class Notifier:
    """Handles popup and sound notifications for YubiKey touch requests."""

    def __init__(
        self,
        popup_enabled: bool = True,
        sound_enabled: bool = True,
        sound_file: str | None = None,
    ):
        """Initialize the notifier.

        Args:
            popup_enabled: Enable popup notifications
            sound_enabled: Enable sound notifications
            sound_file: Path to notification sound file (WAV format recommended)
        """
        self.popup_enabled = popup_enabled
        self.sound_enabled = sound_enabled
        self.sound_file = sound_file
        self._pygame_initialized = False

        # Validate configuration
        if self.popup_enabled and not _PLYER_AVAILABLE:
            logger.warning(
                "Popup notifications enabled but plyer is not available. "
                "Install with: pip install plyer"
            )
            self.popup_enabled = False

        if self.sound_enabled and not _PYGAME_AVAILABLE:
            logger.warning(
                "Sound notifications enabled but pygame is not available. "
                "Install with: pip install pygame"
            )
            self.sound_enabled = False

        # Initialize pygame mixer if sound is enabled
        if self.sound_enabled and _PYGAME_AVAILABLE:
            try:
                # Initialize pygame mixer for sound playback
                # Use -1 for default frequency, -1 for default size,
                # 2 for stereo, and 2048 for buffer
                pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
                self._pygame_initialized = True
                logger.debug("Pygame mixer initialized successfully")
            except pygame.error as e:
                logger.warning(f"Failed to initialize pygame mixer: {e}")
                self.sound_enabled = False

        # Validate sound file if sound is enabled
        if self.sound_enabled and self.sound_file:
            sound_path = self._get_sound_path(self.sound_file)
            if not sound_path or not sound_path.exists():
                logger.warning(
                    f"Sound file '{self.sound_file}' not found. "
                    "Sound notifications will be disabled."
                )
                self.sound_enabled = False
            else:
                logger.debug(f"Sound file configured: {sound_path}")

    def _get_sound_path(self, sound_file: str) -> Path | None:
        """Get the absolute path to the sound file.

        Tries multiple locations:
        1. Absolute path if provided
        2. Relative to current working directory
        3. Relative to this module's directory

        Args:
            sound_file: Sound file path (absolute or relative)

        Returns:
            Absolute path to sound file, or None if not found
        """
        sound_path = Path(sound_file)

        # If absolute path, return it
        if sound_path.is_absolute():
            return sound_path if sound_path.exists() else None

        # Try relative to current working directory
        cwd_path = Path.cwd() / sound_file
        if cwd_path.exists():
            return cwd_path

        # Try relative to project root directory
        # From src/yk_daemon/notifications.py, go up two levels to project root
        project_root = Path(__file__).parent.parent.parent
        project_path = project_root / sound_file
        if project_path.exists():
            return project_path

        return None

    def notify(self, title: str = "YubiKey Touch Required", message: str = "") -> None:
        """Show notification (popup and/or sound).

        This is a convenience method that calls both show_popup() and play_sound()
        based on configuration.

        Args:
            title: Notification title
            message: Notification message

        Raises:
            NotificationError: If both popup and sound fail (and both are enabled)
        """
        popup_success = True
        sound_success = True

        if self.popup_enabled:
            try:
                self.show_popup(title, message)
            except NotificationError as e:
                logger.warning(f"Popup notification failed: {e}")
                popup_success = False

        if self.sound_enabled:
            try:
                self.play_sound()
            except NotificationError as e:
                logger.warning(f"Sound notification failed: {e}")
                sound_success = False

        # If both enabled and both failed, raise error
        if self.popup_enabled and self.sound_enabled:
            if not popup_success and not sound_success:
                raise NotificationError("Both popup and sound notifications failed")

        # If only one enabled and it failed, raise error
        if self.popup_enabled and not self.sound_enabled and not popup_success:
            raise NotificationError("Popup notification failed")
        if self.sound_enabled and not self.popup_enabled and not sound_success:
            raise NotificationError("Sound notification failed")

    def show_popup(self, title: str = "YubiKey Touch Required", message: str = "") -> None:
        """Show a popup notification.

        Args:
            title: Notification title
            message: Notification message (optional)

        Raises:
            NotificationError: If popup notification fails
        """
        if not self.popup_enabled:
            logger.debug("Popup notifications disabled, skipping")
            return

        if not _PLYER_AVAILABLE:
            raise NotificationError("plyer library not available")

        # Default message if not provided
        if not message:
            message = "Please touch your YubiKey to continue"

        try:
            # Show notification using plyer
            # On Windows, this uses win10toast under the hood
            plyer_notification.notify(
                title=title,
                message=message,
                app_name="YubiKey Daemon",
                timeout=10,  # Display for 10 seconds
            )
            logger.debug(f"Popup notification shown: {title}")
        except Exception as e:
            error_msg = f"Failed to show popup notification: {e}"
            logger.error(error_msg)
            raise NotificationError(error_msg) from e

    def play_sound(self) -> None:
        """Play notification sound.

        Raises:
            NotificationError: If sound playback fails
        """
        if not self.sound_enabled:
            logger.debug("Sound notifications disabled, skipping")
            return

        if not _PYGAME_AVAILABLE:
            raise NotificationError("pygame library not available")

        if not self._pygame_initialized:
            raise NotificationError("pygame mixer not initialized")

        if not self.sound_file:
            raise NotificationError("No sound file configured")

        sound_path = self._get_sound_path(self.sound_file)
        if not sound_path or not sound_path.exists():
            raise NotificationError(f"Sound file not found: {self.sound_file}")

        try:
            # Load and play the sound
            sound = pygame.mixer.Sound(str(sound_path))
            sound.play()
            logger.debug(f"Sound notification played: {sound_path}")
        except Exception as e:
            # Catch both pygame.error and any other exceptions
            error_msg = f"Failed to play sound: {e}"
            logger.error(error_msg)
            raise NotificationError(error_msg) from e

    def cleanup(self) -> None:
        """Clean up resources.

        Should be called when the notifier is no longer needed.
        """
        if self._pygame_initialized:
            try:
                pygame.mixer.quit()
                self._pygame_initialized = False
                logger.debug("Pygame mixer cleaned up")
            except Exception as e:
                logger.warning(f"Error cleaning up pygame mixer: {e}")

    def __enter__(self) -> "Notifier":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore
        """Context manager exit."""
        self.cleanup()


def create_notifier_from_config(notifications_config) -> Notifier:  # type: ignore
    """Create a Notifier instance from NotificationsConfig.

    Args:
        notifications_config: NotificationsConfig instance

    Returns:
        Configured Notifier instance
    """
    return Notifier(
        popup_enabled=notifications_config.popup,
        sound_enabled=notifications_config.sound,
        sound_file=notifications_config.sound_file,
    )
