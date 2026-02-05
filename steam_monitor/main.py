import logging
import sys
import time
import signal
from typing import Optional
from .config import Config
from .container import Container
from .errors import SteamNotFoundError
from .models import DownloadState
import logging.handlers


def setup_logging(log_file: Optional[str]) -> None:
    level = logging.INFO
    format_str = "%(asctime)s - %(levelname)s - %(message)s"
    if log_file:
        handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=5
        )
        logging.basicConfig(
            handlers=[handler], level=level, format=format_str, force=True
        )
    else:
        logging.basicConfig(
            stream=sys.stdout, level=level, format=format_str, force=True
        )


def main() -> None:
    config = Config.from_cli()
    setup_logging(config.log_file)

    def shutdown_handler(signum: int, frame) -> None:
        logging.info("Shutting down gracefully...")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)

    if sys.platform == "win32":
        try:
            signal.signal(signal.SIGBREAK, shutdown_handler)
        except ValueError:
            pass

    try:
        container = Container()
        finder = container.steam_finder()
        steam = finder.find(config.steam_path)
        log_parser = container.log_parser(steam.logs)
        game_finder = container.game_finder(steam.steamapps, log_parser)

        with container.steam_monitor(steam, log_parser, game_finder) as monitor:
            i = 0
            while config.samples == 0 or i < config.samples:
                try:
                    sample = monitor.get_current_sample()
                    speed_display = sample.speed_bytes_per_sec

                    if sample.status == DownloadState.IDLE.value:
                        display_name = "None"
                    else:
                        display_name = sample.game.name if sample.game else "Unknown"

                    if sample.status in [
                        DownloadState.IDLE.value,
                        DownloadState.PAUSED.value,
                    ]:
                        speed_display = 0.0

                    log_msg = (
                        f"Status: {sample.status.upper()}, "
                        f"Game: {display_name}, "
                        f"Speed: {speed_display/ 1024 / 1024:.2f} MB/s"
                    )
                    logging.info(log_msg)
                except Exception as e:
                    logging.error(f"Error getting sample: {e}")
                    if config.samples == 0:
                        time.sleep(5)
                        continue
                    else:
                        raise
                i += 1
                if config.samples != 0 and i >= config.samples:
                    break
                time.sleep(config.interval)

    except SteamNotFoundError as e:
        logging.error(str(e))
        sys.exit(1)
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
