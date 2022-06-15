from collections import defaultdict
import logging

import discord
from discord import app_commands
from discord.ext import commands

from . import views
from ..utils import relative_dt

LOGGER = logging.getLogger(__name__)


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
        await self._save_tip(payload)

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

        tip_author = interaction.guild.get_member(tip["author_id"])
        embed = discord.Embed(
            title=f"Tip {tip['name']}",
            description=tip["content"],
            color=discord.Color.blurple(),
            timestamp=tip["last_edited"],
        ).set_author(name=tip_author, icon_url=tip_author.display_avatar.url)

        await interaction.response.send_message(embed=embed)

        await self._increase_tip_uses(tip["tip_id"])

    @tip.command(name="edit")
    @app_commands.describe(name="Name of the tip.")
    @app_commands.autocomplete(name=tip_name_autocomplete)
    async def tip_edit(self, interaction: discord.Integration, name: str):
        """Modify the content of a tip that you own."""

        LOGGER.debug(f"Editing tip {name} in {interaction.guild}")
        tip = await self._get_member_tip_by_name(interaction, name)

        if tip is None:
            await interaction.response.send_message(
                f"No tip named `{name}` here!", ephemeral=True
            )
            return

        modal = views.TipEdit(tip)
        await interaction.response.send_modal(modal)
        await modal.wait()

        payload = dict(
            content=modal.content.value,
            name=modal.name.value,
            last_edited=interaction.created_at,
            tip_id=tip["tip_id"],
        )
        await self._edit_tip(payload)

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

        tip_author = interaction.guild.get_member(tip["author_id"])
        embed = (
            discord.Embed(
                title=f"Tip {tip['name']} Information", color=discord.Color.blurple(),
            )
            .set_author(name=tip_author, icon_url=tip_author.display_avatar.url)
            .add_field(name="Author", value=tip_author.mention)
            .add_field(name="Uses", value=tip["uses"])
            .add_field(name="Created", value=relative_dt(tip["created_at"]))
            .add_field(name="Last Edited", value=relative_dt(tip["last_edited"]))
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
            INSERT INTO tips_tip(author_id,
                                 content, 
                                 created_at, 
                                 guild_id, 
                                 last_edited,
                                 name)
            VALUES (:author_id,
                    :content,
                    :created_at,
                    :guild_id,
                    :last_edited,
                    :name)
            """,
            payload,
        )
        await self.bot.db.commit()
        LOGGER.debug(f"Tip {payload['name']} saved.")

    async def _edit_tip(self, payload):
        """Edit a tip in the database."""

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
            LOGGER.debug(f"Found tip {row['name']} for guild {row['guild_id']}.")

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
            SELECT name
              FROM tips_tip
             WHERE INSTR(name, :substring) > 0
               AND guild_id=:guild_id
            """,
            dict(substring=substring, guild_id=interaction.guild.id),
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
