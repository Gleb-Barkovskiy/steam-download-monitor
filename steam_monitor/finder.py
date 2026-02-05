import platform
from pathlib import Path
from typing import Optional
from .models import SteamInstall
from .errors import SteamNotFoundError


def _find_windows_steam() -> Optional[SteamInstall]:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            path, _ = winreg.QueryValueEx(key, "SteamPath")
        root = Path(path)
        steamapps = root / "steamapps"
        logs = root / "logs"
        if steamapps.exists() and logs.exists():
            return SteamInstall(root=root, steamapps=steamapps, logs=logs)
        return None
    except (OSError, ImportError):
        return None


def _find_linux_steam() -> Optional[SteamInstall]:
    symlink = Path.home() / ".steam/steam"
    if not symlink.exists():
        return None
    root = symlink.resolve()
    steamapps = root / "steamapps"
    logs = root / "logs"
    if steamapps.exists() and logs.exists():
        return SteamInstall(root=root, steamapps=steamapps, logs=logs)
    return None


def _find_macos_steam() -> Optional[SteamInstall]:
    root = Path.home() / "Library/Application Support/Steam"
    steamapps = root / "steamapps"
    logs = root / "logs"
    if steamapps.exists() and logs.exists():
        return SteamInstall(root=root, steamapps=steamapps, logs=logs)
    return None


class SteamFinder:
    def find(self, custom_path: Optional[str] = None) -> SteamInstall:
        if custom_path:
            root = Path(custom_path).resolve()
            steamapps = root / "steamapps"
            logs = root / "logs"
            if steamapps.exists() and logs.exists():
                return SteamInstall(root=root, steamapps=steamapps, logs=logs)
            else:
                raise SteamNotFoundError(
                    f"Custom Steam path {custom_path} is invalid: missing steamapps or logs directory"
                )

        system = platform.system()
        if system == "Windows":
            steam = _find_windows_steam()
        elif system == "Linux":
            steam = _find_linux_steam()
        elif system == "Darwin":
            steam = _find_macos_steam()
        else:
            steam = None
        if steam is None:
            raise SteamNotFoundError(f"Steam not found on {system}")
        return steam
