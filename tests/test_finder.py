import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from steam_monitor.finder import (
    SteamFinder,
    _find_linux_steam,
    _find_macos_steam,
    _find_windows_steam,
)
from steam_monitor.errors import SteamNotFoundError


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only test")
class TestWindowsSteamFinder:
    """Tests for Windows Steam detection."""

    @patch("winreg.OpenKey")
    @patch("winreg.QueryValueEx")
    @patch("steam_monitor.finder.Path.exists", return_value=True)
    def test_find_windows_steam_success(self, mock_exists, mock_query, mock_open):
        """Test successful Windows Steam detection."""
        mock_query.return_value = ("C:\\Program Files (x86)\\Steam", 1)
        steam_install = _find_windows_steam()

        assert steam_install is not None
        assert str(steam_install.root) == "C:\\Program Files (x86)\\Steam"

    @patch("winreg.OpenKey", side_effect=FileNotFoundError())
    def test_find_windows_steam_registry_error(self, mock_open):
        """Test Windows detection when registry access fails."""
        steam_install = _find_windows_steam()
        assert steam_install is None

    @patch("winreg.OpenKey")
    @patch("winreg.QueryValueEx")
    @patch("steam_monitor.finder.Path.exists", return_value=False)
    def test_find_windows_steam_missing_dirs(self, mock_exists, mock_query, mock_open):
        """Test Windows detection when directories don't exist."""
        mock_query.return_value = ("C:\\Fake\\Steam", 1)
        steam_install = _find_windows_steam()
        assert steam_install is None


class TestLinuxSteamFinder:
    """Tests for Linux Steam detection."""

    @patch("pathlib.Path.home")
    def test_find_linux_steam_success(self, mock_home):
        """Test successful Linux Steam detection."""
        mock_home.return_value = Path("/home/user")

        with patch("pathlib.Path.exists") as mock_exists:
            with patch("pathlib.Path.resolve") as mock_resolve:
                mock_exists.return_value = True
                mock_resolve.return_value = Path(
                    "/home/user/.steam/debian-installation"
                )

                result = _find_linux_steam()
                assert result is not None
                assert result.root == Path("/home/user/.steam/debian-installation")

    @patch("pathlib.Path.home")
    def test_find_linux_steam_no_symlink(self, mock_home):
        """Test Linux detection when symlink doesn't exist."""
        mock_home.return_value = Path("/home/user")

        with patch("pathlib.Path.exists", return_value=False):
            result = _find_linux_steam()
            assert result is None

    @patch("pathlib.Path.home")
    def test_find_linux_steam_missing_dirs(self, mock_home):
        """Test Linux detection when required directories are missing."""
        mock_home.return_value = Path("/home/user")

        with patch("pathlib.Path.exists") as mock_exists:
            with patch("pathlib.Path.resolve") as mock_resolve:
                # Symlink exists but directories don't
                mock_exists.side_effect = [True, False, False]
                mock_resolve.return_value = Path(
                    "/home/user/.steam/debian-installation"
                )

                result = _find_linux_steam()
                assert result is None


class TestMacOSSteamFinder:
    """Tests for macOS Steam detection."""

    @patch("pathlib.Path.home")
    def test_find_macos_steam_success(self, mock_home):
        """Test successful macOS Steam detection."""
        mock_home.return_value = Path("/Users/user")

        with patch("pathlib.Path.exists", return_value=True):
            result = _find_macos_steam()
            assert result is not None
            assert result.root == Path("/Users/user/Library/Application Support/Steam")

    @patch("pathlib.Path.home")
    def test_find_macos_steam_missing_dirs(self, mock_home):
        """Test macOS detection when directories don't exist."""
        mock_home.return_value = Path("/Users/user")

        with patch("pathlib.Path.exists", return_value=False):
            result = _find_macos_steam()
            assert result is None


class TestSteamFinder:
    """Tests for the main SteamFinder class."""

    def test_find_with_custom_path_success(self, tmp_path):
        """Test finding Steam with a valid custom path."""
        # Create temporary directories
        steamapps = tmp_path / "steamapps"
        logs = tmp_path / "logs"
        steamapps.mkdir()
        logs.mkdir()

        finder = SteamFinder()
        result = finder.find(custom_path=str(tmp_path))

        assert result.root == tmp_path
        assert result.steamapps == steamapps
        assert result.logs == logs

    def test_find_with_custom_path_missing_dirs(self, tmp_path):
        """Test finding Steam with custom path missing required directories."""
        finder = SteamFinder()
        with pytest.raises(SteamNotFoundError) as exc_info:
            finder.find(custom_path=str(tmp_path))
        assert "missing steamapps or logs directory" in str(exc_info.value)

    @patch("platform.system", return_value="Windows")
    @patch("steam_monitor.finder._find_windows_steam")
    def test_find_windows_auto(self, mock_find_windows, mock_platform):
        """Test auto-detection on Windows."""
        mock_install = MagicMock()
        mock_find_windows.return_value = mock_install

        finder = SteamFinder()
        result = finder.find()

        assert result == mock_install
        mock_find_windows.assert_called_once()

    @patch("platform.system", return_value="Linux")
    @patch("steam_monitor.finder._find_linux_steam")
    def test_find_linux_auto(self, mock_find_linux, mock_platform):
        """Test auto-detection on Linux."""
        mock_install = MagicMock()
        mock_find_linux.return_value = mock_install

        finder = SteamFinder()
        result = finder.find()

        assert result == mock_install
        mock_find_linux.assert_called_once()

    @patch("platform.system", return_value="Darwin")
    @patch("steam_monitor.finder._find_macos_steam")
    def test_find_macos_auto(self, mock_find_macos, mock_platform):
        """Test auto-detection on macOS."""
        mock_install = MagicMock()
        mock_find_macos.return_value = mock_install

        finder = SteamFinder()
        result = finder.find()

        assert result == mock_install
        mock_find_macos.assert_called_once()

    @patch("platform.system", return_value="FreeBSD")
    def test_find_unsupported_platform(self, mock_platform):
        """Test finding Steam on unsupported platform."""
        finder = SteamFinder()
        with pytest.raises(SteamNotFoundError) as exc_info:
            finder.find()
        assert "Steam not found on FreeBSD" in str(exc_info.value)

    @patch("platform.system", return_value="Windows")
    @patch("steam_monitor.finder._find_windows_steam", return_value=None)
    def test_find_steam_not_installed(self, mock_find_windows, mock_platform):
        """Test when Steam is not installed."""
        finder = SteamFinder()
        with pytest.raises(SteamNotFoundError) as exc_info:
            finder.find()
        assert "Steam not found on Windows" in str(exc_info.value)
