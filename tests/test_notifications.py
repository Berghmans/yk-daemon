"""Tests for the notifications module."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from yk_daemon.config import NotificationsConfig
from yk_daemon.notifications import NotificationError, Notifier, create_notifier_from_config


class TestNotifierInitialization:
    """Tests for Notifier initialization."""

    def test_init_default_values(self) -> None:
        """Test Notifier initialization with default values."""
        notifier = Notifier()
        # Note: popup_enabled and sound_enabled may be False if libraries aren't available
        # or if pygame mixer fails to initialize (e.g., no audio device)
        # We just check that the values are set, not what they are
        assert isinstance(notifier.popup_enabled, bool)
        assert isinstance(notifier.sound_enabled, bool)
        assert notifier.sound_file is None

    def test_init_custom_values(self) -> None:
        """Test Notifier initialization with custom values."""
        notifier = Notifier(popup_enabled=False, sound_enabled=True, sound_file="custom.wav")
        assert notifier.popup_enabled is False
        # sound_enabled may be False if pygame can't initialize or sound file not found
        assert isinstance(notifier.sound_enabled, bool)
        assert notifier.sound_file == "custom.wav"

    @patch("yk_daemon.notifications._PLYER_AVAILABLE", False)
    def test_init_plyer_not_available(self) -> None:
        """Test initialization when plyer is not available."""
        notifier = Notifier(popup_enabled=True)
        assert notifier.popup_enabled is False

    @patch("yk_daemon.notifications._PYGAME_AVAILABLE", False)
    def test_init_pygame_not_available(self) -> None:
        """Test initialization when pygame is not available."""
        notifier = Notifier(sound_enabled=True)
        assert notifier.sound_enabled is False

    @patch("yk_daemon.notifications._PYGAME_AVAILABLE", True)
    @patch("yk_daemon.notifications.pygame")
    def test_init_pygame_initialization_success(self, mock_pygame: Mock) -> None:
        """Test successful pygame mixer initialization."""
        mock_pygame.mixer.init = Mock()
        notifier = Notifier(sound_enabled=True)
        assert notifier._pygame_initialized is True
        mock_pygame.mixer.init.assert_called_once()

    @patch("yk_daemon.notifications._PYGAME_AVAILABLE", True)
    @patch("yk_daemon.notifications.pygame")
    def test_init_pygame_initialization_failure(self, mock_pygame: Mock) -> None:
        """Test pygame mixer initialization failure."""
        mock_pygame.error = Exception
        mock_pygame.mixer.init.side_effect = Exception("Init failed")
        notifier = Notifier(sound_enabled=True)
        assert notifier.sound_enabled is False
        assert notifier._pygame_initialized is False

    @patch("yk_daemon.notifications._PYGAME_AVAILABLE", True)
    @patch("yk_daemon.notifications.pygame")
    def test_init_sound_file_not_found(self, mock_pygame: Mock, tmp_path: Path) -> None:
        """Test initialization with non-existent sound file."""
        mock_pygame.mixer.init = Mock()
        notifier = Notifier(sound_enabled=True, sound_file="nonexistent.wav")
        assert notifier.sound_enabled is False


class TestGetSoundPath:
    """Tests for _get_sound_path method."""

    def test_get_sound_path_absolute(self, tmp_path: Path) -> None:
        """Test getting absolute path."""
        sound_file = tmp_path / "test.wav"
        sound_file.touch()
        notifier = Notifier(sound_enabled=False)
        result = notifier._get_sound_path(str(sound_file))
        assert result == sound_file

    def test_get_sound_path_absolute_not_exists(self, tmp_path: Path) -> None:
        """Test getting absolute path that doesn't exist."""
        sound_file = tmp_path / "nonexistent.wav"
        notifier = Notifier(sound_enabled=False)
        result = notifier._get_sound_path(str(sound_file))
        assert result is None

    def test_get_sound_path_relative_cwd(self, tmp_path: Path, monkeypatch) -> None:  # type: ignore
        """Test getting relative path from cwd."""
        monkeypatch.chdir(tmp_path)
        sound_file = tmp_path / "test.wav"
        sound_file.touch()
        notifier = Notifier(sound_enabled=False)
        result = notifier._get_sound_path("test.wav")
        assert result == sound_file

    def test_get_sound_path_relative_module_dir(self, tmp_path: Path) -> None:
        """Test getting relative path from module directory."""
        # Create a sound file in the project root
        module_dir = Path(__file__).parent.parent
        sound_file = module_dir / "test_sound.wav"
        try:
            sound_file.touch()
            notifier = Notifier(sound_enabled=False)
            result = notifier._get_sound_path("test_sound.wav")
            assert result == sound_file
        finally:
            if sound_file.exists():
                sound_file.unlink()

    def test_get_sound_path_not_found(self) -> None:
        """Test getting path for non-existent file."""
        notifier = Notifier(sound_enabled=False)
        result = notifier._get_sound_path("nonexistent.wav")
        assert result is None


class TestShowPopup:
    """Tests for show_popup method."""

    @patch("yk_daemon.notifications._PLYER_AVAILABLE", True)
    @patch("yk_daemon.notifications.plyer_notification")
    def test_show_popup_success(self, mock_notification: Mock) -> None:
        """Test successful popup notification."""
        notifier = Notifier(popup_enabled=True, sound_enabled=False)
        notifier.show_popup("Test Title", "Test Message")
        mock_notification.notify.assert_called_once_with(
            title="Test Title",
            message="Test Message",
            app_name="YubiKey Daemon",
            timeout=10,
        )

    @patch("yk_daemon.notifications._PLYER_AVAILABLE", True)
    @patch("yk_daemon.notifications.plyer_notification")
    def test_show_popup_default_message(self, mock_notification: Mock) -> None:
        """Test popup with default message."""
        notifier = Notifier(popup_enabled=True, sound_enabled=False)
        notifier.show_popup("Test Title")
        mock_notification.notify.assert_called_once()
        call_args = mock_notification.notify.call_args
        assert call_args[1]["message"] == "Please touch your YubiKey to continue"

    def test_show_popup_disabled(self) -> None:
        """Test popup when disabled."""
        notifier = Notifier(popup_enabled=False, sound_enabled=False)
        # Should not raise any exception
        notifier.show_popup("Test Title", "Test Message")

    @patch("yk_daemon.notifications._PLYER_AVAILABLE", False)
    def test_show_popup_plyer_not_available(self) -> None:
        """Test popup when plyer is not available."""
        notifier = Notifier(popup_enabled=True, sound_enabled=False)
        # popup_enabled should be False after init
        assert notifier.popup_enabled is False

    @patch("yk_daemon.notifications._PLYER_AVAILABLE", True)
    @patch("yk_daemon.notifications.plyer_notification")
    def test_show_popup_exception(self, mock_notification: Mock) -> None:
        """Test popup notification failure."""
        mock_notification.notify.side_effect = Exception("Notification failed")
        notifier = Notifier(popup_enabled=True, sound_enabled=False)
        with pytest.raises(NotificationError, match="Failed to show popup notification"):
            notifier.show_popup("Test Title", "Test Message")


class TestPlaySound:
    """Tests for play_sound method."""

    @patch("yk_daemon.notifications._PYGAME_AVAILABLE", True)
    @patch("yk_daemon.notifications.pygame")
    def test_play_sound_success(self, mock_pygame: Mock, tmp_path: Path) -> None:
        """Test successful sound playback."""
        # Create a temporary sound file
        sound_file = tmp_path / "test.wav"
        sound_file.touch()

        mock_sound = Mock()
        mock_pygame.mixer.Sound.return_value = mock_sound

        notifier = Notifier(popup_enabled=False, sound_enabled=True, sound_file=str(sound_file))
        notifier.play_sound()

        mock_pygame.mixer.Sound.assert_called_once_with(str(sound_file))
        mock_sound.play.assert_called_once()

    def test_play_sound_disabled(self) -> None:
        """Test play_sound when sound is disabled."""
        notifier = Notifier(popup_enabled=False, sound_enabled=False)
        # Should not raise any exception
        notifier.play_sound()

    @patch("yk_daemon.notifications._PYGAME_AVAILABLE", False)
    def test_play_sound_pygame_not_available(self) -> None:
        """Test play_sound when pygame is not available."""
        notifier = Notifier(popup_enabled=False, sound_enabled=True)
        # sound_enabled should be False after init
        assert notifier.sound_enabled is False

    @patch("yk_daemon.notifications._PYGAME_AVAILABLE", True)
    @patch("yk_daemon.notifications.pygame")
    def test_play_sound_no_file_configured(self, mock_pygame: Mock) -> None:
        """Test play_sound with no sound file configured."""
        notifier = Notifier(popup_enabled=False, sound_enabled=True, sound_file=None)
        notifier.sound_enabled = True  # Force enable for test
        notifier._pygame_initialized = True
        with pytest.raises(NotificationError, match="No sound file configured"):
            notifier.play_sound()

    @patch("yk_daemon.notifications._PYGAME_AVAILABLE", True)
    @patch("yk_daemon.notifications.pygame")
    def test_play_sound_file_not_found(self, mock_pygame: Mock) -> None:
        """Test play_sound with non-existent file."""
        notifier = Notifier(popup_enabled=False, sound_enabled=True, sound_file="nonexistent.wav")
        # Force enable for test
        notifier.sound_enabled = True
        notifier._pygame_initialized = True
        with pytest.raises(NotificationError, match="Sound file not found"):
            notifier.play_sound()

    @patch("yk_daemon.notifications._PYGAME_AVAILABLE", True)
    @patch("yk_daemon.notifications.pygame")
    def test_play_sound_pygame_error(self, mock_pygame: Mock, tmp_path: Path) -> None:
        """Test play_sound with pygame error."""
        sound_file = tmp_path / "test.wav"
        sound_file.touch()

        mock_pygame.mixer.Sound.side_effect = Exception("Playback failed")

        notifier = Notifier(popup_enabled=False, sound_enabled=True, sound_file=str(sound_file))
        with pytest.raises(NotificationError, match="Failed to play sound"):
            notifier.play_sound()

    @patch("yk_daemon.notifications._PYGAME_AVAILABLE", True)
    @patch("yk_daemon.notifications.pygame")
    def test_play_sound_mixer_not_initialized(self, mock_pygame: Mock) -> None:
        """Test play_sound when mixer is not initialized."""
        notifier = Notifier(popup_enabled=False, sound_enabled=True, sound_file="test.wav")
        notifier.sound_enabled = True  # Force enable
        notifier._pygame_initialized = False  # Force not initialized
        with pytest.raises(NotificationError, match="pygame mixer not initialized"):
            notifier.play_sound()


class TestNotify:
    """Tests for notify method."""

    @patch("yk_daemon.notifications._PLYER_AVAILABLE", True)
    @patch("yk_daemon.notifications._PYGAME_AVAILABLE", True)
    @patch("yk_daemon.notifications.plyer_notification")
    @patch("yk_daemon.notifications.pygame")
    def test_notify_both_enabled_success(
        self, mock_pygame: Mock, mock_notification: Mock, tmp_path: Path
    ) -> None:
        """Test notify with both popup and sound enabled."""
        sound_file = tmp_path / "test.wav"
        sound_file.touch()

        mock_sound = Mock()
        mock_pygame.mixer.Sound.return_value = mock_sound

        notifier = Notifier(popup_enabled=True, sound_enabled=True, sound_file=str(sound_file))
        notifier.notify("Test Title", "Test Message")

        mock_notification.notify.assert_called_once()
        mock_sound.play.assert_called_once()

    @patch("yk_daemon.notifications._PLYER_AVAILABLE", True)
    @patch("yk_daemon.notifications.plyer_notification")
    def test_notify_only_popup_enabled(self, mock_notification: Mock) -> None:
        """Test notify with only popup enabled."""
        notifier = Notifier(popup_enabled=True, sound_enabled=False)
        notifier.notify("Test Title", "Test Message")
        mock_notification.notify.assert_called_once()

    @patch("yk_daemon.notifications._PYGAME_AVAILABLE", True)
    @patch("yk_daemon.notifications.pygame")
    def test_notify_only_sound_enabled(self, mock_pygame: Mock, tmp_path: Path) -> None:
        """Test notify with only sound enabled."""
        sound_file = tmp_path / "test.wav"
        sound_file.touch()

        mock_sound = Mock()
        mock_pygame.mixer.Sound.return_value = mock_sound

        notifier = Notifier(popup_enabled=False, sound_enabled=True, sound_file=str(sound_file))
        notifier.notify()
        mock_sound.play.assert_called_once()

    @patch("yk_daemon.notifications._PLYER_AVAILABLE", True)
    @patch("yk_daemon.notifications._PYGAME_AVAILABLE", True)
    @patch("yk_daemon.notifications.plyer_notification")
    @patch("yk_daemon.notifications.pygame")
    def test_notify_both_fail(
        self, mock_pygame: Mock, mock_notification: Mock, tmp_path: Path
    ) -> None:
        """Test notify when both popup and sound fail."""
        sound_file = tmp_path / "test.wav"
        sound_file.touch()

        mock_notification.notify.side_effect = Exception("Popup failed")
        mock_pygame.mixer.Sound.side_effect = Exception("Sound failed")

        notifier = Notifier(popup_enabled=True, sound_enabled=True, sound_file=str(sound_file))
        with pytest.raises(NotificationError, match="Both popup and sound notifications failed"):
            notifier.notify()

    @patch("yk_daemon.notifications._PLYER_AVAILABLE", True)
    @patch("yk_daemon.notifications.plyer_notification")
    def test_notify_popup_fails_only_popup_enabled(self, mock_notification: Mock) -> None:
        """Test notify when only popup enabled and it fails."""
        mock_notification.notify.side_effect = Exception("Popup failed")
        notifier = Notifier(popup_enabled=True, sound_enabled=False)
        with pytest.raises(NotificationError, match="Popup notification failed"):
            notifier.notify()

    @patch("yk_daemon.notifications._PYGAME_AVAILABLE", True)
    @patch("yk_daemon.notifications.pygame")
    def test_notify_sound_fails_only_sound_enabled(self, mock_pygame: Mock, tmp_path: Path) -> None:
        """Test notify when only sound enabled and it fails."""
        sound_file = tmp_path / "test.wav"
        sound_file.touch()

        mock_pygame.mixer.Sound.side_effect = Exception("Sound failed")

        notifier = Notifier(popup_enabled=False, sound_enabled=True, sound_file=str(sound_file))
        with pytest.raises(NotificationError, match="Sound notification failed"):
            notifier.notify()


class TestCleanup:
    """Tests for cleanup and context manager."""

    @patch("yk_daemon.notifications._PYGAME_AVAILABLE", True)
    @patch("yk_daemon.notifications.pygame")
    def test_cleanup_success(self, mock_pygame: Mock) -> None:
        """Test successful cleanup."""
        notifier = Notifier(popup_enabled=False, sound_enabled=True)
        notifier._pygame_initialized = True
        notifier.cleanup()
        mock_pygame.mixer.quit.assert_called_once()
        assert notifier._pygame_initialized is False

    @patch("yk_daemon.notifications._PYGAME_AVAILABLE", True)
    @patch("yk_daemon.notifications.pygame")
    def test_cleanup_exception(self, mock_pygame: Mock) -> None:
        """Test cleanup with exception."""
        mock_pygame.mixer.quit.side_effect = Exception("Cleanup failed")
        notifier = Notifier(popup_enabled=False, sound_enabled=True)
        notifier._pygame_initialized = True
        # Should not raise exception
        notifier.cleanup()

    @patch("yk_daemon.notifications._PYGAME_AVAILABLE", True)
    @patch("yk_daemon.notifications.pygame")
    def test_context_manager(self, mock_pygame: Mock) -> None:
        """Test context manager usage."""
        with Notifier(popup_enabled=False, sound_enabled=True) as notifier:
            assert notifier is not None
        # cleanup should be called
        mock_pygame.mixer.quit.assert_called()


class TestCreateNotifierFromConfig:
    """Tests for create_notifier_from_config function."""

    def test_create_notifier_from_config(self) -> None:
        """Test creating notifier from config."""
        config = NotificationsConfig(popup=False, sound=True, sound_file="custom.wav")
        notifier = create_notifier_from_config(config)
        assert notifier.popup_enabled is False
        # sound_enabled may be False if pygame can't initialize or sound file not found
        assert isinstance(notifier.sound_enabled, bool)
        assert notifier.sound_file == "custom.wav"

    def test_create_notifier_from_config_defaults(self) -> None:
        """Test creating notifier from config with defaults."""
        config = NotificationsConfig()
        notifier = create_notifier_from_config(config)
        # Note: actual enabled state depends on library availability
        # Just check that sound_file is set correctly
        assert notifier.sound_file == "notification.wav"
