from datetime import datetime, date
import logging

import aiosqlite
import aiohttp
import discord
from discord.ext import commands

from .tree import CommandTree

LOGGER = logging.getLogger(__name__)


def _decode_datetime(s):
    return datetime.fromisoformat(s.decode())


def _decode_date(s):
    return date.fromisoformat(s.decode())


class Bot(commands.Bot):
    def __init__(self, *args, **kwargs):
        self.db_name = kwargs.get("db_name", ":memory:")
        self.permissions = kwargs.get("permissions", discord.Permissions.text())
        self.startup_extensions = kwargs.get("startup_extensions", [])
        kwargs["tree_cls"] = kwargs.get("tree_cls", CommandTree)
        super().__init__(*args, **kwargs)

    async def setup_hook(self):
        # Create HTTP session
        self.http_session = aiohttp.ClientSession()

        # Make DB connection
        self.db = await aiosqlite.connect(self.db_name, detect_types=1)
        # allow for name-based access of data columns
        self.db.row_factory = aiosqlite.Row
        # register boolean type for database
        aiosqlite.register_adapter(bool, int)
        aiosqlite.register_converter("BOOLEAN", lambda v: bool(int(v)))
        # register aware datetime type for database
        aiosqlite.register_adapter("DATETIME", lambda dt: dt.isoformat)
        aiosqlite.register_converter("DATETIME", _decode_datetime)
        aiosqlite.register_converter("TIMESTAMP", _decode_datetime)
        # register date format
        aiosqlite.register_adapter("DATE", lambda date: date.isoformat)
        aiosqlite.register_converter("DATE", _decode_date)
        # allow for cascade deletion
        await self.db.execute("PRAGMA foreign_keys = ON")

        for extension in self.startup_extensions:
            try:
                LOGGER.debug(f"Loading {extension}... ")
                await self.load_extension(extension)
            except Exception as error:
                LOGGER.error(error, exc_info=error)
            else:
                LOGGER.debug(f"{extension} loaded successfully.")

        self.boot_time = discord.utils.utcnow()

    async def close(self):
        """Subclass the close() method to close the HTTP Session."""

        await self.http_session.close()
        await self.db.close()
        await super().close()

    async def on_ready(self):
        if self.user is None:
            # everything below assumes self.user is not None, so we return
            # early if it is
            return
        oauth_url = discord.utils.oauth_url(self.user.id, permissions=self.permissions)
        LOGGER.info(
            f"Logged in as {self.user.name} | discord.py version {discord.__version__}"
        )
        print(
            f"Logged in as {self.user.name} (ID:{self.user.id})\n"
            "--------\n"
            f"Current discord.py version: {discord.__version__}\n"
            "--------\n"
            f"Use this link to invite {self.user.name}:\n"
            f"{oauth_url}\n"
            "--------"
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
