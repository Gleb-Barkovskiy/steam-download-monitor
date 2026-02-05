from typing import Optional, List, Tuple
from pathlib import Path

from .errors import ACFParseError
from .models import DownloadingGame
from .parser import LogParser
import logging


class GameFinder:
    """Finds active downloading games using manifests and logs."""

    def __init__(self, steamapps: Path, log_parser: LogParser):
        self.steamapps = steamapps
        self.log_parser = log_parser

    def find_active_game(self) -> Optional[DownloadingGame]:
        """Finds the active game using logs or fallback."""
        # Get most recent active download directly from log parser
        active_app_id = self.log_parser.get_most_recent_active_download()

        if active_app_id:
            for acf_path in self.steamapps.glob("appmanifest_*.acf"):
                try:
                    data = self.log_parser.parse_acf(acf_path)
                    app_id = int(data.get("appid", "0"))
                    if app_id == active_app_id:
                        name = data.get("name", "Unknown")
                        return DownloadingGame(app_id, name, acf_path)
                except ACFParseError as e:
                    logging.warning(f"Skipping ACF due to parse error: {e}")
                    continue

        return self._find_active_game_fallback()

    def _find_active_game_fallback(self) -> Optional[DownloadingGame]:
        """Fallback using ACF files."""
        active_games: List[Tuple[float, DownloadingGame]] = []
        paused_games: List[Tuple[float, DownloadingGame]] = []

        for acf_path in self.steamapps.glob("appmanifest_*.acf"):
            try:
                data = self.log_parser.parse_acf(acf_path)
                app_id = int(data.get("appid", "0"))
                if app_id == 0:
                    continue

                name = data.get("name", "Unknown")
                flags = int(data.get("StateFlags", "4"))
                last_modified = acf_path.stat().st_mtime
                game = DownloadingGame(app_id, name, acf_path)

                is_recently_paused = (
                    self.log_parser.get_recent_pause_info(app_id) is not None
                )

                if is_recently_paused or flags & 512:
                    paused_games.append((last_modified, game))
                elif flags & (256 | 1024 | 1048576):
                    if "BytesToDownload" in data and "BytesDownloaded" in data:
                        bytes_to_dl = int(data["BytesToDownload"])
                        bytes_dl = int(data["BytesDownloaded"])
                        if bytes_to_dl > bytes_dl:
                            active_games.append((last_modified, game))
                else:
                    paused_games.append((last_modified, game))
            except Exception as e:
                logging.warning(f"Failed to parse ACF in fallback {acf_path}: {e}")
                continue

        if active_games:
            active_games.sort(key=lambda x: x[0], reverse=True)
            return active_games[0][1]
        elif paused_games:
            paused_games.sort(key=lambda x: x[0], reverse=True)
            return paused_games[0][1]

        return None
