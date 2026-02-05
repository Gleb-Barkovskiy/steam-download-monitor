from steam_monitor.container import Container
from steam_monitor.finder import SteamFinder
from steam_monitor.parser import LogParser
from steam_monitor.game_finder import GameFinder
from steam_monitor.monitor import SteamMonitor
from steam_monitor.models import SteamInstall


class TestContainer:
    """Tests for dependency injection container."""

    def test_steam_finder(self):
        """Test that container creates SteamFinder."""
        container = Container()
        finder = container.steam_finder()
        assert isinstance(finder, SteamFinder)

    def test_log_parser(self, tmp_path):
        """Test that container creates LogParser."""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        container = Container()
        parser = container.log_parser(logs_dir)

        assert isinstance(parser, LogParser)
        assert parser.logs_dir == logs_dir

    def test_game_finder(self, tmp_path):
        """Test that container creates GameFinder."""
        steamapps = tmp_path / "steamapps"
        steamapps.mkdir()
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        container = Container()
        parser = container.log_parser(logs_dir)
        game_finder = container.game_finder(steamapps, parser)

        assert isinstance(game_finder, GameFinder)
        assert game_finder.steamapps == steamapps
        assert game_finder.log_parser == parser

    def test_steam_monitor(self, tmp_path):
        """Test that container creates SteamMonitor."""
        steamapps = tmp_path / "steamapps"
        steamapps.mkdir()
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        steam = SteamInstall(root=tmp_path, steamapps=steamapps, logs=logs_dir)

        container = Container()
        parser = container.log_parser(logs_dir)
        game_finder = container.game_finder(steamapps, parser)
        monitor = container.steam_monitor(steam, parser, game_finder)

        assert isinstance(monitor, SteamMonitor)
        assert monitor.steam == steam
        assert monitor.log_parser == parser
        assert monitor.game_finder == game_finder

    def test_container_creates_independent_instances(self, tmp_path):
        """Test that container creates independent instances."""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        container = Container()

        parser1 = container.log_parser(logs_dir)
        parser2 = container.log_parser(logs_dir)

        # Should be different instances
        assert parser1 is not parser2

    def test_full_dependency_chain(self, tmp_path):
        """Test creating full dependency chain through container."""
        steamapps = tmp_path / "steamapps"
        steamapps.mkdir()
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        steam = SteamInstall(root=tmp_path, steamapps=steamapps, logs=logs_dir)

        container = Container()

        # Create all dependencies
        finder = container.steam_finder()
        parser = container.log_parser(logs_dir)
        game_finder = container.game_finder(steamapps, parser)
        monitor = container.steam_monitor(steam, parser, game_finder)

        # Verify all are created and connected
        assert isinstance(finder, SteamFinder)
        assert isinstance(parser, LogParser)
        assert isinstance(game_finder, GameFinder)
        assert isinstance(monitor, SteamMonitor)

        assert monitor.log_parser == parser
        assert monitor.game_finder == game_finder
        assert game_finder.log_parser == parser
