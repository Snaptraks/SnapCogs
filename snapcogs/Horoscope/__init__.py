from ..bot import Bot
from .horoscope import Horoscope


async def setup(bot: Bot) -> None:
    await bot.add_cog(Horoscope(bot))
