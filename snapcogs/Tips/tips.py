from collections import defaultdict
import logging

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands

from . import views
from ..utils import relative_dt
from ..utils.checks import has_guild_permissions
from ..utils.views import confirm_prompt

LOGGER = logging.getLogger(__name__)


def rank_emoji(n: int):
    """Return emojis from one (gold medal) to ten.
    To be used with enumerate(), therefore index 0 returns :first_place: and index 9
    returns :ten:.
    """

    if 0 <= n <= 2:
        # :first_place: == \U0001f947 == chr(129351)
        return chr(129351 + n)

    elif 3 <= n <= 8:
        # :four: == \u0034\ufe0f\u20e3 == chr(52)\ufe0f\u20e3
        return f"{chr(52 + n - 3)}\ufe0f\u20e3"

    elif n == 9:
        return "\N{KEYCAP TEN}"

    else:
        raise ValueError


class Tips(commands.Cog):
    tip = app_commands.Group(
        name="tip", description="Save and share tips for people on the server!"
    )

    async def tip_name_autocomplete(
        self, interaction: discord.Interaction, current: str
    ):
        rows = await self._get_tips_names_like(interaction, current)
        suggestions = [
            app_commands.Choice(name=row["name"], value=row["name"])
            for row in rows[:25]
        ]
        LOGGER.debug(
            f"tip_name_autocomplete: {current=}, {len(suggestions)} suggestions"
        )
        return suggestions

    async def tip_name_from_author_autocomplete(
        self, interaction: discord.Interaction, current: str
    ):
        rows = await self._get_tips_names_like(interaction, current)
        suggestions = [
            app_commands.Choice(name=row["name"], value=row["name"])
            for row in rows
            if row["author_id"] == interaction.user.id
        ][:25]
        LOGGER.debug(
            f"tip_name_from_author_autocomplete: {current=}, "
            f"{len(suggestions)} suggestions"
        )
        return suggestions

    def __init__(self, bot) -> None:
        self.bot = bot

    async def cog_load(self):
        await self._create_tables()

    @tip.command(name="create")
    async def tip_create(self, interaction: discord.Interaction):
        """Create a new tip for the current server, owned by you."""

        LOGGER.debug(f"Creating a tip in guild {interaction.guild}.")
        modal = views.TipCreate()
        await interaction.response.send_modal(modal)
        await modal.wait()
        LOGGER.debug(f"Tip {modal.name.value!r} received.")

        payload = dict(
            author_id=interaction.user.id,
            content=modal.content.value,
            created_at=interaction.created_at,
            guild_id=interaction.guild.id,
            last_edited=interaction.created_at,
            name=modal.name.value,
        )

        try:
            await self._save_tip(payload)

        except aiosqlite.IntegrityError:
            # unique constraint failed
            await interaction.followup.send(
                f"There is already a tip named `{payload['name']}` here.",
                ephemeral=True,
            )

        else:
            await interaction.followup.send(
                f"Tip `{payload['name']}` created!", ephemeral=True
            )

    @tip.command(name="show")
    @app_commands.describe(name="Name of the tip.")
    @app_commands.autocomplete(name=tip_name_autocomplete)
    async def tip_show(self, interaction: discord.Interaction, name: str):
        """Show a tip in the current channel."""

        tip = await self._get_tip_by_name(interaction, name)

        if tip is None:
            await interaction.response.send_message(
                f"No tip named `{name}` here!", ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"Tip {tip['name']}",
            description=tip["content"],
            color=discord.Color.blurple(),
            timestamp=tip["last_edited"],
        )
        tip_author = interaction.guild.get_member(tip["author_id"])
        if tip_author is not None:
            embed.set_author(name=tip_author, icon_url=tip_author.display_avatar.url)

        await interaction.response.send_message(embed=embed)

        await self._increase_tip_uses(tip["tip_id"])

    @tip.command(name="edit")
    @app_commands.describe(name="Name of the tip.")
    @app_commands.autocomplete(name=tip_name_from_author_autocomplete)
    async def tip_edit(self, interaction: discord.Integration, name: str):
        """Modify the content of a tip that you own."""

        tip = await self._get_member_tip_by_name(interaction, name)

        if tip is None:
            await interaction.response.send_message(
                f"No tip named `{name}` here!", ephemeral=True
            )
            return

        LOGGER.debug(f"Editing tip {name} in {interaction.guild}")
        modal = views.TipEdit(tip)
        await interaction.response.send_modal(modal)
        await modal.wait()
        new_name = modal.name.value

        try:
            await self._edit_tip(
                dict(content=modal.content.value, name=new_name, tip_id=tip["tip_id"],)
            )

        except aiosqlite.IntegrityError:
            # unique constraint failed
            await interaction.followup.send(
                f"There is already a tip named `{new_name}` here.", ephemeral=True,
            )

        else:
            await interaction.followup.send(f"Tip `{new_name}` edited!", ephemeral=True)

    @tip.command(name="info")
    @app_commands.describe(name="Name of the tip.")
    @app_commands.autocomplete(name=tip_name_autocomplete)
    async def tip_info(self, interaction: discord.Interaction, name: str):
        """Get information about a tip."""

        tip = await self._get_tip_by_name(interaction, name)

        if tip is None:
            await interaction.response.send_message(
                f"No tip named `{name}` here!", ephemeral=True
            )
            return

        embed = (
            discord.Embed(
                title=f"Tip {tip['name']} Information", color=discord.Color.blurple(),
            )
            .add_field(
                name="Author", value=f"<@{tip['author_id']}>"
            )  # user might have left the server
            .add_field(name="Uses", value=f"`{tip['uses']}`")
            .add_field(name="Created", value=relative_dt(tip["created_at"]))
            .add_field(name="Last Edited", value=relative_dt(tip["last_edited"]))
            .add_field(name="Tip ID", value=f"`{tip['tip_id']}`")
        )
        tip_author = interaction.guild.get_member(tip["author_id"])
        if tip_author is not None:
            embed.set_author(name=tip_author, icon_url=tip_author.display_avatar.url)

        await interaction.response.send_message(embed=embed)

    @tip.command(name="raw")
    @app_commands.describe(name="Name of the tip.")
    @app_commands.autocomplete(name=tip_name_autocomplete)
    async def tip_raw(self, interaction: discord.Interaction, name: str):
        """Get the raw content of a tip, escaping markdown."""

        tip = await self._get_tip_by_name(interaction, name)

        if tip is None:
            await interaction.response.send_message(
                f"No tip named `{name}` here!", ephemeral=True
            )
            return

        raw_content = discord.utils.escape_mentions(
            discord.utils.escape_markdown(tip["content"])
        )

        embed = discord.Embed(
            title=f"Raw content of tip {tip['name']}",
            color=discord.Color.blurple(),
            description=raw_content,
        )
        await interaction.response.send_message(embed=embed)

    @tip.command(name="delete")
    @app_commands.describe(name="Name of the tip.")
    @app_commands.autocomplete(name=tip_name_from_author_autocomplete)
    async def tip_delete(self, interaction: discord.Interaction, name: str):
        """Delete a tip that you wrote."""

        bypass_author_check = (
            await self.bot.is_owner(interaction.user)
            or interaction.user.guild_permissions.manage_messages
        )

        if bypass_author_check:
            # can delete tips not owned
            tip = await self._get_tip_by_name(interaction, name)

        else:
            # can only delete own tip
            tip = await self._get_member_tip_by_name(interaction, name)

        if tip is None:
            await interaction.response.send_message(
                f"No tip named `{name}` here!", ephemeral=True
            )
            return

        await self._delete_tip(tip["tip_id"])
        await interaction.response.send_message(
            f"Tip {name} successfully deleted.", ephemeral=True
        )

    @tip.command(name="purge")
    @app_commands.describe(member="The author of the tips to delete.")
    @has_guild_permissions(manage_messages=True)
    async def tip_purge(self, interaction: discord.Interaction, member: discord.Member):
        """Delete all tips from the given member in this server."""

        tips_count = await self._count_member_tips(member)
        if tips_count == 0:
            await interaction.response.send_message(
                f"{member.mention} does not have any tips on this server.",
                ephemeral=True,
            )
            return

        confirm = await confirm_prompt(
            interaction, f"Purging {tips_count} tips from {member.mention}?"
        )
        if not confirm:
            # send cancelation message within the view
            return

        await self._delete_member_tips(member)
        await interaction.followup.send(
            f"Purged {tips_count} tips from {member.mention}.", ephemeral=True
        )

    @tip_purge.error
    async def tip_purge_error(
        self, interaction: discord.Interaction, error: BaseException
    ):
        """Error handler for the tip purge command."""

        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(error, ephemeral=True)

        else:
            interaction.extras["error_handled"] = False

    @tip.command(name="transfer")
    @app_commands.describe(
        name="Name of the tip.", member="Member to transfer the tip to."
    )
    @app_commands.autocomplete(name=tip_name_from_author_autocomplete)
    async def tip_transfer(
        self, interaction: discord.Interaction, name: str, member: discord.Member
    ):
        """Transfer tip ownership to another member."""

        if member.bot or (interaction.user.id == member.id):
            await interaction.response.send_message(
                "Cannot transfer ownership of the tip to this member.", ephemeral=True
            )
            return

        tip = await self._get_member_tip_by_name(interaction, name)

        if tip is None:
            await interaction.response.send_message(
                f"No tip named `{name}` here!", ephemeral=True
            )
            return

        await self._edit_tip(dict(author_id=member.id, tip_id=tip["tip_id"]))
        await interaction.response.send_message(
            f"Transferring tip `{name}` to {member.mention}",
        )
        LOGGER.debug(f"Tip {name} transfered to {member}")

    @tip.command(name="claim")
    @app_commands.describe(name="Name of the tip.")
    @app_commands.autocomplete(name=tip_name_autocomplete)
    async def tip_claim(self, interaction: discord.Interaction, name: str):
        """Claim a tip where the author has left the server."""

        tip = await self._get_tip_by_name(interaction, name)

        if tip is None:
            await interaction.response.send_message(
                f"No tip named `{name}` here!", ephemeral=True
            )
            return

        member = interaction.guild.get_member(tip["author_id"])
        if member is not None:
            await interaction.response.send_message(
                "The tip author is still in the server.", ephemeral=True
            )
            return

        # all checks passed, claiming the tip
        await self._edit_tip(dict(author_id=interaction.user.id, tip_id=tip["tip_id"]))
        await interaction.response.send_message(
            f"Claiming tip `{name}` for yourself.", ephemeral=True
        )
        LOGGER.debug(f"Tip {name} claimed by {interaction.user}")

    @tip.command(name="list")
    @app_commands.describe(member="Author of the tips.")
    async def tip_list(
        self, interaction: discord.Interaction, member: discord.Member = None
    ):
        """List all the tips that you, or someone else, wrote."""

        if member is None:
            member = interaction.user

        tips = await self._get_member_tips(member)
        LOGGER.debug(f"Listing {len(tips)} tips for {interaction.guild.name}")

        if tips:
            # todo: have a paginated version
            embed = discord.Embed(
                title="List of Tips",
                color=discord.Color.blurple(),
                description="\n".join(tip["name"] for tip in tips),
            ).set_author(name=member.display_name, icon_url=member.display_avatar.url)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(
                f"Member {member} did not write any tips.", ephemeral=True
            )

    @tip.command(name="all")
    async def tip_all(self, interaction: discord.Interaction):
        """List all the tips from this server."""

        tips = await self._get_guild_tips(interaction.guild)
        LOGGER.debug(f"Listing {len(tips)} tips for {interaction.guild.name}")

        if tips:
            max_id_length = max(len(str(tip["tip_id"])) for tip in tips)
            # todo: have a paginated version
            embed = discord.Embed(
                title="List of Tips",
                color=discord.Color.blurple(),
                description="\n".join(
                    (
                        f"`{tip['tip_id']:>{max_id_length}d}` {tip['name']} "
                        f"({interaction.guild.get_member(tip['author_id'])})"
                    )
                    for tip in tips
                ),
            ).set_author(
                name=interaction.guild.name,
                icon_url=getattr(interaction.guild.icon, "url", ""),
            )
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(
                "There are no tips here.", ephemeral=True
            )

    async def tip_stats_guild(self, guild: discord.Guild):
        """Build the embed for guild statistics."""

        embed = (
            discord.Embed(title="Server Tips Statistics", color=discord.Color.blurple())
            .set_author(
                name=guild.name,
                icon_url=(
                    guild.icon.url
                    if guild.icon
                    else "https://cdn.discordapp.com/embed/avatars/1.png"
                ),
            )
            .set_footer(text="Server-wide statistics")
        )

        # total tips
        # total tip uses
        totals = await self._get_guild_totals(guild)
        embed.add_field(name="Total Tips", value=totals["total_tips"])
        embed.add_field(name="Total Tip Uses", value=totals["total_uses"])

        # top 3 tips most used
        top_tips = await self._get_guild_top_tips(guild)
        embed.add_field(
            name="Top Tips",
            value="\n".join(
                (
                    f"{rank_emoji(n)}: {tip['name']} "
                    f"(<@{tip['author_id']}>, {tip['uses']} uses)"
                )
                for n, tip in enumerate(top_tips)
            ),
            inline=False,
        )

        # top 3 authors (most written tips)
        top_authors = await self._get_guild_top_authors(guild)
        embed.add_field(
            name="Top Tip Authors",
            value="\n".join(
                f"{rank_emoji(n)}: <@{author['author_id']}> ({author['tips']} tips)"
                for n, author in enumerate(top_authors)
            ),
            inline=False,
        )

        return embed

    async def tip_stats_member(self, member: discord.Member):
        """Build the embed for member statistics."""

        embed = (
            discord.Embed(title="Member Tips Statistics", color=discord.Color.blurple())
            .set_author(name=member, icon_url=member.display_avatar.url)
            .set_footer(text=f"Statistics for server {member.guild.name}")
        )

        # tips owned
        # tip owned uses
        totals = await self._get_member_totals(member)
        embed.add_field(name="Total Tips", value=totals["total_tips"])
        embed.add_field(name="Total Tip Uses", value=totals["total_uses"])

        # top 3 tips most used
        top_tips = await self._get_member_top_tips(member)
        embed.add_field(
            name="Top Tips",
            value="\n".join(
                f"{rank_emoji(n)}: {tip['name']} ({tip['uses']} uses)"
                for n, tip in enumerate(top_tips)
            ),
            inline=False,
        )

        return embed

    @tip.command(name="stats")
    @app_commands.describe(member="Statistics of the member, or server if ommited.")
    async def tip_stats(
        self, interaction: discord.Interaction, member: discord.Member = None
    ):
        """Get statistics for a member or the whole server."""

        if member is None:
            # guild stats
            embed = await self.tip_stats_guild(interaction.guild)
            LOGGER.debug(f"Sending tip stats for guild {interaction.guild.name}")
        else:
            # member stats
            embed = await self.tip_stats_member(member)
            LOGGER.debug(
                f"Sending tip stats for member {member} in {member.guild.name}"
            )

        await interaction.response.send_message(embed=embed)

    async def _create_tables(self):
        """Create the necessary database tables."""

        await self.bot.db.execute(
            """
            CREATE TABLE IF NOT EXISTS tips_tip(
                author_id   INTEGER  NOT NULL,
                content     TEXT     NOT NULL,
                created_at  DATETIME NOT NULL,
                guild_id    INTEGER  NOT NULL,
                last_edited DATETIME NOT NULL,
                name        TEXT     NOT NULL,
                tip_id      INTEGER  NOT NULL PRIMARY KEY,
                uses        INTEGER  DEFAULT 0 NOT NULL,
                UNIQUE(guild_id, name)
            )
            """,
        )
        await self.bot.db.commit()

    async def _save_tip(self, payload):
        """Save a tip to the database."""

        await self.bot.db.execute(
            """
            INSERT INTO tips_tip(
                author_id,
                content,
                created_at,
                guild_id,
                last_edited,
                name
            )
            VALUES (
                :author_id,
                :content,
                :created_at,
                :guild_id,
                :last_edited,
                :name
            )
            """,
            payload,
        )
        await self.bot.db.commit()
        LOGGER.debug(f"Tip {payload['name']} saved.")

    async def _edit_tip(self, payload):
        """Edit a tip in the database."""

        payload["last_edited"] = discord.utils.utcnow()

        await self.bot.db.execute(
            """
            UPDATE tips_tip
               SET author_id=COALESCE(:author_id, author_id),
                   content=COALESCE(:content, content),
                   last_edited=COALESCE(:last_edited, last_edited),
                   name=COALESCE(:name, name)
             WHERE tip_id=:tip_id
            """,
            defaultdict(lambda: None, payload),
        )
        await self.bot.db.commit()
        LOGGER.debug(f"Tip {payload['tip_id']} edited.")

    async def _get_tip_by_name(self, interaction: discord.Interaction, name: str):
        """Get a tip by its name in the current guild."""

        async with self.bot.db.execute(
            """
            SELECT *
              FROM tips_tip
             WHERE guild_id=:guild_id
               AND name=:name
            """,
            dict(guild_id=interaction.guild.id, name=name),
        ) as c:
            row = await c.fetchone()

        if row:
            LOGGER.debug(f"Found tip {row['name']} for guild {row['guild_id']}")

        return row

    async def _get_member_tip_by_name(
        self, interaction: discord.Interaction, name: str
    ):
        """Get a tip by its name in the current guild, owned by a given member."""

        async with self.bot.db.execute(
            """
            SELECT *
              FROM tips_tip
             WHERE author_id=:author_id
               AND guild_id=:guild_id
               AND name=:name
            """,
            dict(
                author_id=interaction.user.id, guild_id=interaction.guild.id, name=name
            ),
        ) as c:
            row = await c.fetchone()

        if row:
            LOGGER.debug(
                f"Found tip {row['name']} "
                f"for member {row['author_id']} "
                f"and guild {row['guild_id']}."
            )

        return row

    async def _get_tips_names_like(
        self, interaction: discord.Interaction, substring: str
    ):
        """Get a list of tip names that contain substring."""

        return await self.bot.db.execute_fetchall(
            """
            SELECT author_id, name
              FROM tips_tip
             WHERE INSTR(name, :substring) > 0
               AND guild_id=:guild_id
            """,
            dict(substring=substring, guild_id=interaction.guild.id),
        )

    async def _get_member_tips(self, member: discord.Member):
        """Get all tips owned by a member in a specific server."""

        return await self.bot.db.execute_fetchall(
            """
            SELECT name, tip_id
              FROM tips_tip
             WHERE author_id=:author_id
               AND guild_id=:guild_id
             ORDER BY name
            """,
            dict(author_id=member.id, guild_id=member.guild.id),
        )

    async def _count_member_tips(self, member: discord.Member):
        """Return the amount of tips owned by a member in a specific server."""

        async with self.bot.db.execute(
            """
            SELECT COUNT(*) AS count
              FROM tips_tip
             WHERE author_id=:author_id
               AND guild_id=:guild_id
            """,
            dict(author_id=member.id, guild_id=member.guild.id),
        ) as c:
            row = await c.fetchone()

        return row["count"]  # should be 0 or higher

    async def _get_guild_tips(self, guild: discord.Guild):
        """Get all tips saved in the given server."""

        return await self.bot.db.execute_fetchall(
            """
            SELECT *
              FROM tips_tip
             WHERE guild_id=:guild_id
             ORDER BY name
            """,
            dict(guild_id=guild.id),
        )

    async def _get_guild_totals(self, guild: discord.Guild):
        """Get count of tips and total uses for the given server."""

        async with self.bot.db.execute(
            """
            SELECT COUNT(*) AS total_tips,
                   SUM(uses) AS total_uses
              FROM tips_tip
             WHERE guild_id=:guild_id
            """,
            dict(guild_id=guild.id),
        ) as c:
            row = await c.fetchone()

        return row

    async def _get_guild_top_tips(self, guild: discord.Guild, amount: int = 3):
        """Get the top tips by uses for the given server."""

        return await self.bot.db.execute_fetchall(
            """
            SELECT author_id, name, uses
              FROM tips_tip
             WHERE guild_id=:guild_id
             ORDER BY uses DESC
             LIMIT :amount
            """,
            dict(amount=amount, guild_id=guild.id),
        )

    async def _get_guild_top_authors(self, guild: discord.Guild, amount: int = 3):
        """Get the top tip authors by number of tips for the given server."""

        return await self.bot.db.execute_fetchall(
            """
            SELECT COUNT(*) as tips, author_id
              FROM tips_tip
             WHERE guild_id=:guild_id
             GROUP BY author_id
             ORDER BY tips DESC
             LIMIT :amount
            """,
            dict(amount=amount, guild_id=guild.id),
        )

    async def _get_member_totals(self, member: discord.Member):
        """Get count of tips and total uses from the given member."""

        async with self.bot.db.execute(
            """
            SELECT COUNT(*) AS total_tips,
                   SUM(uses) AS total_uses
              FROM tips_tip
             WHERE author_id=:author_id
               AND guild_id=:guild_id
            """,
            dict(author_id=member.id, guild_id=member.guild.id),
        ) as c:
            row = await c.fetchone()

        return row

    async def _get_member_top_tips(self, member: discord.Member, amount=3):
        """Get the top tips by uses from the given member."""

        return await self.bot.db.execute_fetchall(
            """
            SELECT name, uses
              FROM tips_tip
             WHERE author_id=:author_id
               AND guild_id=:guild_id
             ORDER BY uses DESC
             LIMIT :amount
            """,
            dict(amount=amount, author_id=member.id, guild_id=member.guild.id),
        )

    async def _increase_tip_uses(self, tip_id: int):
        """Increase the use of tip with tip_id by 1."""

        await self.bot.db.execute(
            """
            UPDATE tips_tip
               SET uses = uses + 1
             WHERE tip_id=:tip_id
            """,
            dict(tip_id=tip_id),
        )
        await self.bot.db.commit()
        LOGGER.debug(f"Increased uses for {tip_id=}")

    async def _delete_tip(self, tip_id: int):
        """Delete a tip from the database."""

        await self.bot.db.execute(
            """
            DELETE FROM tips_tip
             WHERE tip_id=:tip_id
            """,
            dict(tip_id=tip_id),
        )
        await self.bot.db.commit()
        LOGGER.debug(f"Deleted tip with {tip_id=}")

    async def _delete_member_tips(self, member: discord.Member):
        """Delete all tips from a member, in a specific server."""

        async with self.bot.db.execute(
            """
            DELETE FROM tips_tip
             WHERE author_id=:author_id
               AND guild_id=:guild_id
            """,
            dict(author_id=member.id, guild_id=member.guild.id),
        ) as c:
            deleted = c.rowcount

        await self.bot.db.commit()
        LOGGER.debug(f"Deleted {deleted} tips from {member=}")

        return deleted
