import discord
from discord.app_commands import (
    BotMissingPermissions,
    MissingPermissions,
    NoPrivateMessage,
    check,
)


def has_guild_permissions(**perms: bool):
    """Similar to :func:`.has_permissions`, but operates on guild wide
    permissions instead of the current channel permissions.
    If this check is called in a DM context, it will raise an
    exception, :exc:`.NoPrivateMessage`.

    Ported from `discord.ext.commands` and adapted for ApplicationCommands.
    """

    invalid = set(perms) - set(discord.Permissions.VALID_FLAGS)
    if invalid:
        raise TypeError(f"Invalid permission(s): {', '.join(invalid)}")

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


def bot_has_guild_permissions(**perms: bool):
    """Similar to :func:`.has_guild_permissions`, but checks the bot
    members guild permissions.

    Ported from `discord.ext.commands` and adapted for ApplicationCommands.
    """

    invalid = set(perms) - set(discord.Permissions.VALID_FLAGS)
    if invalid:
        raise TypeError(f"Invalid permission(s): {', '.join(invalid)}")

    def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            raise NoPrivateMessage

        permissions = interaction.guild.me.guild_permissions  # type: ignore
        missing = [
            perm for perm, value in perms.items() if getattr(permissions, perm) != value
        ]

        if not missing:
            return True

        raise BotMissingPermissions(missing)

    return check(predicate)
