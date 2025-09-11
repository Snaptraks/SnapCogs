from enum import IntEnum

import discord
from aiohttp import ClientSession
from bs4 import BeautifulSoup, Tag
from discord import Interaction, app_commands
from discord.ext import commands

from ..bot import Bot

HOROSCOPE_BASE_URL = (
    "https://www.horoscope.com/us/horoscopes/general/horoscope-general-daily-today.aspx"
)
STAR_RATING_BASE_URL = "https://www.horoscope.com/star-ratings/today/"
PARSER = "html.parser"


class ZodiacSign(IntEnum):
    # Match the values that horoscope.com expects
    Aries = 1
    Taurus = 2
    Gemini = 3
    Cancer = 4
    Leo = 5
    Virgo = 6
    Libra = 7
    Scorpio = 8
    Sagittarius = 9
    Capricorn = 10
    Aquarius = 11
    Pisces = 12


ZODIAC_EMOJIS = {
    zodiac_sign: (
        "https://raw.githubusercontent.com/twitter/twemoji/"
        f"refs/heads/master/assets/72x72/{9799 + zodiac_sign:x}.png"
    )
    for zodiac_sign in ZodiacSign
}


async def get_today_horoscope(
    session: ClientSession,
    zodiac_sign: ZodiacSign,
) -> str:
    """Get today's horoscope text from horoscope.com for the given zodiac sign."""

    resp = await session.get(HOROSCOPE_BASE_URL, params={"sign": zodiac_sign})
    soup = BeautifulSoup(await resp.text(), PARSER)
    data = soup.find("div", attrs={"class": "main-horoscope"})
    if isinstance(data, Tag):
        assert data.p is not None
        _, horoscope_data = data.p.text.split(" - ", 1)
    else:
        msg = "Returned data not in the expected type."
        raise TypeError(msg)

    return horoscope_data


async def get_today_star_rating(
    session: ClientSession,
    zodiac_sign: ZodiacSign,
) -> list[tuple[str, str]]:
    """Get today's star rating from horoscope.com for the given zodiac sign."""

    resp = await session.get(f"{STAR_RATING_BASE_URL}{zodiac_sign.name}")
    soup = BeautifulSoup(await resp.text(), PARSER)

    data = soup.find("div", attrs={"class": "module-skin"})
    if isinstance(data, Tag):
        categories = data.find_all("h3")
        texts = data.find_all("p")[:-1]
    else:
        msg = "Returned data not in the expected type."
        raise TypeError(msg)

    star_ratings: list[tuple[str, str]] = []
    for c, t in zip(categories, texts, strict=True):
        stars = "\N{WHITE MEDIUM STAR}" * len(
            c.find_all("i", attrs={"class": "highlight"})  # type: ignore[reportAttributeAccessIssue]
        )

        star_ratings.append(
            (
                f"{c.text}:{stars}",
                t.text,
            )
        )

    return star_ratings


class Horoscope(commands.Cog):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @app_commands.command()
    @app_commands.describe(zodiac_sign="The Zodiac sign to get the horoscope of.")
    async def horoscope(
        self,
        interaction: Interaction,
        zodiac_sign: ZodiacSign,
    ) -> None:
        """Get today's horoscope for the given Zodiac sign."""

        today = discord.utils.utcnow()
        horoscope = await get_today_horoscope(self.bot.http_session, zodiac_sign)
        star_ratings = await get_today_star_rating(self.bot.http_session, zodiac_sign)
        zodiac_name = zodiac_sign.name.title()
        author_name = interaction.user.display_name

        embed = (
            discord.Embed(
                color=0x9266CC,
                title=f"Horoscope for {zodiac_sign.name.title()}",
            )
            .set_thumbnail(url=ZODIAC_EMOJIS[zodiac_sign])
            .add_field(
                name=discord.utils.format_dt(today, style="D"),
                value=horoscope.replace(zodiac_name, author_name),
                inline=False,
            )
        )

        for category, text in star_ratings:
            embed.add_field(
                name=category,
                value=text,
                inline=False,
            )

        await interaction.response.send_message(embed=embed)
