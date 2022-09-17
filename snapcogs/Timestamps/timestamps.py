from collections import defaultdict
from datetime import datetime
import itertools
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil.parser import parse, ParserError
import discord
from discord import app_commands
from discord.ext import commands

from .timezones import abbrevs_pytz

TZ_DATA = abbrevs_pytz()


class DatetimeTransformerError(app_commands.AppCommandError):
    pass


class TimezoneTransformerError(app_commands.AppCommandError):
    pass


class DatetimeTransformer(app_commands.Transformer):
    cache = defaultdict(lambda: discord.utils.utcnow())

    async def transform(
        self, interaction: discord.Interaction, value: str, /
    ) -> datetime:
        try:
            dt = parse(timestr=value, fuzzy=True, ignoretz=True)
            self.cache[interaction.user.id] = dt
        except ParserError:
            # ignore possible incomplete input
            dt = self.cache[interaction.user.id]
        return dt

    async def autocomplete(
        self, interaction: discord.Interaction, value: str, /
    ) -> list[app_commands.Choice[str]]:
        dt = await self.transform(interaction, value)
        return [
            app_commands.Choice(
                name=dt.strftime("%A, %B %d, %Y %H:%M"), value=dt.isoformat()
            )
        ]


class TimezoneTransformer(app_commands.Transformer):
    async def transform(self, interaction: discord.Interaction, value: str, /) -> str:
        try:
            tz = ZoneInfo(value)
        except ZoneInfoNotFoundError as e:
            raise TimezoneTransformerError(e)
        return tz

    async def autocomplete(
        self, interaction: discord.Interaction, value: str, /
    ) -> list[app_commands.Choice[str]]:
        possible_abbrevs = [
            abbrev for abbrev in TZ_DATA.keys() if value.upper() in abbrev
        ]
        possible_tz = list(
            itertools.chain(*[TZ_DATA[abbrev] for abbrev in possible_abbrevs])
        )
        possible_tz.sort()
        return [
            app_commands.Choice(name=tz.choice_str, value=tz.name) for tz in possible_tz
        ][:25]


class Timestamps(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _make_timestamps_embed(self, dt: datetime) -> discord.Embed:
        styles = "fFtTdDR"
        embed = discord.Embed(
            title="Timestamps",
            color=discord.Color.blurple(),
            description=(
                f"Timestamps for `{dt}`.\n"
                "To send a timestamp, copy the text in the black "
                "box below the format of your choice."
            ),
        )
        for style in styles:
            formatted_dt = discord.utils.format_dt(dt, style=style)
            embed.add_field(name=formatted_dt, value=f"`{formatted_dt}`")

        return embed

    @app_commands.command()
    async def now(self, interaction: discord.Interaction) -> None:
        """Create timestamps of now to send to get rich formatting."""
        _now = discord.utils.utcnow()

        embed = self._make_timestamps_embed(_now)
        await interaction.response.send_message(embed=embed)

    @app_commands.command()
    @app_commands.describe(dt="Date and time", tz="Time zone of the time")
    @app_commands.rename(dt="datetime", tz="timezone")
    async def timestamp(
        self,
        interaction: discord.Interaction,
        dt: app_commands.Transform[str, DatetimeTransformer],
        tz: app_commands.Transform[str, TimezoneTransformer],
    ) -> None:
        """Create timestamps of the given time to send to get rich formatting."""
        dt_tz = dt.replace(tzinfo=tz)

        embed = self._make_timestamps_embed(dt_tz)
        await interaction.response.send_message(embed=embed)

    @timestamp.error
    async def timestamp_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        interaction.extras["error_handled"] = False
