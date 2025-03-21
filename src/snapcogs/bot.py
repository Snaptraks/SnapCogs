import logging
import sys

import aiohttp
import discord
from discord.ext import commands

from .database import Database
from .tree import CommandTree

LOGGER = logging.getLogger(__name__)


class Bot(commands.Bot):
    def __init__(self, *args, **kwargs):
        self.db_name = kwargs.get("db_name", None)
        self.permissions = kwargs.get("permissions", discord.Permissions.text())
        self.startup_extensions = kwargs.get("startup_extensions", [])
        kwargs["tree_cls"] = kwargs.get("tree_cls", CommandTree)
        super().__init__(*args, **kwargs)

    async def setup_hook(self):
        # Create HTTP session
        self.http_session = aiohttp.ClientSession()

        # Make DB connection
        self.db = Database(self.db_name)

        for extension in self.startup_extensions:
            try:
                LOGGER.debug(f"Loading {extension}... ")
                await self.load_extension(extension)
            except Exception as error:
                LOGGER.error(error, exc_info=error)
            else:
                LOGGER.debug(f"{extension} loaded successfully.")

        await self.db.initialise_database()

        self.boot_time = discord.utils.utcnow()

    async def close(self):
        """Subclass the close() method to close the HTTP Session."""

        await self.http_session.close()
        await self.db.engine.dispose()
        await super().close()

    async def on_ready(self):
        if self.user is None:
            # everything below assumes self.user is not None, so we return
            # early if it is
            return
        oauth_url = discord.utils.oauth_url(self.user.id, permissions=self.permissions)
        py_version = sys.version_info
        LOGGER.info(
            "\n".join(
                [
                    "Login Info",
                    f"Logged in as {self.user.name} (ID:{self.user.id})",
                    "--------",
                    "Versions:",
                    f"\tPython: {py_version.major}.{py_version.minor}.{py_version.micro}",
                    f"\tdiscord.py: {discord.__version__}",
                    "--------",
                    f"Use this link to invite {self.user.name}:",
                    f"{oauth_url}",
                    "--------",
                ]
            )
        )

    async def on_command_error(
        self, ctx: commands.Context, exception: commands.CommandError, /
    ) -> None:
        """Default error handler.

        To make sure errors are logged here even when commands have an error
        handler, you should use the following pattern for the handler:

        ```py
        async def error_handler(ctx: commands.Context, error: Exception):
            if isinstance(error, ...):
                # do something here
            elif isinstance(error, ...):
                # for another type of exception
            else:
                # this is the important part
                ctx.error_handled = False
        ```
        """
        if self.extra_events.get("on_command_error", None):
            # do nothing if user has an on_command_error event registered
            return

        error_handled = getattr(ctx, "error_handled", True)
        command = ctx.command
        cog = ctx.cog
        if (
            command is None
            or (  # if no error handler defined
                (command and not command.has_error_handler())
                and (cog and not cog.has_error_handler())
            )
            or not error_handled  # or the error is not handled
        ):
            LOGGER.error(
                f"Exception {exception} raised in {command}", exc_info=exception
            )
        else:
            LOGGER.debug(f"Exception in command {command} was already handled")

    async def get_or_fetch_member(
        self, guild: discord.Guild, member_id: int
    ) -> discord.Member | None:
        """Look up a member in cache, or fetches if not found."""

        member = guild.get_member(member_id)
        if member is not None:
            return member

        members = await guild.query_members(limit=1, user_ids=[member_id])

        if len(members) == 0:
            return None

        return members[0]
