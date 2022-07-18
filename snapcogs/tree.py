import logging

import discord
from discord import app_commands

LOGGER = logging.getLogger(__name__)


class CommandTree(app_commands.CommandTree):
    async def on_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
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

        if (command and not command._has_any_error_handlers()) or not error_handled:
            LOGGER.error(
                f"Ignoring exception in command {repr(command.name)}", exc_info=error,
            )
        else:
            LOGGER.error("Ignoring exception in command tree", exc_info=error)
