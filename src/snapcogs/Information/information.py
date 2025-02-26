import logging
from typing import Union

import discord
from discord import app_commands
from discord.ext import commands

from ..bot import Bot
from ..utils import relative_dt, run_process

LOGGER = logging.getLogger(__name__)


def int_fmt(number, digits=3):
    return f"`{number:>{digits}d}`"


class Information(commands.Cog):
    info = app_commands.Group(
        name="info", description="Get information about something"
    )

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

        self.info_user_context_menu = app_commands.ContextMenu(
            name="Info",
            callback=self.info_user_callback,
        )
        self.bot.tree.add_command(self.info_user_context_menu)

    @app_commands.command()
    async def about(self, interaction: discord.Interaction):
        """View information about the bot itself."""

        assert self.bot.user is not None
        assert interaction.guild is not None
        app_info = await self.bot.application_info()

        # host should have git installed if they installed this package
        git_link, _ = await run_process("git config --get remote.origin.url")

        if self.bot.user.avatar:
            thumbnail_url = self.bot.user.avatar.url
        else:
            thumbnail_url = ""

        embed = discord.Embed(
            title=f"Information about {self.bot.user}.",
            description=app_info.description,
            url=git_link,
            color=discord.Color.blurple(),
        ).set_thumbnail(url=thumbnail_url)

        # some statistics
        total_members = 0
        total_online = 0
        offline = discord.Status.offline
        for member in self.bot.get_all_members():
            total_members += 1
            if member.status is not offline:
                total_online += 1

        total_unique = len(self.bot.users)

        text_channels = 0
        voice_channels = 0
        guilds = 0
        for guild in self.bot.guilds:
            guilds += 1
            for channel in guild.channels:
                if isinstance(channel, discord.TextChannel):
                    text_channels += 1
                elif isinstance(channel, discord.VoiceChannel):
                    voice_channels += 1

        embed.add_field(
            name="Members",
            value=(
                f"{int_fmt(total_members)} Total\n"
                f"{int_fmt(total_unique)} Unique\n"
                f"{int_fmt(total_online)} Online"
            ),
        )
        embed.add_field(
            name="Channels",
            value=(
                f"{int_fmt(text_channels + voice_channels)} Total\n"
                f"{int_fmt(text_channels)} Text\n"
                f"{int_fmt(voice_channels)} Voice"
            ),
        )
        embed.add_field(
            name="Installs",
            value=(
                f"{int_fmt(app_info.approximate_guild_count)} Servers\n"
                f"{int_fmt(app_info.approximate_user_install_count)} Users"
            ),
        )
        embed.add_field(
            name="Timeline",
            value=(
                f"Created: {relative_dt(self.bot.user.created_at)}\n"
                f"Joined server: {relative_dt(interaction.guild.me.joined_at or discord.utils.utcnow())}\n"
                f"Boot time: {relative_dt(self.bot.boot_time)}"
            ),
            inline=False,
        )

        embed.set_footer(
            text=f"Made with discord.py v{discord.__version__} by {app_info.owner}",
            icon_url="http://i.imgur.com/5BFecvA.png",
        )
        embed.timestamp = discord.utils.utcnow()

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @info.command(name="server")
    async def info_guild(self, interaction: discord.Interaction):
        """View information about the current server."""

        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message(
                "Cannot use this command in private messages.", ephemeral=True
            )

        embed = discord.Embed(title=guild.name, color=discord.Color.blurple())
        description = f"Server created {relative_dt(guild.created_at)}."
        if guild.description:
            description = f"{guild.description}\n{description}"
        embed.description = description

        embed.set_thumbnail(
            url=(
                guild.icon.url
                if guild.icon
                else "https://cdn.discordapp.com/embed/avatars/1.png"
            )
        )

        embed.add_field(
            name="Members Info",
            value=(
                f"{int_fmt(guild.member_count)} Members\n"
                f"{int_fmt(len(guild.roles) - 1)} Roles\n"
            ),
        ).add_field(
            name=f"Nitro Level {guild.premium_tier}",
            value=(
                f"{int_fmt(len(guild.premium_subscribers))} Nitro Boosters\n"
                f"{int_fmt(guild.premium_subscription_count)} Nitro Boosts\n"
            ),
        ).add_field(
            name="Channels",
            value=(
                f"{int_fmt(len(guild.text_channels))} Text\n"
                f"{int_fmt(len(guild.voice_channels))} Voice\n"
                f"{int_fmt(len(guild.stage_channels))} Stage\n"
            ),
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @info.command(name="user")
    @app_commands.describe(user="User or member to get the information of")
    async def info_user(
        self,
        interaction: discord.Interaction,
        user: Union[discord.Member, discord.User],
    ):
        """View information about a user / member."""

        await self.info_user_callback(interaction, user)

    async def info_user_callback(
        self,
        interaction: discord.Interaction,
        user: Union[discord.Member, discord.User],
    ):
        """Send the information about the requested user / member."""

        application_emojis = await self.bot.fetch_application_emojis()

        def get_badge_emoji(badge: str) -> discord.Emoji | None:
            for emoji in application_emojis:
                if emoji.name == badge:
                    return emoji

            return None

        badges = []
        emoji_warning = []
        for badge, is_set in user.public_flags:
            if not is_set:
                # skip if the flag is not set: the user does not have the badge
                continue

            emoji = get_badge_emoji(badge)
            if emoji is not None:
                badges.append(str(emoji))
            else:
                emoji_warning.append(badge)

        if len(emoji_warning) != 0:
            warning_str = ", ".join(emoji_warning)
            LOGGER.warning(
                "Some Application Emoji were not found, they will not show on profile: "
                f"{warning_str}"
            )
            LOGGER.warning(
                "Download the files at https://emoji.gg/pack/1834-profile-badges# "
                "and name them according to discord.User.public_flags"
            )

        embed = (
            discord.Embed(
                title=f"{user}", description=" ".join(badges), color=user.color
            )
            .add_field(
                name="User information",
                value=(
                    f"Created: {relative_dt(user.created_at)}\n"
                    f"Profile: {user.mention}\n"
                    f"ID: {user.id}"
                ),
                inline=False,
            )
            .set_thumbnail(url=user.avatar.url if user.avatar else None)
        )

        if isinstance(user, discord.Member):
            # we have more information here
            embed.title = f"{user.display_name} ({user})"
            embed.add_field(
                name="Member information",
                value=(
                    f"Joined: {relative_dt(user.joined_at) if user.joined_at else 'Unknown'}\n"
                    f"Roles: {', '.join(r.mention for r in reversed(user.roles[1:]))}"
                ),
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)
