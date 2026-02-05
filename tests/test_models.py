import pytest
from pathlib import Path
from steam_monitor.models import (
    SteamInstall,
    DownloadingGame,
    Throughput,
    DownloadState,
    DownloadSample,
)


class TestSteamInstall:
    """Tests for SteamInstall dataclass."""

    def test_creation(self):
        """Test SteamInstall creation."""
        root = Path("/steam")
        steamapps = Path("/steam/steamapps")
        logs = Path("/steam/logs")
        install = SteamInstall(root=root, steamapps=steamapps, logs=logs)
        assert install.root == root
        assert install.steamapps == steamapps
        assert install.logs == logs

    def test_frozen(self):
        """Test that SteamInstall is immutable."""
        install = SteamInstall(
            root=Path("/steam"),
            steamapps=Path("/steam/steamapps"),
            logs=Path("/steam/logs"),
        )
        with pytest.raises(AttributeError):
            install.root = Path("/other")


class TestDownloadingGame:
    """Tests for DownloadingGame dataclass."""

    def test_creation(self):
        """Test DownloadingGame creation."""
        game = DownloadingGame(
            app_id=12345,
            name="Test Game",
            path=Path("/steam/steamapps/appmanifest_12345.acf"),
        )
        assert game.app_id == 12345
        assert game.name == "Test Game"
        assert game.path == Path("/steam/steamapps/appmanifest_12345.acf")

    def test_frozen(self):
        """Test that DownloadingGame is immutable."""
        game = DownloadingGame(app_id=12345, name="Test Game", path=Path("/test"))
        with pytest.raises(AttributeError):
            game.app_id = 67890


class TestThroughput:
    """Tests for Throughput dataclass."""

    def test_bytes_per_sec(self):
        """Test bytes_per_sec storage."""
        throughput = Throughput(bytes_per_sec=1_000_000)
        assert throughput.bytes_per_sec == 1_000_000

    def test_mbps_conversion(self):
        """Test conversion to Mbps (megabits per second)."""
        throughput = Throughput(bytes_per_sec=1_000_000)
        assert throughput.mbps == 8.0

    def test_mb_per_sec_conversion(self):
        """Test conversion to MB/s (megabytes per second)."""
        throughput = Throughput(bytes_per_sec=1_000_000)
        assert throughput.mb_per_sec == 1.0

    def test_zero_throughput(self):
        """Test zero throughput."""
        throughput = Throughput(bytes_per_sec=0)
        assert throughput.mbps == 0
        assert throughput.mb_per_sec == 0

    def test_high_throughput(self):
        """Test high throughput values."""
        throughput = Throughput(bytes_per_sec=125_000_000)  # 125 MB/s
        assert throughput.mbps == 1000.0  # 1 Gbps
        assert throughput.mb_per_sec == 125.0

    def test_frozen(self):
        """Test that Throughput is immutable."""
        throughput = Throughput(bytes_per_sec=1000)
        with pytest.raises(AttributeError):
            throughput.bytes_per_sec = 2000


class TestDownloadState:
    """Tests for DownloadState enum."""

    def test_all_states(self):
        """Test all download states exist."""
        assert DownloadState.DOWNLOADING.value == "downloading"
        assert DownloadState.PAUSED.value == "paused"
        assert DownloadState.UNPACKING.value == "unpacking"
        assert DownloadState.IDLE.value == "idle"

    def test_enum_comparison(self):
        """Test enum comparison."""
        assert DownloadState.DOWNLOADING == DownloadState.DOWNLOADING
        assert DownloadState.DOWNLOADING != DownloadState.PAUSED


class TestDownloadSample:
    """Tests for DownloadSample dataclass."""

    def test_creation_without_game(self):
        """Test DownloadSample creation without game."""
        sample = DownloadSample(
            timestamp=1234567890.0,
            speed_bytes_per_sec=100000.0,
            status="downloading",
        )
        assert sample.timestamp == 1234567890.0
        assert sample.speed_bytes_per_sec == 100000.0
        assert sample.status == "downloading"
        assert sample.game is None

    def test_creation_with_game(self):
        """Test DownloadSample creation with game."""
        game = DownloadingGame(app_id=12345, name="Test Game", path=Path("/test"))
        sample = DownloadSample(
            timestamp=1234567890.0,
            speed_bytes_per_sec=100000.0,
            status="downloading",
            game=game,
        )
        assert sample.game == game
        assert sample.game.app_id == 12345

    def test_mutable(self):
        """Test that DownloadSample is mutable (not frozen)."""
        sample = DownloadSample(
            timestamp=1234567890.0,
            speed_bytes_per_sec=100000.0,
            status="downloading",
        )
        # Should be able to modify
        sample.speed_bytes_per_sec = 2000000
        assert sample.speed_bytes_per_sec == 2000000
