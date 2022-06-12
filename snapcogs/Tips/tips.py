import discord
from discord import app_commands
from discord.ext import commands


class Tips(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(name="tip")
    async def tip(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            'You can use the "/" character to list available commands!', ephemeral=True
        )

