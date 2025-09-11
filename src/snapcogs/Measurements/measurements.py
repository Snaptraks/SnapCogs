from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

import discord
import pint
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from pint.facets.plain import PlainQuantity

    from ..bot import Bot


LOGGER = logging.getLogger(__name__)


UREG = pint.UnitRegistry()
UREG.default_system = None  # type: ignore[reportAttributeAccessIssue]
UREG.formatter.default_format = ".3g~P"

# define joke units
UREG.define("banana = 178 millimeter")
UREG.define("washing_machine = 70 * kilogram")


METRIC = {
    UREG.millimeter,
    UREG.centimeter,
    UREG.meter,
    UREG.kilometer,
    UREG.gram,
    UREG.kilogram,
    UREG.degree_Celsius,
    UREG.banana,
    UREG.washing_machine,
}

IMPERIAL = {
    UREG.inch,
    UREG.foot,
    UREG.yard,
    UREG.mile,
    UREG.ounce,
    UREG.pound,
    UREG.degree_Fahrenheit,
    UREG.banana,
    UREG.washing_machine,
}

SYSTEMS = {
    "mks": METRIC,
    "imperial": IMPERIAL,
}


def _extract_units() -> list[str]:
    """Return a list of units from the UnitRegistry.

    Returns
    -------
    list[str]
        The list of unit names from the UnitRegistry
    """
    units: list[str] = []
    for attr in dir(UREG):
        try:
            if isinstance(getattr(UREG, attr), pint.Unit):
                units.append(attr)

        except pint.UndefinedUnitError:
            pass

    return units


UNITS = _extract_units()


async def from_units_autocomplete(
    _: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    """Autocomplete function that returns the units that contain the current string.

    Parameters
    ----------
    interaction : discord.Interaction
        The discord Interaction that triggered the autocomplete.
    current : str
        The current input from the user.

    Returns
    -------
    list[app_commands.Choice[str]]
        The list of units that contain the current string input.
    """
    choice_units = [u for u in UNITS if current.lower() in u.lower()][:25]
    return [app_commands.Choice(name=unit, value=unit) for unit in choice_units]


async def to_units_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    """Autocomplete function that returns the units with the same dimensions as the
    value in the "from" argument, and contain the current string.

    Parameters
    ----------
    interaction : discord.Interaction
        The discord Interaction that triggered the autocomplete.
    current : str
        The current input from the user.

    Returns
    -------
    list[app_commands.Choice[str]]
        The list of units with the same dimensions and contain the current string.
    """
    if from_ := interaction.namespace["from"]:
        from_unit = getattr(UREG, from_)
        choice_units = [
            app_commands.Choice(name=str(unit), value=str(unit))
            for unit in UREG.get_compatible_units(from_unit.dimensionality)
            if current.lower() in str(unit).lower()
        ][:25]

    else:
        choice_units = await from_units_autocomplete(interaction, current)

    return choice_units


def find_quantities(text: str) -> list[PlainQuantity]:
    """Scans a string for quantities in imperial or metric systems and returns a list
    of found Quantity.

    Parameters
    ----------
    text : str
        The text to extract the quantities from.

    Returns
    -------
    list[PlainQuantity]
        The list of found quantities.
    """
    # Regular expressions for different measurement units
    metric_units = r"mm|cm|m|km|g|kg|°C|C"
    imperial_units = r"in|\"|ft|foot|feet|\'|yd|yard|mi|oz|lb|°F|F"
    measurement_pattern = rf"(-?\d+(?:\.\d+)?)\s?(?:({metric_units}|{imperial_units}))"

    matches = re.findall(measurement_pattern, text)

    # Combine matches and format them
    quantities: list[PlainQuantity] = []

    for match in matches:
        value = float(match[0])
        unit = match[1]

        # manually set units that use shorthands
        if unit in {"C", "F"}:
            # we rarely use Coulomb or Farad anyway
            unit = f"°{unit}"

        elif unit == '"':
            unit = "inch"

        elif unit == "'":
            unit = "feet"

        quantities.append(UREG.Quantity(value, unit))

    return quantities


def convert_to_other(measurement: PlainQuantity) -> list[PlainQuantity]:
    """Convert Quantities from metric to imperial system (or vice versa).

    Parameters
    ----------
    measurement : PlainQuantity
        A Quantity, in the metric or imperial system.

    Returns
    -------
    list[PlainQuantity]
        A list of Quantities of the corresponding dimensions, in the imperial
        or metric system.

    Raises
    ------
    ValueError
        The Quantity is not defined in the metric or imperial system.
    """
    if measurement.check("[temperature]"):
        # handle temperature differently
        return [convert_to_other_temperature(measurement)]

    if measurement.units in METRIC:
        target_system = "imperial"

    elif measurement.units in IMPERIAL:
        target_system = "mks"

    else:
        msg = f"{measurement.units} not defined in metric or imperial system."
        raise ValueError(msg)

    target_units = (
        UREG.get_compatible_units(
            measurement.dimensionality, group_or_system=target_system
        )
        & SYSTEMS[target_system]
    )

    # for _some reason_ the system wants to use grams instead
    # of the conventional kg, so we force it here
    return [
        measurement.to(unit if unit != UREG.gram else UREG.kilogram)
        for unit in target_units
    ]


def convert_to_other_temperature(measurement: PlainQuantity) -> PlainQuantity:
    """Convert a temperature Quantity in Celsius to Fahrenheit, or vice versa.

    Parameters
    ----------
    measurement : PlainQuantity
        A temperature Quantity in Celsius or Fahrenheit.

    Returns
    -------
    PlainQuantity
        A temperature Quantity converted to Fahrenheit or Celsius.

    Raises
    ------
    ValueError
        Temperature units not Celsius or Fahrenheit.
    """
    if measurement.units == UREG.degree_Celsius:
        return measurement.to(UREG.degree_Fahrenheit)

    if measurement.units == UREG.degree_Fahrenheit:
        return measurement.to(UREG.degree_Celsius)

    msg = f"Wrong temperature unit {measurement.units}."
    raise ValueError(msg)


class Measurements(commands.Cog):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

        self.convert_units_context_menu = app_commands.ContextMenu(
            name="Convert Units",
            callback=self.convert_units,
        )
        self.bot.tree.add_command(self.convert_units_context_menu)

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
    ) -> None:
        """Convert a value from one unit to another."""

        quantity = UREG.Quantity(value, from_)

        await interaction.response.send_message(
            f"You converted `{quantity}` to `{quantity.to(to):.3g}`", ephemeral=True
        )

    async def convert_units(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        """Convert quantities in metric to imperial, and vice versa."""

        quantities = find_quantities(message.content)

        LOGGER.debug(f"Found {len(quantities)} quantities: {quantities}")

        embed = discord.Embed(
            colour=discord.Colour.blurple(),
            title="Unit Conversions",
        )
        descriptions: list[str] = []

        for quantity in quantities:
            converted_quantities = convert_to_other(quantity)
            converted_quantities_str = (
                f"• **{quantity}** is {', '.join(str(q) for q in converted_quantities)}"
            )
            descriptions.append(converted_quantities_str)

        if len(descriptions) == 0:
            embed.description = "No quantities found."
            await interaction.response.send_message(embed=embed, ephemeral=True)

        else:
            embed.description = "\n".join(descriptions)
            await interaction.response.send_message(embed=embed)
