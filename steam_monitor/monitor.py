import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from .models import SteamInstall, DownloadSample, DownloadState, LogParserProtocol
from .game_finder import GameFinder
import logging


class LogHandler(FileSystemEventHandler):
    def __init__(self, log_parser: LogParserProtocol):
        self.log_parser = log_parser

    def on_modified(self, event):
        if event.src_path == str(self.log_parser.log_file):
            try:
                self.log_parser._update_log_state()
            except Exception as e:
                logging.warning(f"Error updating log state on file modify: {e}")


class SteamMonitor:
    """Monitors Steam downloads with injected dependencies and event-driven updates."""

    def __init__(
        self,
        steam: SteamInstall,
        log_parser: LogParserProtocol,
        game_finder: GameFinder,
    ):
        self.steam = steam
        self.log_parser = log_parser
        self.game_finder = game_finder
        self.observer = Observer()
        self.observer.schedule(LogHandler(log_parser), str(steam.logs), recursive=False)
        self._started = False

    def __enter__(self):
        if not self._started:
            self.observer.start()
            self._started = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._started:
            self.observer.stop()
            self.observer.join(timeout=2.0)
            self._started = False

    def get_current_sample(self) -> DownloadSample:
        game = self.game_finder.find_active_game()
        timestamp = time.time()
        speed_entry = self.log_parser.read_latest_speed()
        speed_bytes_per_sec = speed_entry[1].bytes_per_sec if speed_entry else 0.0

        if not game:
            return DownloadSample(
                timestamp=timestamp,
                speed_bytes_per_sec=0.0,
                status=DownloadState.IDLE.value,
            )

        try:
            data = self.log_parser.parse_acf(game.path)
            flags = int(data.get("StateFlags", "4"))
            status = self.log_parser.get_status(
                flags, data, speed_bytes_per_sec, game.app_id
            )
        except Exception as e:
            logging.warning(f"Error processing sample for game {game.app_id}: {e}")
            status = DownloadState.IDLE

        return DownloadSample(
            timestamp=timestamp,
            speed_bytes_per_sec=speed_bytes_per_sec,
            status=status.value,
            game=game,
        )
