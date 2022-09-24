from collections import defaultdict
from datetime import datetime
import itertools
import typing
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil.parser import parse, ParserError
import discord
from discord import app_commands
from discord.ext import commands

from .timezones import abbrevs_pytz
from ..bot import Bot

TZ_DATA = abbrevs_pytz()

_STYLES = {
    "t": "Short Time",
    "T": "Long Time",
    "d": "Short Date",
    "D": "Long Date",
    "f": "Short Date Time",
    "F": "Long Date Time",
    "R": "Relative Time",
}

TIMESTAMP_STYLE = [app_commands.Choice(name=v, value=k) for k, v in _STYLES.items()]


class DatetimeTransformerError(app_commands.AppCommandError):
    pass


class TimezoneTransformerError(app_commands.AppCommandError):
    def __init__(self, tz_key: str) -> None:
        self.tz_key = tz_key


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
    async def transform(
        self, interaction: discord.Interaction, value: str, /
    ) -> ZoneInfo:
        try:
            tz = ZoneInfo(value)
        except ZoneInfoNotFoundError:
            raise TimezoneTransformerError(value)

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
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    def _make_timestamps_embed(
        self, dt: datetime, style: typing.Optional[app_commands.Choice[str]] = None
    ) -> discord.Embed:
        embed = discord.Embed(
            title="Timestamps",
            color=discord.Color.blurple(),
            description=(
                f"Timestamps for `{dt}`.\n"
                "To send a timestamp, copy the text in the black "
                "box below the format of your choice."
            ),
        )
        for s in _STYLES.keys():
            if style is not None and style.value != s:
                continue
            formatted_dt = discord.utils.format_dt(dt, style=s)
            embed.add_field(name=formatted_dt, value=f"`{formatted_dt}`")

        return embed

    @app_commands.command()
    @app_commands.describe(style="The style to format the datetime with.")
    @app_commands.choices(style=TIMESTAMP_STYLE)
    async def now(
        self,
        interaction: discord.Interaction,
        style: typing.Optional[app_commands.Choice[str]] = None,
    ) -> None:
        """Create timestamps of now to send to get rich formatting."""

        _now = discord.utils.utcnow()

        embed = self._make_timestamps_embed(_now, style=style)
        await interaction.response.send_message(embed=embed)

    @app_commands.command()
    @app_commands.describe(
        dt="The date and time.",
        tz="The time zone of the time.",
        style="The style to format the datetime with.",
    )
    @app_commands.rename(dt="datetime", tz="timezone")
    @app_commands.choices(style=TIMESTAMP_STYLE)
    async def timestamp(
        self,
        interaction: discord.Interaction,
        dt: app_commands.Transform[str, DatetimeTransformer],
        tz: app_commands.Transform[str, TimezoneTransformer],
        style: typing.Optional[app_commands.Choice[str]] = None,
    ) -> None:
        """Create timestamps of the given time to send to get rich formatting."""

        dt_tz = dt.replace(tzinfo=tz)

        embed = self._make_timestamps_embed(dt_tz, style=style)
        await interaction.response.send_message(embed=embed)

    @timestamp.error
    async def timestamp_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        """Error handler for the timestamp command."""

        if isinstance(error, TimezoneTransformerError):
            await interaction.response.send_message(
                f"Could not find the appropriate time zone `{error.tz_key}`. "
                "Try again by selecting a proposed value.",
                ephemeral=True,
            )
        else:
            interaction.extras["error_handled"] = False
