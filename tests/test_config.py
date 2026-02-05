import pytest
from unittest.mock import patch
from steam_monitor.config import Config


class TestConfig:
    """Tests for Config dataclass and CLI parsing."""

    def test_default_values(self):
        """Test that Config has correct default values."""
        config = Config()
        assert config.interval == 60
        assert config.samples == 6
        assert config.log_file is None
        assert config.daemon is False
        assert config.steam_path is None

    def test_custom_values(self):
        """Test Config with custom values."""
        config = Config(
            interval=30,
            samples=10,
            log_file="/tmp/test.log",
            daemon=True,
            steam_path="/custom/steam",
        )
        assert config.interval == 30
        assert config.samples == 10
        assert config.log_file == "/tmp/test.log"
        assert config.daemon is True
        assert config.steam_path == "/custom/steam"

    def test_frozen_dataclass(self):
        """Test that Config is immutable (frozen)."""
        config = Config()
        with pytest.raises(AttributeError):
            config.interval = 100

    @patch("sys.argv", ["steam-monitor"])
    def test_from_cli_defaults(self):
        """Test CLI parsing with default arguments."""
        config = Config.from_cli()
        assert config.interval == 60
        assert config.samples == 6
        assert config.log_file is None
        assert config.daemon is False
        assert config.steam_path is None

    @patch("sys.argv", ["steam-monitor", "--interval", "30"])
    def test_from_cli_interval(self):
        """Test CLI parsing with custom interval."""
        config = Config.from_cli()
        assert config.interval == 30

    @patch("sys.argv", ["steam-monitor", "--samples", "10"])
    def test_from_cli_samples(self):
        """Test CLI parsing with custom samples."""
        config = Config.from_cli()
        assert config.samples == 10

    @patch("sys.argv", ["steam-monitor", "--log-file", "/tmp/test.log"])
    def test_from_cli_log_file(self):
        """Test CLI parsing with log file."""
        config = Config.from_cli()
        assert config.log_file == "/tmp/test.log"

    @patch("sys.argv", ["steam-monitor", "--daemon"])
    def test_from_cli_daemon_mode(self):
        """Test CLI parsing in daemon mode sets samples to 0."""
        config = Config.from_cli()
        assert config.daemon is True
        assert config.samples == 0

    @patch("sys.argv", ["steam-monitor", "--daemon", "--samples", "10"])
    def test_from_cli_daemon_overrides_samples(self):
        """Test that daemon mode overrides samples to 0."""
        config = Config.from_cli()
        assert config.daemon is True
        assert config.samples == 0

    @patch("sys.argv", ["steam-monitor", "--steam-path", "/custom/steam"])
    def test_from_cli_steam_path(self):
        """Test CLI parsing with custom Steam path."""
        config = Config.from_cli()
        assert config.steam_path == "/custom/steam"

    @patch(
        "sys.argv",
        [
            "steam-monitor",
            "--interval",
            "15",
            "--samples",
            "20",
            "--log-file",
            "/var/log/steam.log",
            "--daemon",
            "--steam-path",
            "/opt/steam",
        ],
    )
    def test_from_cli_all_arguments(self):
        """Test CLI parsing with all arguments."""
        config = Config.from_cli()
        assert config.interval == 15
        assert config.samples == 0  # Overridden by daemon
        assert config.log_file == "/var/log/steam.log"
        assert config.daemon is True
        assert config.steam_path == "/opt/steam"
