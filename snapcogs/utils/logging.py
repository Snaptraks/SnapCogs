import logging

import discord


def get_logger(name: str | None = None) -> logging.Logger:
    logger = logging.getLogger(name)
    log_handler = logging.StreamHandler()
    if discord.utils.stream_supports_colour(log_handler.stream):
        log_format = discord.utils._ColourFormatter()
    else:
        log_format = logging.Formatter(
            "%(asctime)s : %(levelname)s : %(name)s : %(message)s"
        )
    log_handler.setFormatter(log_format)
    logger.addHandler(log_handler)
    return logger
