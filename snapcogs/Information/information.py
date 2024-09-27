from typing import Union

import discord
from discord import app_commands
from discord.ext import commands

from ..bot import Bot
from ..utils import relative_dt, run_process


def int_fmt(number, digits=3):
    return f"`{number:>{digits}d}`"


class Badge:
    active_developer = "<:active_developer:1266092694506311843>"
    bug_hunter = "<:bug_hunter:1266092708460499044>"
    bug_hunter_level_2 = "<:bug_hunter_level_2:1266092721475686432>"
    discord_verified_moderator = "<:discord_certified_moderator:1266092743122354276>"
    early_supporter = "<:early_supporter:1266092753692000448>"
    hypesquad = "<:hypesquad:1266092765566210171>"
    hypesquad_balance = "<:hypesquad_balance:1266092776827654286>"
    hypesquad_bravery = "<:hypesquad_bravery:1266092787267272784>"
    hypesquad_brilliance = "<:hypesquad_brilliance:1266092800173150209>"
    moderator = "<:moderator:1266092811208364175>"
    partner = "<:partner:1266092818628214906>"
    partner_server_owner = "<:partner_server_owner:1266092826249396396>"
    staff = "<:staff:1266092833744490526>"
    subscriber_nitro = "<:subscriber_nitro:1266092840895647855>"
    verified = "<:verified:1266092849573920779>"
    verified_bot_developer = "<:verified_bot_developer:1266092858813714442>"


class Information(commands.Cog):
    # timestamps?

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
            name="Servers",
            value=int_fmt(guilds),
        )
        embed.add_field(
            name="Timeline",
            value=(
                f"Created: {relative_dt(self.bot.user.created_at)}\n"
                f"Joined server: {relative_dt(interaction.guild.me.joined_at or discord.utils.utcnow())}\n"
                f"Boot time: {relative_dt(self.bot.boot_time)}"
            ),
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
                f"{int_fmt(len(guild.roles)-1)} Roles\n"
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

        badges = []
        for badge, is_set in user.public_flags:
            if is_set and (emoji := getattr(Badge, badge, None)):
                badges.append(emoji)

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
            .set_thumbnail(url=user.avatar.url if user.avatar else "")
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
