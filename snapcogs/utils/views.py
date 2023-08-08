import discord
from discord import ui


# confirm view
class Confirm(ui.View):
    def __init__(self):
        super().__init__()
        self.value = None
        self.interaction: discord.Interaction | None = None

    @ui.button(
        label="Confirm",
        style=discord.ButtonStyle.green,
        emoji="\N{WHITE HEAVY CHECK MARK}",
    )
    async def on_confirm(self, interaction: discord.Interaction, button: ui.Button):
        self.interaction = interaction
        self.value = True
        self.stop()

    @ui.button(
        label="Cancel",
        style=discord.ButtonStyle.gray,
        emoji="\N{CROSS MARK}",
    )
    async def on_cancel(self, interaction: discord.Interaction, button: ui.Button):
        self.interaction = interaction
        self.value = False
        self.stop()

    def __bool__(self) -> bool:
        ...


# confirm prompt
async def confirm_prompt(
    interaction: discord.Interaction, content: str | None = None
) -> Confirm:
    """Send a confirmation prompt to the user, and return the Confirm View where
    you can access the resulting interaction and view.confirm boolean.
    """
    confirm = Confirm()
    await interaction.response.send_message(content, view=confirm, ephemeral=True)
    await confirm.wait()

    return confirm
