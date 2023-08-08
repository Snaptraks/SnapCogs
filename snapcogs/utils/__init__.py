import asyncio
import datetime

import discord


def relative_dt(dt: datetime.datetime) -> str:
    """Format the datetime in the relative timestamp form."""

    return discord.utils.format_dt(dt, style="R")


async def run_process(command):
    """Run a command in shell. To be used carefully!"""

    process = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    result = await process.communicate()

    return [output.decode("utf-8", "ignore") for output in result]


def cleanup_code(content):
    """Automatically remove code blocks from the code."""
    # remove ```py\n```
    if content.startswith("```") and content.endswith("```"):
        return "\n".join(content.split("\n")[1:-1])

    # remove `foo`
    return content.strip("` \n")
