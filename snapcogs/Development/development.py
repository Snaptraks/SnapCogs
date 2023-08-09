import re
import unicodedata

import discord
from discord import app_commands
from discord.ext import commands
import pint


UREG = pint.UnitRegistry()
UREG.default_system = None


def _extract_units():
    units = []
    for attr in dir(UREG):
        try:
            if isinstance(getattr(UREG, attr), pint.Unit):
                units.append(attr)

        except pint.UndefinedUnitError:
            pass

    return units


UNITS = _extract_units()


async def from_units_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    choice_units = [u for u in UNITS if current.lower() in u.lower()][:25]
    return [app_commands.Choice(name=unit, value=unit) for unit in choice_units]


async def to_units_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    if from_ := interaction.namespace["from"]:
        from_unit = getattr(UREG, from_)
        choice_units = [
            app_commands.Choice(name=str(unit), value=str(unit))
            for unit in UREG.get_compatible_units(from_unit.dimensionality)
            if current in str(unit)
        ][:25]

    else:
        choice_units = await from_units_autocomplete(interaction, current)

    return choice_units


class Development(commands.Cog):
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

    @app_commands.command()
    @app_commands.rename(from_="from")
    @app_commands.describe(
        value="Value of the quantity",
        from_="Units of the quantity",
        to="Units to convert the quantity to",
    )
    @app_commands.autocomplete(from_=from_units_autocomplete, to=to_units_autocomplete)
    async def convert(
        self,
        interaction: discord.Interaction,
        value: float,
        from_: str,
        to: str,
    ):
        """Convert a value from one unit to another."""

        quantity = UREG.Quantity(value, from_)

        await interaction.response.send_message(
            f"You converted `{quantity}` to `{quantity.to(to):.3g}`", ephemeral=True
        )
