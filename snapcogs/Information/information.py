import re
from typing import Union
import unicodedata

import discord
from discord import app_commands
from discord.ext import commands
import pint

from ..bot import Bot
from ..utils import relative_dt, run_process


UREG = pint.UnitRegistry()
UREG.default_system = None


def _extract_units():
    units = []
    for attr in dir(UREG):
        try:
            if isinstance(getattr(UREG, attr), pint.Unit):
                units.append(attr)

        except pint.UndefinedUnitError:
            pass

    return units


UNITS = _extract_units()


async def from_units_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    choice_units = [u for u in UNITS if current.lower() in u.lower()][:25]
    return [app_commands.Choice(name=unit, value=unit) for unit in choice_units]


async def to_units_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    if from_ := interaction.namespace["from"]:
        from_unit = getattr(UREG, from_)
        choice_units = [
            app_commands.Choice(name=str(unit), value=str(unit))
            for unit in UREG.get_compatible_units(from_unit.dimensionality)
            if current in str(unit)
        ][:25]

    else:
        choice_units = await from_units_autocomplete(interaction, current)

    return choice_units


def int_fmt(number, digits=3):
    return f"`{number:>{digits}d}`"


class Badge:
    active_developer = "<:active_developer:1138853279921610782>"
    bug_hunter = "<:bug_hunter:1138853282039726150>"
    bug_hunter_level_2 = "<:bug_hunter_level_2:1138853283209945198>"
    discord_verified_moderator = "<:discord_certified_moderator:1138853284598259912>"
    early_supporter = "<:early_supporter:1138853286330511481>"
    hypesquad = "<:hypesquad:1138853287882403971>"
    hypesquad_balance = "<:hypesquad_balance:1138853288884850879>"
    hypesquad_bravery = "<:hypesquad_bravery:1138853290638061599>"
    hypesquad_brilliance = "<:hypesquad_brilliance:1138853291619532902>"
    moderator = "<:moderator:1138853620218073138>"
    partner = "<:partner:1138853621287624795>"
    partner_server_owner = "<:partner_server_owner:1138853294123536424>"
    staff = "<:staff:1138853623141503076>"
    subscriber_nitro = "<:subscriber_nitro:1138853624009732268>"
    verified = "<:verified:1138853625112838224>"
    verified_bot_developer = "<:verified_bot_developer:1138853626358534206>"


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

        app_info = await self.bot.application_info()

        # host should have git installed if they installed this package
        git_link, _ = await run_process("git config --get remote.origin.url")

        embed = discord.Embed(
            title=f"Information about {self.bot.user}.",
            description=app_info.description,
            url=git_link,
            color=discord.Color.blurple(),
        ).set_thumbnail(url=self.bot.user.avatar.url)

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
                f"Joined server: {relative_dt(interaction.guild.me.joined_at)}\n"
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
            .set_thumbnail(url=user.avatar.url)
        )

        if isinstance(user, discord.Member):
            # we have more information here
            embed.title = f"{user.display_name} ({user})"
            embed.add_field(
                name="Member information",
                value=(
                    f"Joined: {relative_dt(user.joined_at)}\n"
                    f"Roles: {', '.join(r.mention for r in reversed(user.roles[1:]))}"
                ),
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command()
    @app_commands.describe(
        characters="Characters to get the unicode representation of.",
    )
    async def charinfo(self, interaction: discord.Interaction, characters: str):
        """Show information on up to 25 unicode characters.

        Adapted from
        https://github.com/python-discord/bot/blob/master/bot/cogs/utils.py
        """
        match = re.match(r"<(a?):(\w+):(\d+)>", characters)
        if match:
            embed = discord.Embed(
                title="Non-Character Detected",
                description=(
                    "Only unicode characters can be processed, but a custom "
                    "Discord emoji was found. Please remove it and try again."
                ),
                colour=discord.Colour.red(),
            )
            await interaction.response.send_message(embed=embed)
            return

        if len(characters) > 25:
            embed = discord.Embed(
                title=f"Too many characters ({len(characters)}/25)",
                colour=discord.Colour.red(),
            )

            await interaction.response.send_message(embed=embed)
            return

        def get_info(char):
            digit = f"{ord(char):x}"
            if len(digit) <= 4:
                u_code = f"\\u{digit:>04}"
            else:
                u_code = f"\\U{digit:>08}"
            url = f"https://www.compart.com/en/unicode/U+{digit:>04}"
            name = f"[{unicodedata.name(char, '')}]({url})"
            info = f"`{u_code.ljust(10)}`: {name} - {char}"
            return info, u_code

        charlist, rawlist = zip(*(get_info(c) for c in characters))

        embed = discord.Embed(
            description="\n".join(charlist), color=discord.Color.blurple()
        )
        embed.set_author(name="Character Info")

        if len(characters) > 1:
            embed.add_field(
                name="Raw",
                value=f"`{''.join(rawlist)}`",
                inline=False,
            )

        string_literals = "\n".join(
            [rf"`\N{{{unicodedata.name(char, '')}}}`" for char in characters]
        )

        embed.add_field(
            name="String Literals",
            value=string_literals,
            inline=False,
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command()
    @app_commands.rename(from_="from")
    @app_commands.describe(
        value="Value of the quantity",
        from_="Units of the quantity",
        to="Units to convert the quantity to",
    )
    @app_commands.autocomplete(from_=from_units_autocomplete, to=to_units_autocomplete)
    async def convert(
        self,
        interaction: discord.Interaction,
        value: float,
        from_: str,
        to: str,
    ):
        """Convert a value from one unit to another."""

        quantity = UREG.Quantity(value, from_)

        await interaction.response.send_message(
            f"You converted `{quantity}` to `{quantity.to(to):.3g}`", ephemeral=True
        )
