from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.app_commands import (
    BotMissingPermissions,
    MissingPermissions,
    NoPrivateMessage,
    check,
)
from discord.ext import commands

from .errors import NotOwner

if TYPE_CHECKING:
    from collections.abc import Callable


def has_guild_permissions(**perms: bool) -> Callable:
    """Similar to :func:`.has_permissions`, but operates on guild wide
    permissions instead of the current channel permissions.
    If this check is called in a DM context, it will raise an
    exception, :exc:`.NoPrivateMessage`.

    Ported from `discord.ext.commands` and adapted for ApplicationCommands.
    """

    invalid = set(perms) - set(discord.Permissions.VALID_FLAGS)
    if invalid:
        msg = f"Invalid permission(s): {', '.join(invalid)}"
        raise TypeError(msg)

    def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            raise NoPrivateMessage
        assert isinstance(interaction.user, discord.Member)

        permissions = interaction.user.guild_permissions
        missing = [
            perm for perm, value in perms.items() if getattr(permissions, perm) != value
        ]

        if not missing:
            return True

        raise MissingPermissions(missing)

    return check(predicate)


def bot_has_guild_permissions(**perms: bool) -> Callable:
    """Similar to :func:`.has_guild_permissions`, but checks the bot
    members guild permissions.

    Ported from `discord.ext.commands` and adapted for ApplicationCommands.
    """

    invalid = set(perms) - set(discord.Permissions.VALID_FLAGS)
    if invalid:
        msg = f"Invalid permission(s): {', '.join(invalid)}"
        raise TypeError(msg)

    def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            raise NoPrivateMessage

        permissions = interaction.guild.me.guild_permissions
        missing = [
            perm for perm, value in perms.items() if getattr(permissions, perm) != value
        ]

        if not missing:
            return True

        raise BotMissingPermissions(missing)

    return check(predicate)


async def _is_owner(interaction: discord.Interaction) -> bool:
    """Interaction based version of the discord.ext.commands.Bot.is_owner method."""

    if isinstance(interaction.client, commands.Bot):
        return await interaction.client.is_owner(interaction.user)

    app = await interaction.client.application_info()

    if app.team:
        ids = {m.id for m in app.team.members}
        return interaction.user.id in ids

    return interaction.user.id == app.owner.id


def is_owner[T]() -> Callable[[T], T]:
    """A check decorator that checks if the user invoking the command
    is the owner of the bot.
    """

    async def predicate(interaction: discord.Interaction) -> bool:
        if not await _is_owner(interaction):
            msg = "You do not own this bot."
            raise NotOwner(msg)

        return True

    return app_commands.check(predicate)
