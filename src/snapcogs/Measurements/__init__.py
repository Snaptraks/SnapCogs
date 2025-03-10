from ..bot import Bot
from .measurements import Measurements


async def setup(bot: Bot) -> None:
    await bot.add_cog(Measurements(bot))
