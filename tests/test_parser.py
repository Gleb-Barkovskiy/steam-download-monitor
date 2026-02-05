import pytest
from datetime import datetime, timedelta
from steam_monitor.errors import ACFParseError
from steam_monitor.parser import LogParser
from steam_monitor.models import Throughput, DownloadState


class TestLogParser:
    """Tests for LogParser class."""

    @pytest.fixture
    def temp_logs_dir(self, tmp_path):
        """Create a temporary logs directory."""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        return logs_dir

    @pytest.fixture
    def log_file(self, temp_logs_dir):
        """Create a temporary content_log.txt file."""
        log_file = temp_logs_dir / "content_log.txt"
        log_file.touch()
        return log_file

    def test_initialization(self, temp_logs_dir):
        """Test LogParser initialization."""
        parser = LogParser(temp_logs_dir)
        assert parser.logs_dir == temp_logs_dir
        assert parser.log_file == temp_logs_dir / "content_log.txt"
        assert parser.last_pos == 0
        assert parser.latest_rate is None
        assert parser.recent_events == {}
        assert parser.depot_to_app == {}

    def test_parse_acf_valid(self, temp_logs_dir, tmp_path):
        """Test parsing a valid ACF file."""
        acf_file = tmp_path / "appmanifest_12345.acf"
        acf_content = """
"AppState"
{
    "appid"    "12345"
    "name"    "Test Game"
    "StateFlags"    "4"
    "BytesDownloaded"    "1000000"
    "BytesToDownload"    "5000000"
}
"""
        acf_file.write_text(acf_content)

        parser = LogParser(temp_logs_dir)
        data = parser.parse_acf(acf_file)

        assert data["appid"] == "12345"
        assert data["name"] == "Test Game"
        assert data["StateFlags"] == "4"
        assert data["BytesDownloaded"] == "1000000"
        assert data["BytesToDownload"] == "5000000"

    def test_parse_acf_missing_file(self, temp_logs_dir, tmp_path):
        """Test parsing a non-existent ACF file."""
        parser = LogParser(temp_logs_dir)
        acf_file = tmp_path / "nonexistent.acf"

        with pytest.raises(ACFParseError):
            parser.parse_acf(acf_file)

    def test_read_latest_speed_from_kb_s(self, log_file, temp_logs_dir):
        """Test reading speed in KB/s format."""
        now = datetime.now()
        log_content = f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Download rate: 1024.5 KB/s AppID 12345\n"
        log_file.write_text(log_content)

        parser = LogParser(temp_logs_dir)
        result = parser.read_latest_speed()

        assert result is not None
        timestamp, throughput = result
        assert isinstance(throughput, Throughput)
        # 1024.5 KB/s = 1024.5 * 1024 bytes/s
        assert abs(throughput.bytes_per_sec - (1024.5 * 1024)) < 1

    def test_read_latest_speed_from_mb_s(self, log_file, temp_logs_dir):
        """Test reading speed in MB/s format."""
        now = datetime.now()
        log_content = f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Download rate: 10.5 MB/s AppID 12345\n"
        log_file.write_text(log_content)

        parser = LogParser(temp_logs_dir)
        result = parser.read_latest_speed()

        assert result is not None
        timestamp, throughput = result
        # 10.5 MB/s = 10.5 * 1024 * 1024 bytes/s
        assert abs(throughput.bytes_per_sec - (10.5 * 1024 * 1024)) < 1

    def test_read_latest_speed_from_mbps(self, log_file, temp_logs_dir):
        """Test reading speed in Mbps format."""
        now = datetime.now()
        log_content = f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Download rate: 100.0 Mbps AppID 12345\n"
        log_file.write_text(log_content)

        parser = LogParser(temp_logs_dir)
        result = parser.read_latest_speed()

        assert result is not None
        timestamp, throughput = result
        # 100 Mbps = 100 * 1_000_000 / 8 bytes/s
        assert abs(throughput.bytes_per_sec - (100 * 1_000_000 / 8)) < 1

    def test_read_latest_speed_old_entry(self, log_file, temp_logs_dir):
        """Test that old speed entries are ignored."""
        old_time = datetime.now() - timedelta(seconds=200)
        log_content = f"[{old_time.strftime('%Y-%m-%d %H:%M:%S')}] Download rate: 10.0 MB/s AppID 12345\n"
        log_file.write_text(log_content)

        parser = LogParser(temp_logs_dir)
        result = parser.read_latest_speed()

        assert result is None

    def test_read_latest_speed_no_log(self, temp_logs_dir):
        """Test reading speed when log file doesn't exist."""
        parser = LogParser(temp_logs_dir)
        result = parser.read_latest_speed()
        assert result is None

    def test_build_depot_app_mapping(self, log_file, temp_logs_dir):
        """Test building depot to app ID mapping."""
        now = datetime.now()
        log_content = f"""[{now.strftime('%Y-%m-%d %H:%M:%S')}] Downloading 50 chunks from depot 12346 AppID 12345
[{now.strftime('%Y-%m-%d %H:%M:%S')}] Downloading 30 chunks from depot 12347 AppID 12345
"""
        log_file.write_text(log_content)

        parser = LogParser(temp_logs_dir)
        mapping = parser.build_depot_app_mapping()

        assert mapping["12346"] == "12345"
        assert mapping["12347"] == "12345"

    def test_get_recent_pause_info_paused(self, log_file, temp_logs_dir):
        """Test detecting recent pause event."""
        now = datetime.now()
        log_content = (
            f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] AppID 12345 update canceled\n"
        )
        log_file.write_text(log_content)

        parser = LogParser(temp_logs_dir)
        result = parser.get_recent_pause_info(12345)

        assert result is not None
        timestamp, status = result
        assert status == "paused"

    def test_get_recent_pause_info_not_paused(self, log_file, temp_logs_dir):
        """Test when app is not paused."""
        now = datetime.now()
        log_content = (
            f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] AppID 12345 update started\n"
        )
        log_file.write_text(log_content)

        parser = LogParser(temp_logs_dir)
        result = parser.get_recent_pause_info(12345)

        assert result is None

    def test_get_status_downloading(self, temp_logs_dir):
        """Test status detection for downloading state."""
        parser = LogParser(temp_logs_dir)
        data = {"BytesToDownload": "5000000", "BytesDownloaded": "1000000"}
        flags = 256  # Download flag

        status = parser.get_status(flags, data, speed=100000.0, app_id=12345)
        assert status == DownloadState.DOWNLOADING

    def test_get_status_paused(self, temp_logs_dir):
        """Test status detection for paused state."""
        parser = LogParser(temp_logs_dir)
        data = {"BytesToDownload": "5000000", "BytesDownloaded": "1000000"}
        flags = 512  # Paused flag

        status = parser.get_status(flags, data, speed=0.0, app_id=12345)
        assert status == DownloadState.PAUSED

    def test_get_status_unpacking(self, temp_logs_dir):
        """Test status detection for unpacking state."""
        parser = LogParser(temp_logs_dir)
        data = {"BytesToDownload": "5000000", "BytesDownloaded": "5000000"}
        flags = 2097152  # Unpacking flag

        status = parser.get_status(flags, data, speed=0.0, app_id=12345)
        assert status == DownloadState.UNPACKING

    def test_get_status_idle(self, temp_logs_dir):
        """Test status detection for idle state."""
        parser = LogParser(temp_logs_dir)
        data = {"BytesToDownload": "5000000", "BytesDownloaded": "5000000"}
        flags = 4  # Installed flag

        status = parser.get_status(flags, data, speed=0.0, app_id=12345)
        assert status == DownloadState.IDLE

    def test_get_status_paused_no_speed(self, temp_logs_dir):
        """Test status detection for paused state when speed is 0."""
        parser = LogParser(temp_logs_dir)
        data = {"BytesToDownload": "5000000", "BytesDownloaded": "1000000"}
        flags = 256  # Download flag but no speed

        status = parser.get_status(flags, data, speed=0.0, app_id=12345)
        assert status == DownloadState.PAUSED

    def test_get_most_recent_active_download_with_rate(self, log_file, temp_logs_dir):
        """Test finding active download based on recent rate entry."""
        now = datetime.now()
        log_content = f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Download rate: 10.0 MB/s AppID 12345\n"
        log_file.write_text(log_content)

        parser = LogParser(temp_logs_dir)
        result = parser.get_most_recent_active_download()

        assert result == 12345

    def test_get_most_recent_active_download_with_start_event(
        self, log_file, temp_logs_dir
    ):
        """Test finding active download based on start event."""
        now = datetime.now()
        log_content = (
            f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] AppID 12345 update started\n"
        )
        log_file.write_text(log_content)

        parser = LogParser(temp_logs_dir)
        result = parser.get_most_recent_active_download()

        assert result == 12345

    def test_get_most_recent_active_download_paused_after_rate(
        self, log_file, temp_logs_dir
    ):
        """Test that pause after rate entry is detected."""
        now = datetime.now()
        rate_time = now - timedelta(seconds=30)
        pause_time = now - timedelta(seconds=10)
        log_content = f"""[{rate_time.strftime('%Y-%m-%d %H:%M:%S')}] Download rate: 10.0 MB/s AppID 12345
[{pause_time.strftime('%Y-%m-%d %H:%M:%S')}] AppID 12345 update canceled
"""
        log_file.write_text(log_content)

        parser = LogParser(temp_logs_dir)
        result = parser.get_most_recent_active_download()

        assert result is None

    def test_log_file_truncation(self, log_file, temp_logs_dir):
        """Test handling of log file truncation."""
        now = datetime.now()
        initial_content = (
            f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Download rate: 5.0 MB/s AppID 12345\n"
            * 100
        )
        log_file.write_text(initial_content)

        parser = LogParser(temp_logs_dir)
        assert parser.last_pos > 0

        # Truncate log file
        log_file.write_text(
            f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Download rate: 3.0 MB/s AppID 12345\n"
        )

        parser._update_log_state()
        result = parser.read_latest_speed()
        assert result is not None
        # Parser interprets "MB/s" as MiB/s (1024-based), so 3.0 MB/s = 3.0 * 1024 * 1024 bytes/s
        expected_mb = 3.0
        assert abs(result[1].bytes_per_sec - (expected_mb * 1024 * 1024)) < 1000
