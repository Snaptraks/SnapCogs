from ..bot import Bot
from .timestamps import Timestamps


async def setup(bot: Bot) -> None:
    await bot.add_cog(Timestamps(bot))
