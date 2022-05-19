import discord
from discord import app_commands
from discord.ext import commands

from . import views


class Poll(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    poll = app_commands.Group(name="poll", description="Create a poll")

    @poll.command(name="single")
    async def poll_single(self, interaction: discord.Interaction):
        """Create a single choice poll."""

        await self._poll_callback(interaction, views.PollCreate(), max_values=1)

    @poll.command(name="multiple")
    @app_commands.describe(max_answers="The maximum choices a user can select")
    async def poll_multiple(
        self,
        interaction: discord.Interaction,
        max_answers: app_commands.Range[int, 2, 25] = 25,
    ):
        """Create a multiple choice poll."""

        await self._poll_callback(
            interaction, views.PollCreate(), max_values=max_answers
        )

    @poll.command(name="yes-no")
    async def poll_yes_no(self, interaction: discord.Interaction):
        """Create a "Yes or No" poll."""

        await self._poll_callback(interaction, views.PollYesNoCreate(), max_values=1)

    async def _poll_callback(
        self,
        interaction: discord.Interaction,
        modal: discord.ui.Modal,
        *,
        max_values: int
    ):
        """Callback for poll creation and sending to the channel."""

        await interaction.response.send_modal(modal)
        await modal.wait()

        options = modal.options.value.split("\n")
        max_values = min(max_values, len(options))

        view = views.PollInput(
            author=interaction.user, modal=modal, max_values=max_values
        )
        embed, graph = await view.build_embed()

        await interaction.followup.send(
            embed=embed, file=graph, view=view,
        )
