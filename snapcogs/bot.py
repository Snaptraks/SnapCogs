import logging

import aiosqlite
import aiohttp
import discord
from discord.ext import commands

LOGGER = logging.getLogger("snapcogs")
LOG_FORMAT = logging.Formatter("%(asctime)s : %(levelname)s : %(name)s : %(message)s")
LOG_HANDLER = logging.StreamHandler()
LOG_HANDLER.setFormatter(LOG_FORMAT)
LOGGER.addHandler(LOG_HANDLER)


class Bot(commands.Bot):
    def __init__(self, *args, **kwargs):
        self.db_name = kwargs.get("db_name", ":memory:")
        self.permissions = kwargs.get("permissions", discord.Permissions.text())
        self.startup_extensions = kwargs.get("startup_extensions", [])
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
        # allow for cascade deletion
        await self.db.execute("PRAGMA foreign_keys = ON")

        for extension in self.startup_extensions:
            try:
                LOGGER.debug(f"Loading {extension}... ")
                await self.load_extension(extension)
            except Exception as e:
                exc = "{}: {}".format(type(e).__name__, e)
                LOGGER.error("Failed to load {}\n{}".format(extension, exc))
            else:
                LOGGER.debug(f"{extension} loaded successfully.")

        self.boot_time = discord.utils.utcnow()

    async def close(self):
        """Subclass the close() method to close the HTTP Session."""

        await self.http_session.close()
        await self.db.close()
        await super().close()

    async def on_ready(self):
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
