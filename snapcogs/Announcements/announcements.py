import asyncio
import datetime
import itertools
import logging
import random
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.utils import format_dt
from snapcogs import Bot
from snapcogs.utils import relative_dt
from snapcogs.utils.db import read_sql_query
from snapcogs.utils.views import confirm_prompt

LOGGER = logging.getLogger(__name__)
SQL = Path(__file__).parent / "sql"


EMBED_COLOR = 0xFFD700


@dataclass
class Birthday:
    birthday: datetime.date
    guild_id: int
    user_id: int


class Month(Enum):
    January = 1
    February = 2
    March = 3
    April = 4
    May = 5
    June = 6
    July = 7
    August = 8
    September = 9
    October = 10
    November = 11
    December = 12


def get_next_occurence(date: datetime.date) -> datetime.datetime:
    """Return a date object for the next occurence of the given birthday."""

    now = discord.utils.utcnow()
    bday = datetime.datetime(
        year=now.year, month=date.month, day=date.day, hour=12, tzinfo=datetime.UTC
    )

    if (bday - now).total_seconds() < 0:
        bday = bday.replace(year=bday.year + 1)

    return bday


class Announcements(commands.Cog):
    birthday = app_commands.Group(
        name="birthday", description="Save and celebrate server members' birthday!"
    )

    def __init__(self, bot: Bot):
        self.bot = bot

    async def cog_load(self):
        await self._create_tables()
        self.birthday_announcement.start()

    async def cog_unload(self):
        self.birthday_announcement.cancel()

    @tasks.loop(time=datetime.time(hour=12, tzinfo=datetime.UTC))
    async def birthday_announcement(self):
        """Accounce the birthday of a member.
        Birthdays need to be registered by the member beforehand
        with the command `!birthday register <DD/MM/YYYY>`.
        """
        birthdays = await self._get_today_birthday()
        LOGGER.debug(f"Found {len(birthdays)} birthdays for today")

        if len(birthdays) != 0:
            for bday in birthdays:
                guild = self.bot.get_guild(bday.guild_id)
                if guild is None:
                    # Bot left the guild maybe?
                    continue
                try:
                    member = await guild.fetch_member(bday.user_id)
                    guild.get_member
                    # if we bring back the Birthday role,
                    # this needs to be called as a task
                    asyncio.create_task(self.birthday_task(member))
                except discord.NotFound:
                    LOGGER.error(
                        f"Member {bday.user_id} was not found in guild {guild.id}."
                    )

    @birthday_announcement.before_loop
    async def birthday_announcement_before(self):
        await self.bot.wait_until_ready()

    async def birthday_task(self, member: discord.Member):
        """Task to send the birthday Embed to the member's guild's system channel."""
        if member.guild.system_channel is None:
            LOGGER.debug(
                f"Guild {member.guild.name} ({member.guild.id}) has no system_channel."
            )
            return

        LOGGER.debug(f"Celebrating {member}'s birthday")
        embed = (
            discord.Embed(
                description=(
                    f"# Happy Birthday {member.display_name} ({member.mention})!\n"
                    f"It is a very special day! Let's all wish them a happy birthday!"
                ),
                color=EMBED_COLOR,
            )
            .set_thumbnail(url=member.display_avatar.url)
            .set_footer(
                text=(
                    "Want to celebrate your birthday too? "
                    "Register with /birthday register."
                ),
                icon_url="https://em-content.zobj.net/thumbs/160/twitter/351/information_2139-fe0f.png",  # noqa
            )
        )
        message = await member.guild.system_channel.send(embed=embed)
        reactions = [
            "\U0001f973",
            "\U0001f382",
            "\U0001f381",
            "\U0001f389",
        ]
        random.shuffle(reactions)

        for reaction in reactions:
            await message.add_reaction(reaction)
        # await member.add_roles(self.birthday_role, reason="Birthday!")
        # await asyncio.sleep(24 * 3600)  # 24 hours
        # await member.remove_roles(self.birthday_role)

    @birthday.command(name="register")
    @app_commands.describe(month="Month of the year", day="Day of the month (1-31)")
    async def birthday_register(
        self,
        interaction: discord.Interaction,
        month: Month,
        day: app_commands.Range[int, 1, 31],
    ):
        """Register your birthday in this server."""

        if isinstance(interaction.user, discord.User):
            await interaction.response.send_message(
                "Cannot register a birthday in direct messages."
            )
            return

        # save year as a leap year. no need for user year of birth!
        birthday_date = datetime.date(4, month.value, day)
        next_occurence = get_next_occurence(birthday_date)
        LOGGER.debug(f"{interaction.user} registered birthday for {birthday_date}")

        await self._save_birthday(interaction.user, birthday_date)

        await interaction.response.send_message(
            f"Saved your birthday as {month.name} {day}. "
            f"See you {relative_dt(next_occurence)}!",
            ephemeral=True,
        )

    @birthday_register.error
    async def birthday_register_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        """Error handler for the birthday register subcommand."""

        error = getattr(error, "original", error)

        if isinstance(error, ValueError):
            month = interaction.namespace.month
            day = interaction.namespace.day
            LOGGER.debug(f"{day} is not in {month}")
            await interaction.response.send_message(
                f"Day {day} is out of range for month {month}",
                ephemeral=True,
            )

        else:
            interaction.extras["error_handled"] = False

    @birthday.command(name="next")
    async def birthday_next(self, interaction: discord.Interaction):
        """Display the next birthday in the server."""

        if interaction.guild is None:
            await interaction.response.send_message(
                "Cannot get a birthday in direct messages."
            )
            return

        guild_birthdays = await self._get_guild_birthdays(interaction.guild)
        # return early if there is no birthdays in the guild
        if len(guild_birthdays) == 0:
            await interaction.response.send_message(
                "No birthdays registered here, sorry!",
                ephemeral=True,
            )
            return
        next_guild_birthdays = sorted(
            guild_birthdays, key=lambda x: get_next_occurence(x.birthday)
        )
        next_birthday_date, next_birthdays = next(
            itertools.groupby(next_guild_birthdays, key=lambda x: x.birthday)
        )
        next_birthday = get_next_occurence(next_birthday_date)
        next_birthday_members = [
            await interaction.guild.fetch_member(bday.user_id)
            for bday in next_birthdays
        ]
        LOGGER.debug(
            f"Next birthday(s) on {next_birthday} for "
            f"{len(next_birthday_members)} members"
        )

        embed = (
            discord.Embed(
                description="# Next Birthday Celebration",
                color=EMBED_COLOR,
            )
            .add_field(
                name="Members",
                value="\n".join(
                    [
                        f"{member.display_name} ({member.mention})"
                        for member in next_birthday_members
                        if member is not None
                    ]
                ),
            )
            .add_field(
                name="Date",
                value=(
                    f"{format_dt(next_birthday, style='D')} "
                    f"({relative_dt(next_birthday)})"
                ),
                inline=False,
            )
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @birthday.command(name="celebrate")
    @app_commands.checks.has_permissions(mention_everyone=True)
    @app_commands.describe(member="The person whose birthday is today!")
    async def birthday_celebrate(
        self, interaction: discord.Interaction, member: discord.Member
    ):
        """Celebrate a member's birthday!"""

        asyncio.create_task(self.birthday_task(member))
        await interaction.response.send_message(
            f"Thank you for celebrating {member.mention}!", ephemeral=True
        )

    @birthday_celebrate.error
    async def birthday_celebrate_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        """Error handler for the birthday celebrate subcommand."""

        error = getattr(error, "original", error)

        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You are missing permissions for this command "
                f"({', '.join(error.missing_permissions)})",
                ephemeral=True,
            )

        else:
            interaction.extras["error_handled"] = False

    @birthday.command(name="delete")
    async def birthday_delete(self, interaction: discord.Interaction):
        """Delete your registered birthday."""

        if isinstance(interaction.user, discord.User):
            await interaction.response.send_message(
                "Cannot delete a birthday in direct messages."
            )
            return

        birthday = await self._get_member_birthday(interaction.user)
        LOGGER.debug(f"Retreived birthday is {birthday}")

        if birthday is None:
            await interaction.response.send_message(
                "You did not register a birthday here, so nothing to delete!",
                ephemeral=True,
            )
            return

        confirm = await confirm_prompt(
            interaction,
            "Are you sure you want to delete your birthday? "
            "You can register it again later.",
        )

        if confirm.value is None:
            LOGGER.debug("Confirmation timed out.")
            await interaction.followup.send("Confirmation timed out.", ephemeral=True)
            return

        if confirm.value:
            LOGGER.debug(
                f"Deleting birthday for {interaction.user} in {interaction.guild}"
            )
            await self._delete_birthday(interaction.user)
            content = "Deleting your birthday!"

        else:
            next_occurence = get_next_occurence(birthday.birthday)
            content = f"Keeping your birthday. See you {relative_dt(next_occurence)}!"

        await confirm.interaction.response.send_message(content, ephemeral=True)

    async def _create_tables(self):
        """Create the necessary DB tables if they do not exist."""

        await self.bot.db.execute(read_sql_query(SQL / "create_tables.sql"))

        await self.bot.db.commit()

    async def _get_guild_birthdays(self, guild: discord.Guild) -> list[Birthday]:
        """Get a guild's birthdays."""

        rows = await self.bot.db.execute_fetchall(
            read_sql_query(SQL / "get_guild_birthdays.sql"),
            dict(guild_id=guild.id),
        )

        return [Birthday(**row) for row in rows]

    async def _get_member_birthday(self, member: discord.Member) -> Birthday | None:
        """Get a member's birthday."""

        async with self.bot.db.execute(
            read_sql_query(SQL / "get_member_birthday.sql"),
            dict(user_id=member.id, guild_id=member.guild.id),
        ) as c:
            row = await c.fetchone()

        return Birthday(**row) if row is not None else None

    async def _get_today_birthday(
        self, guild: discord.Guild | None = None
    ) -> list[Birthday]:
        """Return a list of today's birthdays.
        The list is empty is there is none.
        """
        if guild is None:
            rows = await self.bot.db.execute_fetchall(
                "SELECT * FROM announcements_birthday"
            )

        else:
            rows = await self.bot.db.execute_fetchall(
                read_sql_query(SQL / "get_guild_birthdays.sql"),
                dict(guild_id=guild.id),
            )

        birthdays = []
        today = datetime.date.today()
        for row in rows:
            birthday = Birthday(**row)
            if (
                birthday.birthday.day,
                birthday.birthday.month,
            ) == (
                today.day,
                today.month,
            ):
                birthdays.append(birthday)

        return birthdays

    async def _is_already_registered(self, member: discord.Member) -> bool:
        """Verify if a member has registered a birthday already."""

        async with self.bot.db.execute(
            read_sql_query(SQL / "is_already_registered.sql"),
            dict(user_id=member.id, guild_id=member.guild.id),
        ) as c:
            row = await c.fetchone()

        if row:
            return bool(row[0])
        return False

    async def _save_birthday(self, member: discord.Member, birthday: datetime.date):
        """Save the birthday to the database."""

        await self.bot.db.execute(
            read_sql_query(SQL / "save_birthday.sql"),
            dict(user_id=member.id, guild_id=member.guild.id, birthday=birthday),
        )
        await self.bot.db.commit()

    async def _delete_birthday(self, member: discord.Member):
        """Remove the member's birthday from the database."""

        await self.bot.db.execute(
            read_sql_query(SQL / "delete_birthday.sql"),
            dict(user_id=member.id, guild_id=member.guild.id),
        )
        await self.bot.db.commit()
