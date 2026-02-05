from dataclasses import dataclass
from typing import Optional
import argparse


@dataclass(frozen=True)
class Config:
    interval: int = 60
    samples: int = 6
    log_file: Optional[str] = None
    daemon: bool = False
    steam_path: Optional[str] = None

    @classmethod
    def from_cli(cls) -> "Config":
        """Parses config from CLI with defaults."""
        parser = argparse.ArgumentParser(description="Steam Download Monitor")
        parser.add_argument(
            "--interval",
            type=int,
            default=cls.interval,
            help="Interval in seconds between samples (default: 60)",
        )
        parser.add_argument(
            "--samples",
            type=int,
            default=cls.samples,
            help="Number of samples to take (default: 5; 0 for infinite in daemon mode)",
        )
        parser.add_argument(
            "--log-file",
            type=str,
            default=cls.log_file,
            help="Log file path (default: stdout)",
        )
        parser.add_argument(
            "--daemon",
            action="store_true",
            help="Run indefinitely as a background process",
        )
        parser.add_argument(
            "--steam-path",
            type=str,
            default=cls.steam_path,
            help="Custom Steam installation path (overrides auto-detection)",
        )
        args = parser.parse_args()
        return cls(
            interval=args.interval,
            samples=args.samples if not args.daemon else 0,
            log_file=args.log_file,
            daemon=args.daemon,
            steam_path=args.steam_path,
        )
