import re
import unicodedata

import discord
from discord import app_commands
from discord.ext import commands

from ..bot import Bot


class Development(commands.Cog):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @app_commands.command()
    @app_commands.describe(
        characters="Characters to get the unicode representation of.",
    )
    async def charinfo(self, interaction: discord.Interaction, characters: str):
        """Show information on up to 25 unicode characters.

        Adapted from
        https://github.com/python-discord/bot/blob/master/bot/cogs/utils.py
        """
        match = re.match(r"<(a?):(\w+):(\d+)>", characters)
        if match:
            embed = discord.Embed(
                title="Non-Character Detected",
                description=(
                    "Only unicode characters can be processed, but a custom "
                    "Discord emoji was found. Please remove it and try again."
                ),
                colour=discord.Colour.red(),
            )
            await interaction.response.send_message(embed=embed)
            return

        if len(characters) > 25:
            embed = discord.Embed(
                title=f"Too many characters ({len(characters)}/25)",
                colour=discord.Colour.red(),
            )

            await interaction.response.send_message(embed=embed)
            return

        def get_info(char):
            digit = f"{ord(char):x}"
            if len(digit) <= 4:
                u_code = f"\\u{digit:>04}"
            else:
                u_code = f"\\U{digit:>08}"
            url = f"https://www.compart.com/en/unicode/U+{digit:>04}"
            name = f"[{unicodedata.name(char, '')}]({url})"
            info = f"`{u_code.ljust(10)}`: {name} - {char}"
            return info, u_code

        charlist, rawlist = zip(*(get_info(c) for c in characters))

        embed = discord.Embed(
            description="\n".join(charlist), color=discord.Color.blurple()
        )
        embed.set_author(name="Character Info")

        if len(characters) > 1:
            embed.add_field(
                name="Raw",
                value=f"`{''.join(rawlist)}`",
                inline=False,
            )

        string_literals = "\n".join(
            [rf"`\N{{{unicodedata.name(char, '')}}}`" for char in characters]
        )

        embed.add_field(
            name="String Literals",
            value=string_literals,
            inline=False,
        )

        await interaction.response.send_message(embed=embed)
