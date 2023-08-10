from ..bot import Bot
from .development import Development


async def setup(bot: Bot):
    await bot.add_cog(Development(bot))
