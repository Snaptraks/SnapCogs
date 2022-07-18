import logging

import discord
from discord import app_commands

LOGGER = logging.getLogger(__name__)


class CommandTree(app_commands.CommandTree):
    async def on_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        command = interaction.command
        error_handled = interaction.extras.get("error_handled", True)

        if command is not None:
            if command._has_any_error_handlers() and not error_handled:
                LOGGER.error(
                    f"Ignoring exception in command {repr(command.name)}",
                    exc_info=error,
                )
            else:
                return
        else:
            LOGGER.error("Ignoring exception in command tree", exc_info=error)
