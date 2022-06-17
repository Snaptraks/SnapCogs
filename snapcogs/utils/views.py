import discord
from discord import ui

# confirm view
class Confirm(ui.View):
    def __init__(self):
        super().__init__()
        self.confirm = None

    @ui.button(
        label="Confirm",
        style=discord.ButtonStyle.green,
        emoji="\N{WHITE HEAVY CHECK MARK}",
    )
    async def on_confirm(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("You confirmed!", ephemeral=True)
        self.confirm = True
        self.stop()

    @ui.button(
        label="Cancel", style=discord.ButtonStyle.gray, emoji="\N{CROSS MARK}",
    )
    async def on_cancel(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("You cancelled!", ephemeral=True)
        self.confirm = False
        self.stop()


# confirm prompt
async def confirm_prompt(interaction: discord.Interaction, content: str = None) -> bool:
    """Send a confirmation prompt to the user, and return a bool."""

    view = Confirm()
    await interaction.response.send_message(content, view=view, ephemeral=True)
    await view.wait()

    return view.confirm
