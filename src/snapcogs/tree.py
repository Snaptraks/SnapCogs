import logging
from datetime import timedelta

import discord
from discord import app_commands

LOGGER = logging.getLogger(__name__)


class CommandTree(app_commands.CommandTree):
    async def on_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        """Error handler that sends unhandled errors to the logger.

        To make sure errors are logged here even when application commands have
        an error handler, you should use the following pattern for the handler:

        ```py
        async def error_handler(interaction: discord.Interaction, error: Exception):
            if isinstance(error, ...):
                # do something here
            elif isinstance(error, ...):
                # for another type of exception
            else:
                # this is the important part
                interaction.extras["error_handled"] = False
        ```
        """
        command = interaction.command
        # assume the error is handled by default, unless explicitely set to False
        error_handled = interaction.extras.get("error_handled", True)

        if (
            command is None
            or (command and not command._has_any_error_handlers())
            or not error_handled
        ):
            # special case when command is on cooldown
            if isinstance(error, app_commands.CommandOnCooldown):
                await self._on_cooldown(interaction, error)
            else:
                LOGGER.error(
                    f"Ignoring exception in command ({interaction.data['name']})",  # type: ignore[not-none]
                    exc_info=error,
                )
        else:
            LOGGER.debug("Exception in command tree was already handled")

    async def _on_cooldown(
        self, interaction: discord.Interaction, error: app_commands.CommandOnCooldown
    ) -> None:
        retry_in = discord.utils.format_dt(
            discord.utils.utcnow() + timedelta(seconds=error.retry_after),
            style="R",
        )
        embed = discord.Embed(
            color=discord.Color.red(),
            title=f"Command `/{interaction.data['name']}` is on cooldown!",  # type: ignore[not-none]
            description=f"Try again {retry_in}.",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
