class SteamNotFoundError(Exception):
    """Raised when Steam installation cannot be located."""

    pass


class ACFParseError(Exception):
    """Raised when an ACF file is malformed or unreadable."""

    pass
