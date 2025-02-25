from ..bot import Bot
from .roles import Roles


async def setup(bot: Bot):
    await bot.add_cog(Roles(bot))
