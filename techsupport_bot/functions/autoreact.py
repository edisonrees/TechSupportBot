"""Module for the autoreact extension for the discord bot."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import munch
from core import auxiliary, cogs, extensionconfig
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Autoreact plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    config = extensionconfig.ExtensionConfig()
    config.add(
        key="react_map",
        datatype="dict",
        title="Mapping of phrases",
        description="Lowercase phrase to reaction wanted",
        default={"hello": "👋"},
    )

    await bot.add_cog(AutoReact(bot=bot, extension_name="autoreact"))
    bot.add_extension_config("autoreact", config)


class AutoReact(cogs.MatchCog):
    """Class for the autoreact to make it to discord."""

    async def match(
        self: Self, config: munch.Munch, _: commands.Context, content: str
    ) -> bool:
        """A match function to determine if somehting should be reacted to

        Args:
            config (munch.Munch): The guild config for the running bot
            content (str): The string content of the message

        Returns:
            bool: True if there needs to be a reaction, False otherwise
        """
        search_content = f" {content} "
        search_content = search_content.lower()
        for word in config.extensions.autoreact.react_map.value:
            if f" {word.lower()} " in search_content:
                return True
        return False

    async def response(
        self: Self, config: munch.Munch, ctx: commands.Context, content: str, _: bool
    ) -> None:
        """The function to generate and add reactions

        Args:
            config (munch.Munch): The guild config for the running bot
            ctx (commands.Context): The context in which the message was sent in
            content (str): The string content of the message
        """
        search_content = f" {content} "
        search_content = search_content.lower()
        reactions = []
        for word in config.extensions.autoreact.react_map.value:
            if f" {word.lower()} " in search_content:
                reaction = config.extensions.autoreact.react_map.value.get(word)
                if reaction not in reactions:
                    reactions.append(
                        config.extensions.autoreact.react_map.value.get(word)
                    )
        await auxiliary.add_list_of_reactions(message=ctx.message, reactions=reactions)
