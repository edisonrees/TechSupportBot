"""This is the core of the IRC bot. It connects to IRC and handles
message tranmissions to discord"""

from __future__ import annotations

import asyncio
import functools
import logging
import os
import ssl
import threading
from typing import Self

import commands
import discord
import irc.bot
import irc.client
import irc.connection
from ircrelay import formatting


class IRCBot(irc.bot.SingleServerIRCBot):
    """The IRC bot class. This is the class that runs the entire IRC side of the bot
    The class to start the entire IRC bot

    Attributes:
        irc_cog (commands.relay.DiscordToIRC): The discord cog for the relay,
            to allow communication between
        loop (asyncio.AbstractEventLoop): The discord bots event loop
        console (logging.Logger): The console to print errors to
        IRC_BOLD (str): The bold character for IRC
        connection (irc.client.ServerConnection): The IRC connection event
        join_thread (threading.Timer): The repeating join channel request thread
        ready (bool): Whether the IRC bot is ready to send messages

    Args:
        loop (asyncio.AbstractEventLoop): The running event loop for the discord API.
        server (str): The string server domain/IP
        port (int): The port the IRC server is running on
        channels (list[str]): The list of channels to join
        username (str): The username of the IRC bot account
        password (str): The password of the IRC bot account
    """

    irc_cog: commands.relay.DiscordToIRC = None
    loop: asyncio.AbstractEventLoop = None
    console: logging.Logger = logging.getLogger("root")
    IRC_BOLD: str = ""
    connection: irc.client.ServerConnection = None
    join_thread: threading.Timer = None
    ready: bool = False

    def __init__(
        self: Self,
        loop: asyncio.AbstractEventLoop,
        server: str,
        port: int,
        channels: list[str],
        username: str,
        password: str,
    ) -> None:
        self.loop = loop
        self.username = username
        self.password = password
        self.join_channel_list = channels

        # SSL context setup
        context = ssl.create_default_context()
        factory = irc.connection.Factory(
            wrapper=functools.partial(context.wrap_socket, server_hostname=server)
        )

        # Pass the correct server info and password
        super().__init__(
            server_list=[
                (server, port, password)
            ],  # Ensure this has the correct password
            realname=username,
            nickname=username,
            connect_factory=factory,
        )

        # Reconnect handler if disconnected
        self._on_disconnect = self.reconnect_from_disconnect

    def exit_irc(self: Self) -> None:
        """Instatly kills the IRC thread"""
        # pylint: disable=protected-access
        os._exit(1)

    def start_bot(self: Self) -> None:
        """Start the bot and handle SASL authentication."""
        self.connection.set_rate_limit(1)  # Be nice to server
        self.connection.username = self.username
        self.connection.sasl_login = self.username
        self.start()  # Starts the IRC bot's main loop

    def reconnect_from_disconnect(
        self: Self, connection: irc.client.ServerConnection, event: irc.client.Event
    ) -> None:
        """Reconnecting to IRC in the event there is a disconnect

        Args:
            connection (irc.client.ServerConnection): The IRC connection
            event (irc.client.Event): The event object that triggered this function
        """
        self.console.error("Disconnected from IRC - Attempting reconnection: %s", event)
        connection.reconnect()

    def on_nicknameinuse(
        self: Self, connection: irc.client.ServerConnection, _: irc.client.Event
    ) -> None:
        """A simple way to ensure that the bot will never be reject for an in use nickname

        Args:
            connection (irc.client.ServerConnection): The IRC connection
        """
        connection.nick(connection.get_nickname() + "_")

    def on_welcome(
        self: Self, connection: irc.client.ServerConnection, _: irc.client.Event
    ) -> None:
        """What to do after the connection has been established, but before authentication
        This authenticates using SASL, joins channels, and starts a thread to auto join channels
        when needed

        Args:
            connection (irc.client.ServerConnection): The IRC connection
        """
        self.console.info("Connected to IRC")
        self.ready = True
        self.custom_join_channels()
        self.connection = connection
        self.join_thread = threading.Timer(600, self.join_channels_thread)
        self.join_thread.start()

    def custom_join_channels(self: Self) -> None:
        """Joins all channels from the list of channels in self.join_channel_list"""
        if not self.ready:
            return
        for channel in self.join_channel_list:
            self.console.info("Joining %s", channel)
            self.connection.join(channel)

    def join_channels_thread(self: Self) -> None:
        """A function called by the auto join channel thread
        This restarts the thread, and calls the join channels function
        In the event the bot ever leaves a channel for some reason, like a net split
        This will ensure that the bot rejoins them
        """
        self.custom_join_channels()
        if self.join_thread and self.join_thread.is_alive():
            self.join_thread.cancel()
        self.join_thread = threading.Timer(600, self.join_channels_thread)
        self.join_thread.start()

    def on_part(
        self: Self, connection: irc.client.ServerConnection, event: irc.client.Event
    ) -> None:
        """How to handle what happens when the bot leaves a channel

        Args:
            connection (irc.client.ServerConnection): The IRC connection
            event (irc.client.Event): The event object that triggered this function
        """
        if event.target == self.username:
            self.custom_join_channels()

    def on_privmsg(
        self: Self, _: irc.client.ServerConnection, event: irc.client.Event
    ) -> None:
        """What to do when the bot gets DMs on IRC
        Currently just sends a message to the discord bot owners DMs

        Args:
            event (irc.client.Event): The event object that triggered this function
        """
        asyncio.run_coroutine_threadsafe(
            self.irc_cog.handle_dm_from_irc(message=event.arguments[0], event=event),
            self.loop,
        )

    def on_pubmsg(
        self: Self, _: irc.client.ServerConnection, event: irc.client.Event
    ) -> None:
        """What to do when a message is sent in a public channel the bot is in
        If the channel is linked to a discord channel, the message will get sent to discord

        Args:
           event (irc.client.Event): The event object that triggered this function
        """
        split_message = formatting.parse_irc_message(event=event)
        if len(split_message) == 0:
            return
        self.send_message_to_discord(split_message=split_message)

    def send_message_to_discord(self: Self, split_message: dict[str, str]) -> None:
        """Sends the given message to discord, using the discord API event loop

        Args:
            split_message (dict[str, str]): The formatted message to send to discord
        """
        asyncio.run_coroutine_threadsafe(
            self.irc_cog.send_message_from_irc(split_message=split_message), self.loop
        )

    def get_irc_status(self: Self) -> dict[str, str]:
        """Gets the status of the IRC bot
        Returns nicely formatted status, username, and channels

        Returns:
            dict[str, str]: The dictionary containing the 3 status items as strings
        """
        status_text = self.generate_status_string()
        channels = ", ".join(self.channels.keys())
        if len(channels.strip()) == 0:
            channels = "No channels"
        return {
            "status": status_text,
            "name": self.username,
            "channels": channels,
        }

    def generate_status_string(self: Self) -> str:
        """Generates a human readable status string
        This takes into account the login process, if the connection is active,
        and if the discord side loaded fie

        Returns:
            str: The human readable string, will be one or two words
        """
        if not self.ready:
            return "Not ready"
        if not self.irc_cog:
            return "Discord failure"
        if not self.connection.is_connected():
            return "Not connected"
        return "Connected"

    def send_edit_from_discord(
        self: Self, message: discord.Message, channel: str
    ) -> None:
        """This handles a discord message being edited

        Args:
            message (discord.Message): The message object after being edited
            channel (str): The linked IRC channel the message was sent
        """
        # if channel not in self.channels:
        #    self.join_channels(self.connection)
        formatted_message = formatting.format_discord_edit_message(message=message)
        self.send_message_to_channel(channel=channel, message=formatted_message)

    def send_reaction_from_discord(
        self: Self, reaction: discord.Reaction, user: discord.User, channel: str
    ) -> None:
        """This handles a discord message getting a reaction added to it
        This does currently not handle the IRC message getting a reaction added to it

        Args:
            reaction (discord.Reaction): The reaction object that added
            user (discord.User): The user who added the reaction
            channel (str): The linked IRC channel the message reacted to is in
        """
        # if channel not in self.channels:
        #    self.join_channels(connection=self.connection)
        formatted_message = formatting.format_discord_reaction_message(
            reaction.message, user, reaction
        )
        self.send_message_to_channel(channel=channel, message=formatted_message)

    def send_message_from_discord(
        self: Self, message: discord.Message, channel: str, content_override: str = None
    ) -> None:
        """Sends a message from discord to IRC

        Args:
            message (discord.Message): The message object that was sent on discord
            channel (str): The linked IRC channel the message was sent
            content_override (str): If passed, this will changed the content of the message
        """
        # if channel not in self.channels:
        #    self.join_channels(connection=self.connection)
        formatted_message = formatting.format_discord_message(
            message=message, content_override=content_override
        )
        self.send_message_to_channel(channel=channel, message=formatted_message)

    def send_message_to_channel(self: Self, channel: str, message: str) -> None:
        """Sends a message to a channel. Splits the message if needed

        Args:
            channel (str): The IRC channel to send the message to
            message (str): The fully formatted string to send to the IRC channel
        """
        message_list = [message[i : i + 430] for i in range(0, len(message), 430)]
        for cut_message in message_list:
            self.connection.privmsg(channel, cut_message)

    def on_mode(
        self: Self, _: irc.client.ServerConnection, event: irc.client.Event
    ) -> None:
        """What to do when a channel mode is changed
        Currently just handles ban notifications

        Args:
            event (irc.client.Event): The event object that triggered this function
        """
        # Parse the mode change event
        modes = event.arguments[0].split()
        # The first element of `modes` is the mode being set or removed
        mode = modes[0]

        if mode in ("+b", "-b"):
            message = formatting.parse_ban_message(event=event)
            self.send_message_to_discord(split_message=message)

    def ban_on_irc(self: Self, user: str, channel: str, action: str) -> None:
        """Ban or unban a given user on the specified IRC channe;

        Args:
            user (str): The hostmask of the user to modify
            channel (str): The channel to modify the user in
            action (str): The action, either +b or -b, to take on the user
        """
        self.connection.mode(channel, f"{action} {user}")

    def is_bot_op_on_channel(self: Self, channel_name: str) -> bool:
        """Checking if the bot is an operator on the given channel

        Args:
            channel_name (str): The string representation of the IRC channel to check

        Returns:
            bool: True if the bot is an operator, False if it's not
        """
        return self.channels[channel_name].is_oper(self.username)
