import discord
from discord import ui


class TipCreate(ui.Modal, title="Tip Creation"):
    name = ui.TextInput(label="Name", placeholder="How do you want to name your tip?")
    content = ui.TextInput(
        label="content",
        placeholder="What is your tip about?",
        style=discord.TextStyle.paragraph,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"Tip `{self.name}` created!", ephemeral=True
        )
