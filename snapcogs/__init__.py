import logging

import discord

from snapcogs.bot import Bot  # noqa: F401


LOGGER = logging.getLogger("snapcogs")
LOG_HANDLER = logging.StreamHandler()
if discord.utils.stream_supports_colour(LOG_HANDLER.stream):
    LOG_FORMAT = discord.utils._ColourFormatter()
else:
    LOG_FORMAT = logging.Formatter(
        "%(asctime)s : %(levelname)s : %(name)s : %(message)s"
    )
LOG_HANDLER.setFormatter(LOG_FORMAT)
LOGGER.addHandler(LOG_HANDLER)
