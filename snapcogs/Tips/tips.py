import logging

import discord
from discord import app_commands
from discord.ext import commands

from . import views

LOGGER = logging.getLogger(__name__)


class Tips(commands.Cog):
    tip = app_commands.Group(
        name="tip", description="Save and share tips for people on the server!"
    )

    def __init__(self, bot) -> None:
        self.bot = bot

    async def cog_load(self):
        await self._create_tables()

    @tip.command(name="create")
    async def create(self, interaction: discord.Interaction):
        LOGGER.debug(f"Creating a tip in guild {interaction.guild}.")
        modal = views.TipCreate()
        await interaction.response.send_modal(modal)
        await modal.wait()
        LOGGER.debug(f"Tip {modal.name.value!r} received.")

        payload = dict(
            content=modal.content.value,
            created_at=interaction.created_at,
            guild_id=interaction.guild.id,
            name=modal.name.value,
        )

        await self._save_tip(payload)

    async def _create_tables(self):
        """Create the necessary database tables."""

        await self.bot.db.execute(
            """
                CREATE TABLE IF NOT EXISTS tips_tip(
                    content    TEXT     NOT NULL,
                    created_at DATETIME NOT NULL,
                    guild_id   INTEGER  NOT NULL,
                    name       TEXT     NOT NULL,
                    tip_id     INTEGER  NOT NULL PRIMARY KEY,
                    uses       INTEGER  DEFAULT 0 NOT NULL
                )
                """,
        )

        await self.bot.db.commit()

    async def _save_tip(self, payload):
        """Save a tip to the database."""

        await self.bot.db.execute(
            """
            INSERT INTO tips_tip(content, 
                                 created_at, 
                                 guild_id, 
                                 name)
            VALUES (:content,
                    :created_at,
                    :guild_id,
                    :name)
            """,
            payload,
        )
        LOGGER.debug(f"Tip {payload['name']} saved.")
        await self.bot.db.commit()
