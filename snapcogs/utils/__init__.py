import asyncio
import datetime
from typing import LiteralString

import discord


def relative_dt(dt: datetime.datetime) -> str:
    """Format the datetime in the relative timestamp form."""

    return discord.utils.format_dt(dt, style="R")


async def run_process(command: LiteralString) -> tuple[str, str]:
    """Run a command in shell. To be used carefully!"""

    process = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    result = await process.communicate()

    return tuple(output.decode("utf-8", "ignore") for output in result)  # type: ignore


def cleanup_code(content: str) -> str:
    """Automatically remove code blocks from the code."""

    # remove ```py\n```
    if content.startswith("```") and content.endswith("```"):
        return "\n".join(content.split("\n")[1:-1])

    # remove `foo`
    return content.strip("` \n")
