from ..bot import Bot
from .timestamps import Timestamps


async def setup(bot: Bot):
    await bot.add_cog(Timestamps(bot))
