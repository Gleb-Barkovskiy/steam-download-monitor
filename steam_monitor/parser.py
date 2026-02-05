import re
from pathlib import Path
from typing import Dict, Optional, Tuple, List
import datetime as dt
import time

from .errors import ACFParseError
from .models import Throughput, DownloadState, LogParserProtocol
import logging

_LINE_RE = re.compile(
    r"\[(?P<ts>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\]\s+(?:Current\s+)?Download rate:\s+([\d.]+)\s*(KB/s|MB/s|Mbps)",
    re.IGNORECASE,
)

PAUSE_PATTERNS = [
    r"(?P<ts>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\].*?AppID\s+(?P<app_id>\d+)\s+update\s+canceled",
    r"(?P<ts>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\].*?AppID\s+(?P<app_id>\d+)\s+App update changed.*?Suspended",
    r"(?P<ts>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\].*?AppID\s+(?P<app_id>\d+)\s+scheduler finished.*?Suspended",
    r"(?P<ts>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\].*?AppID\s+(?P<app_id>\d+)\s+App update changed.*?Stopping",
]

START_PATTERNS = [
    r"(?P<ts>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\].*?AppID\s+(?P<app_id>\d+)\s+update started",
    r"(?P<ts>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\].*?AppID\s+(?P<app_id>\d+)\s+App update changed.*?Running Update.*?Downloading",
    r"(?P<ts>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\].*?Downloading\s+\d+\s+chunks\s+from\s+depot\s+\d+.*?AppID\s+(?P<app_id>\d+)",
]

NETWORK_PATTERNS = [
    r"(?P<ts>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\].*?AppID\s+(?P<app_id>\d+)\s+Increasing target number of download connections",
    r"(?P<ts>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\].*?AppID\s+(?P<app_id>\d+)\s+Created download interface",
]

DEPOT_PATTERNS = [
    r"Downloading\s+\d+\s+chunks\s+from\s+depot\s+(?P<depot_id>\d+).*?AppID\s+(?P<app_id>\d+)",
]

MAX_AGE_SEC = 180
PRUNE_AGE_SEC = 3600


def _read_file_with_retry(
    path: Path, retries: int = 3, delay: float = 0.1
) -> Optional[str]:
    """Read file with retry logic for Windows file locking issues."""
    for attempt in range(retries):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except (PermissionError, OSError) as e:
            if attempt < retries - 1:
                time.sleep(delay)
                continue
            logging.warning(f"Failed to read {path} after {retries} attempts: {e}")
            return None
    return None


class LogParser(LogParserProtocol):
    """Parses Steam logs with stateful tailing and caching."""

    def __init__(self, logs_dir: Path):
        self.logs_dir = logs_dir
        self.log_file = logs_dir / "content_log.txt"
        self.last_pos = 0
        self.latest_rate: Optional[Tuple[dt.datetime, Throughput]] = None
        self.recent_events: Dict[int, List[Tuple[dt.datetime, str]]] = (
            {}
        )  # app_id -> [(ts, etype)]
        self.depot_to_app: Dict[str, str] = {}  # depot_id -> app_id
        self.rate_entries: List[Tuple[dt.datetime, int, str]] = (
            []
        )  # [(ts, app_id, rate_str)]

        if not self.log_file.exists():
            logging.warning(
                f"Log file not found: {self.log_file}. "
                "Monitoring will start when it appears."
            )

        self._update_log_state(full_load=True)

    def _update_log_state(self, full_load=False) -> None:
        """Updates internal state by tailing the log file incrementally."""
        if not self.log_file.exists():
            return

        try:
            with open(self.log_file, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(0, 2)
                current_size = f.tell()

                if current_size < self.last_pos:
                    full_load = True
                    self.last_pos = 0

                if full_load:
                    f.seek(0)
                    content = f.read()
                    self.last_pos = f.tell()
                    lines = content.splitlines()
                    self.latest_rate = None
                    self.recent_events = {}
                    self.depot_to_app = {}
                    self.rate_entries = []
                else:
                    f.seek(self.last_pos)
                    new_content = f.read()
                    self.last_pos = f.tell()
                    lines = new_content.splitlines()
                    if not lines:
                        return
        except (OSError, IOError) as e:
            logging.warning(f"Failed to read log file {self.log_file}: {e}")
            return

        now = dt.datetime.now()
        all_patterns = PAUSE_PATTERNS + START_PATTERNS + NETWORK_PATTERNS
        etypes = (
            ["pause"] * len(PAUSE_PATTERNS)
            + ["start"] * len(START_PATTERNS)
            + ["network"] * len(NETWORK_PATTERNS)
        )

        for line in lines:
            match = _LINE_RE.search(line)
            if match:
                ts_str = match.group("ts").strip()
                try:
                    ts = dt.datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                    if (now - ts).total_seconds() > MAX_AGE_SEC:
                        continue
                    value = float(match.group(2))
                    unit = match.group(3).lower()
                    if unit == "kb/s":
                        speed_bytes = value * 1024
                    elif unit == "mb/s":
                        speed_bytes = value * 1024 * 1024
                    elif unit == "mbps":
                        speed_bytes = value * 1_000_000 / 8
                    else:
                        continue
                    if self.latest_rate is None or ts > self.latest_rate[0]:
                        self.latest_rate = (ts, Throughput(speed_bytes))

                    app_id_matches = re.findall(r"AppID\s+(\d+)", line)
                    app_id = None
                    if app_id_matches:
                        app_id = int(app_id_matches[0])
                    else:
                        depot_matches = re.findall(r"depot\s+(\d+)", line)
                        if depot_matches:
                            depot_id = depot_matches[0]
                            if depot_id in self.depot_to_app:
                                app_id = int(self.depot_to_app[depot_id])
                    if app_id is not None:
                        self.rate_entries.append((ts, app_id, match.group(2)))
                except ValueError:
                    continue

            for pattern in DEPOT_PATTERNS:
                match = re.search(pattern, line)
                if match:
                    depot_id = match.group("depot_id")
                    app_id = match.group("app_id")
                    self.depot_to_app[depot_id] = app_id

            app_id_match = re.search(r"AppID\s+(\d+)", line)
            if app_id_match:
                app_id = int(app_id_match.group(1))
                self.recent_events.setdefault(app_id, [])
                ts_match = re.search(
                    r"(?P<ts>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})", line
                )
                if ts_match:
                    ts_str = ts_match.group("ts")
                    try:
                        ts = dt.datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                        if (now - ts).total_seconds() > PRUNE_AGE_SEC:
                            continue
                        for idx, pattern in enumerate(all_patterns):
                            if re.search(
                                pattern.replace("(?P<app_id>\\d+)", str(app_id)), line
                            ):
                                etype = etypes[idx]
                                self.recent_events[app_id].append((ts, etype))
                                break
                    except ValueError:
                        continue

        self.rate_entries = [
            e
            for e in self.rate_entries
            if (now - e[0]).total_seconds() <= PRUNE_AGE_SEC
        ]
        for app_id in list(self.recent_events):
            self.recent_events[app_id] = [
                e
                for e in self.recent_events[app_id]
                if (now - e[0]).total_seconds() <= PRUNE_AGE_SEC
            ]
            if not self.recent_events[app_id]:
                del self.recent_events[app_id]

    def parse_acf(self, path: Path) -> Dict[str, str]:
        """Parse ACF file with retry logic for Windows file locking."""
        data: Dict[str, str] = {}

        content = _read_file_with_retry(path)
        if content is None:
            raise ACFParseError(f"Cannot read ACF file {path} after retries")

        try:
            for match in re.finditer(r'"(\s*[^"]+\s*)"\s*"(\s*[^"]+\s*)"', content):
                key, value = match.groups()
                data[key.strip()] = value.strip()
        except Exception as e:
            raise ACFParseError(f"Failed to parse ACF {path}: {e}") from e

        return data

    def build_depot_app_mapping(self) -> Dict[str, str]:
        """Returns the cached depot-to-app mapping."""
        self._update_log_state()
        return self.depot_to_app.copy()

    def get_most_recent_active_download(self) -> Optional[int]:
        """Analyzes cached events and rates for most recent active download."""
        self._update_log_state()
        now = dt.datetime.now()

        rate_entries = sorted(self.rate_entries, key=lambda x: x[0], reverse=True)
        for ts, app_id, _ in rate_entries:
            if (now - ts).total_seconds() <= MAX_AGE_SEC:
                events = self.recent_events.get(app_id, [])
                all_events = sorted(events, key=lambda x: x[0])
                has_later_pause = False
                for event_ts, event_type in all_events:
                    if (
                        event_type == "pause"
                        and event_ts > ts
                        and (now - event_ts).total_seconds() <= MAX_AGE_SEC
                    ):
                        has_later_pause = True
                        break
                if not has_later_pause:
                    return app_id

        active_apps = []
        for app_id, events in self.recent_events.items():
            sorted_events = sorted(events, key=lambda x: x[0])
            if sorted_events:
                latest_event_time, latest_event_type = sorted_events[-1]
                if (
                    latest_event_type in ["start", "network"]
                    and (now - latest_event_time).total_seconds() <= MAX_AGE_SEC
                ):
                    has_later_pause = any(
                        event_type == "pause"
                        and event_time > latest_event_time
                        and (now - event_time).total_seconds() <= MAX_AGE_SEC
                        for event_time, event_type in sorted_events
                    )
                    if not has_later_pause:
                        active_apps.append((latest_event_time, app_id))
        if active_apps:
            active_apps.sort(key=lambda x: x[0], reverse=True)
            return active_apps[0][1]
        return None

    def get_recent_pause_info(self, app_id: int) -> Optional[Tuple[dt.datetime, str]]:
        """Gets recent pause info using cached events."""
        self._update_log_state()
        events = self.recent_events.get(app_id, [])
        if not events:
            return None
        events.sort(key=lambda x: x[0], reverse=True)
        latest_etype = events[0][1]
        if latest_etype == "pause":
            return events[0][0], "paused"
        return None

    def get_status(
        self, flags: int, data: Dict[str, str], speed: float, app_id: int
    ) -> DownloadState:
        """Determines download state."""
        pause_info = self.get_recent_pause_info(app_id)
        if pause_info:
            return DownloadState.PAUSED
        if flags & 512:
            return DownloadState.PAUSED
        if "BytesToDownload" not in data or "BytesDownloaded" not in data:
            return DownloadState.IDLE
        bytes_to_dl = int(data["BytesToDownload"])
        bytes_dl = int(data["BytesDownloaded"])
        if bytes_to_dl == bytes_dl:
            if flags & (2097152 | 4194304):
                return DownloadState.UNPACKING
            if speed > 0:
                return DownloadState.DOWNLOADING
            return DownloadState.IDLE
        if flags & (256 | 1024 | 1048576):
            return DownloadState.DOWNLOADING if speed > 0 else DownloadState.PAUSED
        return DownloadState.PAUSED

    def read_latest_speed(self) -> Optional[Tuple[dt.datetime, Throughput]]:
        """Reads latest speed from cached state, returns None if stale."""
        self._update_log_state()

        if self.latest_rate:
            age = (dt.datetime.now() - self.latest_rate[0]).total_seconds()
            if age <= MAX_AGE_SEC:
                return self.latest_rate

        return None
