import datetime as dt
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol, Dict, Optional


@dataclass(frozen=True)
class SteamInstall:
    root: Path
    steamapps: Path
    logs: Path


@dataclass(frozen=True)
class DownloadingGame:
    app_id: int
    name: str
    path: Path


@dataclass(frozen=True)
class Throughput:
    bytes_per_sec: float

    @property
    def mbps(self) -> float:
        return self.bytes_per_sec * 8 / 1_000_000

    @property
    def mb_per_sec(self) -> float:
        return self.bytes_per_sec / 1_000_000


class DownloadState(Enum):
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    UNPACKING = "unpacking"
    IDLE = "idle"


@dataclass
class DownloadSample:
    timestamp: float
    speed_bytes_per_sec: float
    status: str
    game: Optional[DownloadingGame] = None


class LogParserProtocol(Protocol):
    """Interface for log parsing to allow mocking/swapping implementations."""

    log_file: Path

    def parse_acf(self, path: Path) -> Dict[str, str]: ...

    def build_depot_app_mapping(self) -> Dict[str, str]: ...

    def get_most_recent_active_download(self) -> Optional[int]: ...

    def get_recent_pause_info(
        self, app_id: int
    ) -> Optional[tuple[dt.datetime, str]]: ...

    def read_latest_speed(self) -> Optional[tuple[dt.datetime, Throughput]]: ...

    def get_status(
        self, flags: int, data: Dict[str, str], speed: float, app_id: int
    ) -> DownloadState: ...
