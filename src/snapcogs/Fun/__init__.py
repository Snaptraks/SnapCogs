from ..bot import Bot
from .fun import Fun


async def setup(bot: Bot):
    await bot.add_cog(Fun(bot))
