from ..bot import Bot
from .development import Development


async def setup(bot: Bot) -> None:
    await bot.add_cog(Development(bot))
