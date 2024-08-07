"""A few common functions to help the logging system work smoothly"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import discord


class LogLevel(Enum):
    """This is a way to map log levels to strings, and have the easy ability
    to dynamically add or remove log levels

    Attributes:
        DEBUG (str): Representation of debug
        INFO (str): Representation of info
        WARNING (str): Representation of warning
        ERROR (str): Representation of error
    """

    DEBUG: str = "debug"
    INFO: str = "info"
    WARNING: str = "warning"
    ERROR: str = "error"


@dataclass
class LogContext:
    """A very simple class to store a few contextual items about the log
    This is used to determine if some guild settings means the log shouldn't be logged

    Attributes:
        guild (discord.Guild | None): The guild the log occured with. Optional
        channel (discord.abc.Messageable | None): The channel, DM, thread,
            or other messagable the log occured in
    """

    guild: discord.Guild | None = None
    channel: discord.abc.Messageable | None = None
