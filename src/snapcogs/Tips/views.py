import discord
from discord import ui

from .models import Tip


class TipCreate(ui.Modal, title="Tip Creation"):
    name = ui.TextInput(label="Name", placeholder="How do you want to name your tip?")
    content = ui.TextInput(
        label="content",
        placeholder="What is your tip about?",
        style=discord.TextStyle.paragraph,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()


class TipEdit(TipCreate, title="Tip Edit"):
    def __init__(self, tip: Tip) -> None:
        super().__init__()
        self.name.default = tip.name
        self.content.default = tip.content
