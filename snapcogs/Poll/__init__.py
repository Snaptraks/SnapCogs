from ..bot import Bot
from .poll import Poll


async def setup(bot: Bot):
    await bot.add_cog(Poll(bot))
