import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from steam_monitor.monitor import SteamMonitor, LogHandler
from steam_monitor.models import (
    SteamInstall,
    DownloadingGame,
    DownloadState,
    Throughput,
)
from datetime import datetime


class TestLogHandler:
    """Tests for LogHandler class."""

    def test_initialization(self):
        """Test LogHandler initialization."""
        mock_parser = MagicMock()
        handler = LogHandler(mock_parser)
        assert handler.log_parser == mock_parser

    def test_on_modified_updates_log_state(self):
        """Test that on_modified calls _update_log_state."""
        mock_parser = MagicMock()
        mock_parser.log_file = Path("/tmp/content_log.txt")
        handler = LogHandler(mock_parser)

        # Create mock event
        event = MagicMock()
        event.src_path = str(mock_parser.log_file)

        handler.on_modified(event)

        mock_parser._update_log_state.assert_called_once()

    def test_on_modified_ignores_other_files(self):
        """Test that on_modified ignores events for other files."""
        mock_parser = MagicMock()
        mock_parser.log_file = Path("/tmp/content_log.txt")
        handler = LogHandler(mock_parser)

        # Create mock event for different file
        event = MagicMock()
        event.src_path = "/tmp/other_file.txt"

        handler.on_modified(event)

        mock_parser._update_log_state.assert_not_called()

    def test_on_modified_handles_exceptions(self, caplog):
        """Test that on_modified handles exceptions gracefully."""
        mock_parser = MagicMock()
        mock_parser.log_file = Path("/tmp/content_log.txt")
        mock_parser._update_log_state.side_effect = Exception("Update failed")
        handler = LogHandler(mock_parser)

        event = MagicMock()
        event.src_path = str(mock_parser.log_file)

        # Should not raise
        handler.on_modified(event)

        assert "Error updating log state" in caplog.text


class TestSteamMonitor:
    """Tests for SteamMonitor class."""

    @pytest.fixture
    def mock_steam_install(self):
        """Create a mock SteamInstall."""
        return SteamInstall(
            root=Path("/steam"),
            steamapps=Path("/steam/steamapps"),
            logs=Path("/steam/logs"),
        )

    @pytest.fixture
    def mock_parser(self):
        """Create a mock LogParser."""
        parser = MagicMock()
        parser.log_file = Path("/steam/logs/content_log.txt")
        parser.read_latest_speed.return_value = None
        parser.parse_acf.return_value = {
            "appid": "12345",
            "name": "Test Game",
            "StateFlags": "256",
        }
        parser.get_status.return_value = DownloadState.DOWNLOADING
        return parser

    @pytest.fixture
    def mock_game_finder(self):
        """Create a mock GameFinder."""
        finder = MagicMock()
        finder.find_active_game.return_value = None
        return finder

    @patch("steam_monitor.monitor.Observer")
    def test_initialization(
        self, mock_observer, mock_steam_install, mock_parser, mock_game_finder
    ):
        """Test SteamMonitor initialization."""
        monitor = SteamMonitor(mock_steam_install, mock_parser, mock_game_finder)

        assert monitor.steam == mock_steam_install
        assert monitor.log_parser == mock_parser
        assert monitor.game_finder == mock_game_finder
        assert monitor.observer is not None
        # Observer should NOT be started in __init__ - only in __enter__
        mock_observer.return_value.start.assert_not_called()

    @patch("steam_monitor.monitor.Observer")
    def test_cleanup(
        self, mock_observer, mock_steam_install, mock_parser, mock_game_finder
    ):
        """Test SteamMonitor cleanup via context manager."""
        monitor = SteamMonitor(mock_steam_install, mock_parser, mock_game_finder)
        mock_obs = mock_observer.return_value

        # Use context manager to trigger cleanup
        with monitor:
            pass

        mock_obs.stop.assert_called_once()
        mock_obs.join.assert_called_once()

    @patch("steam_monitor.monitor.Observer")
    def test_get_current_sample_no_active_game(
        self, mock_observer, mock_steam_install, mock_parser, mock_game_finder
    ):
        """Test getting sample when no game is active."""
        mock_game_finder.find_active_game.return_value = None

        monitor = SteamMonitor(mock_steam_install, mock_parser, mock_game_finder)
        sample = monitor.get_current_sample()

        assert sample.speed_bytes_per_sec == 0.0
        assert sample.status == DownloadState.IDLE.value
        assert sample.game is None

    @patch("steam_monitor.monitor.Observer")
    @patch("time.time", return_value=1234567890.0)
    def test_get_current_sample_with_game_downloading(
        self,
        mock_time,
        mock_observer,
        mock_steam_install,
        mock_parser,
        mock_game_finder,
    ):
        """Test getting sample when game is downloading."""
        game = DownloadingGame(
            app_id=12345,
            name="Test Game",
            path=Path("/steam/steamapps/appmanifest_12345.acf"),
        )
        mock_game_finder.find_active_game.return_value = game

        mock_parser.read_latest_speed.return_value = (
            datetime.now(),
            Throughput(bytes_per_sec=10_000_000.0),
        )
        mock_parser.parse_acf.return_value = {
            "StateFlags": "256",
        }
        mock_parser.get_status.return_value = DownloadState.DOWNLOADING

        monitor = SteamMonitor(mock_steam_install, mock_parser, mock_game_finder)
        sample = monitor.get_current_sample()

        assert sample.timestamp == 1234567890.0
        assert sample.speed_bytes_per_sec == 10_000_000.0
        assert sample.status == DownloadState.DOWNLOADING.value
        assert sample.game == game

    @patch("steam_monitor.monitor.Observer")
    def test_get_current_sample_with_game_paused(
        self, mock_observer, mock_steam_install, mock_parser, mock_game_finder
    ):
        """Test getting sample when game is paused."""
        game = DownloadingGame(
            app_id=12345,
            name="Test Game",
            path=Path("/steam/steamapps/appmanifest_12345.acf"),
        )
        mock_game_finder.find_active_game.return_value = game

        mock_parser.read_latest_speed.return_value = None
        mock_parser.parse_acf.return_value = {
            "StateFlags": "512",
        }
        mock_parser.get_status.return_value = DownloadState.PAUSED

        monitor = SteamMonitor(mock_steam_install, mock_parser, mock_game_finder)
        sample = monitor.get_current_sample()

        assert sample.speed_bytes_per_sec == 0.0
        assert sample.status == DownloadState.PAUSED.value

    @patch("steam_monitor.monitor.Observer")
    def test_get_current_sample_speed_zero_when_not_downloading(
        self, mock_observer, mock_steam_install, mock_parser, mock_game_finder
    ):
        """Test that speed is set to 0 when status is not downloading."""
        game = DownloadingGame(
            app_id=12345,
            name="Test Game",
            path=Path("/steam/steamapps/appmanifest_12345.acf"),
        )
        mock_game_finder.find_active_game.return_value = game

        # Clear any existing speed cache
        mock_parser.read_latest_speed.return_value = None

        mock_parser.parse_acf.return_value = {
            "BytesDownloaded": "5000000",
            "StateFlags": "512",  # PAUSED state
        }
        mock_parser.get_status.return_value = DownloadState.PAUSED

        monitor = SteamMonitor(mock_steam_install, mock_parser, mock_game_finder)
        sample = monitor.get_current_sample()

        # Speed should be 0 since no recent speed entry and status is paused
        assert sample.speed_bytes_per_sec == 0.0

    @patch("steam_monitor.monitor.Observer")
    def test_get_current_sample_acf_parse_error(
        self, mock_observer, mock_steam_install, mock_parser, mock_game_finder, caplog
    ):
        """Test handling of ACF parse errors."""
        game = DownloadingGame(
            app_id=12345,
            name="Test Game",
            path=Path("/steam/steamapps/appmanifest_12345.acf"),
        )
        mock_game_finder.find_active_game.return_value = game
        mock_parser.parse_acf.side_effect = Exception("Parse error")

        monitor = SteamMonitor(mock_steam_install, mock_parser, mock_game_finder)
        sample = monitor.get_current_sample()

        assert sample.status == DownloadState.IDLE.value
        assert "Error processing sample" in caplog.text
