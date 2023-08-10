from ..bot import Bot
from .link import Link


async def setup(bot: Bot):
    await bot.add_cog(Link(bot))
