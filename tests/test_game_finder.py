from unittest.mock import MagicMock
import pytest
from steam_monitor.game_finder import GameFinder


class TestGameFinder:
    """Tests for GameFinder class."""

    @pytest.fixture
    def temp_steamapps(self, tmp_path):
        """Create a temporary steamapps directory."""
        steamapps = tmp_path / "steamapps"
        steamapps.mkdir()
        return steamapps

    @pytest.fixture
    def mock_parser(self):
        """Create a mock LogParser."""
        parser = MagicMock()
        parser.parse_acf.return_value = {
            "appid": "12345",
            "name": "Test Game",
            "StateFlags": "256",
            "BytesDownloaded": "1000000",
            "BytesToDownload": "5000000",
        }
        parser.build_depot_app_mapping.return_value = {}
        parser.get_most_recent_active_download.return_value = None
        parser.get_recent_pause_info.return_value = None
        return parser

    def test_initialization(self, temp_steamapps, mock_parser):
        """Test GameFinder initialization."""
        finder = GameFinder(temp_steamapps, mock_parser)
        assert finder.steamapps == temp_steamapps
        assert finder.log_parser == mock_parser

    def test_find_active_game_from_logs(self, temp_steamapps, mock_parser):
        """Test finding active game using log data."""
        # Create ACF file
        acf_file = temp_steamapps / "appmanifest_12345.acf"
        acf_file.write_text('"AppState" { "appid" "12345" "name" "Test Game" }')

        # Mock parser to return app_id from logs
        mock_parser.get_most_recent_active_download.return_value = 12345
        mock_parser.parse_acf.return_value = {"appid": "12345", "name": "Test Game"}

        finder = GameFinder(temp_steamapps, mock_parser)
        game = finder.find_active_game()

        assert game is not None
        assert game.app_id == 12345
        assert game.name == "Test Game"
        assert game.path == acf_file

    def test_find_active_game_fallback_active(self, temp_steamapps, mock_parser):
        """Test fallback to ACF files when logs don't help."""
        # Create ACF file for downloading game
        acf_file = temp_steamapps / "appmanifest_12345.acf"
        acf_file.write_text('"AppState" { }')

        # Mock parser
        mock_parser.get_most_recent_active_download.return_value = None
        mock_parser.parse_acf.return_value = {
            "appid": "12345",
            "name": "Test Game",
            "StateFlags": "256",  # Downloading flag
            "BytesDownloaded": "1000000",
            "BytesToDownload": "5000000",
        }
        mock_parser.get_recent_pause_info.return_value = None

        finder = GameFinder(temp_steamapps, mock_parser)
        game = finder.find_active_game()

        assert game is not None
        assert game.app_id == 12345

    def test_find_active_game_fallback_paused(self, temp_steamapps, mock_parser):
        """Test fallback finds paused game when no active games."""
        # Create ACF file for paused game
        acf_file = temp_steamapps / "appmanifest_12345.acf"
        acf_file.write_text('"AppState" { }')

        # Mock parser
        mock_parser.get_most_recent_active_download.return_value = None
        mock_parser.parse_acf.return_value = {
            "appid": "12345",
            "name": "Test Game",
            "StateFlags": "512",  # Paused flag
            "BytesDownloaded": "1000000",
            "BytesToDownload": "5000000",
        }
        mock_parser.get_recent_pause_info.return_value = None

        finder = GameFinder(temp_steamapps, mock_parser)
        game = finder.find_active_game()

        assert game is not None
        assert game.app_id == 12345

    def test_find_active_game_no_games(self, temp_steamapps, mock_parser):
        """Test when no games are found."""
        mock_parser.get_most_recent_active_download.return_value = None

        finder = GameFinder(temp_steamapps, mock_parser)
        game = finder.find_active_game()

        assert game is None

    def test_find_active_game_multiple_active(self, temp_steamapps, mock_parser):
        """Test finding most recent when multiple games are active."""
        import time

        # Create multiple ACF files
        acf_file1 = temp_steamapps / "appmanifest_12345.acf"
        acf_file1.write_text('"AppState" { }')

        time.sleep(0.01)

        acf_file2 = temp_steamapps / "appmanifest_67890.acf"
        acf_file2.write_text('"AppState" { }')

        # Mock parser to return different data for each file
        def parse_acf_side_effect(path):
            if "12345" in str(path):
                return {
                    "appid": "12345",
                    "name": "Game 1",
                    "StateFlags": "256",
                    "BytesDownloaded": "1000000",
                    "BytesToDownload": "5000000",
                }
            else:
                return {
                    "appid": "67890",
                    "name": "Game 2",
                    "StateFlags": "256",
                    "BytesDownloaded": "2000000",
                    "BytesToDownload": "8000000",
                }

        mock_parser.get_most_recent_active_download.return_value = None
        mock_parser.parse_acf.side_effect = parse_acf_side_effect
        mock_parser.get_recent_pause_info.return_value = None

        finder = GameFinder(temp_steamapps, mock_parser)
        game = finder.find_active_game()

        # Should return most recently modified
        assert game is not None
        assert game.app_id == 67890

    def test_find_active_game_invalid_acf(self, temp_steamapps, mock_parser, caplog):
        """Test handling of invalid ACF files."""
        # Create invalid ACF file
        acf_file = temp_steamapps / "appmanifest_12345.acf"
        acf_file.write_text("invalid content")

        # Mock parser to raise exception
        mock_parser.get_most_recent_active_download.return_value = None
        mock_parser.parse_acf.side_effect = Exception("Parse error")

        finder = GameFinder(temp_steamapps, mock_parser)
        game = finder.find_active_game()

        assert game is None
        assert "Failed to parse ACF" in caplog.text

    def test_find_active_game_recently_paused(self, temp_steamapps, mock_parser):
        """Test detecting recently paused games."""
        from datetime import datetime

        acf_file = temp_steamapps / "appmanifest_12345.acf"
        acf_file.write_text('"AppState" { }')

        mock_parser.get_most_recent_active_download.return_value = None
        mock_parser.parse_acf.return_value = {
            "appid": "12345",
            "name": "Test Game",
            "StateFlags": "4",  # Not paused by flags
            "BytesDownloaded": "1000000",
            "BytesToDownload": "5000000",
        }
        # But recent pause in logs
        mock_parser.get_recent_pause_info.return_value = (datetime.now(), "paused")

        finder = GameFinder(temp_steamapps, mock_parser)
        game = finder.find_active_game()

        assert game is not None
        assert game.app_id == 12345

    def test_find_active_game_completed_download(self, temp_steamapps, mock_parser):
        """Test skipping games where download is complete."""
        acf_file = temp_steamapps / "appmanifest_12345.acf"
        acf_file.write_text('"AppState" { }')

        mock_parser.get_most_recent_active_download.return_value = None
        mock_parser.parse_acf.return_value = {
            "appid": "12345",
            "name": "Test Game",
            "StateFlags": "256",
            "BytesDownloaded": "5000000",  # Same as BytesToDownload
            "BytesToDownload": "5000000",
        }
        mock_parser.get_recent_pause_info.return_value = None

        finder = GameFinder(temp_steamapps, mock_parser)
        game = finder.find_active_game()

        # Should not return completed game
        assert game is None

    def test_find_active_game_zero_app_id(self, temp_steamapps, mock_parser):
        """Test skipping ACF files with invalid app_id."""
        acf_file = temp_steamapps / "appmanifest_0.acf"
        acf_file.write_text('"AppState" { }')

        mock_parser.get_most_recent_active_download.return_value = None
        mock_parser.parse_acf.return_value = {
            "appid": "0",
            "name": "Invalid",
            "StateFlags": "256",
        }

        finder = GameFinder(temp_steamapps, mock_parser)
        game = finder.find_active_game()

        assert game is None

    def test_find_active_game_prefers_logs_over_fallback(
        self, temp_steamapps, mock_parser
    ):
        """Test that log-based detection is preferred over fallback."""
        # Create two ACF files
        acf_file1 = temp_steamapps / "appmanifest_12345.acf"
        acf_file1.write_text('"AppState" { }')

        acf_file2 = temp_steamapps / "appmanifest_67890.acf"
        acf_file2.write_text('"AppState" { }')

        # Mock parser to return app_id from logs
        mock_parser.get_most_recent_active_download.return_value = 67890

        def parse_acf_side_effect(path):
            if "12345" in str(path):
                return {"appid": "12345", "name": "Game 1"}
            else:
                return {"appid": "67890", "name": "Game 2"}

        mock_parser.parse_acf.side_effect = parse_acf_side_effect

        finder = GameFinder(temp_steamapps, mock_parser)
        game = finder.find_active_game()

        # Should return the one from logs (67890), not fallback
        assert game is not None
        assert game.app_id == 67890
