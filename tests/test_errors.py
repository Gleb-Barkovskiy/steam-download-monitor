import pytest
from steam_monitor.errors import SteamNotFoundError


class TestSteamNotFoundError:
    """Tests for SteamNotFoundError exception."""

    def test_is_exception(self):
        """Test that SteamNotFoundError is an Exception."""
        assert issubclass(SteamNotFoundError, Exception)

    def test_raise_with_message(self):
        """Test raising SteamNotFoundError with a message."""
        with pytest.raises(SteamNotFoundError) as exc_info:
            raise SteamNotFoundError("Steam not found on Linux")
        assert str(exc_info.value) == "Steam not found on Linux"

    def test_raise_without_message(self):
        """Test raising SteamNotFoundError without a message."""
        with pytest.raises(SteamNotFoundError):
            raise SteamNotFoundError()

    def test_catch_as_exception(self):
        """Test catching SteamNotFoundError as generic Exception."""
        try:
            raise SteamNotFoundError("Test error")
        except Exception as e:
            assert isinstance(e, SteamNotFoundError)
            assert str(e) == "Test error"
