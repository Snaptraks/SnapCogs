import asyncio
import discord


def relative_dt(dt):
    """Format the datetime in the relative timestamp form."""

    return discord.utils.format_dt(dt, style="R")


async def run_process(command):
    """Run a command in shell. To be used carefully!"""

    process = await asyncio.create_subprocess_shell(
        command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    result = await process.communicate()

    return [output.decode("utf-8", "ignore") for output in result]
