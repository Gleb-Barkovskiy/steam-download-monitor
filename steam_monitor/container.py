from pathlib import Path
from .finder import SteamFinder
from .models import SteamInstall
from .parser import LogParser
from .game_finder import GameFinder
from .monitor import SteamMonitor


class Container:
    """Provider container for dependencies."""

    def steam_finder(self) -> SteamFinder:
        return SteamFinder()

    def log_parser(self, logs_dir: Path) -> LogParser:
        return LogParser(logs_dir)

    def game_finder(self, steamapps: Path, log_parser: LogParser) -> GameFinder:
        return GameFinder(steamapps, log_parser)

    def steam_monitor(
        self, steam: SteamInstall, log_parser: LogParser, game_finder: GameFinder
    ) -> SteamMonitor:
        return SteamMonitor(steam, log_parser, game_finder)
