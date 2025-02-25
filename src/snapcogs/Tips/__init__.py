from ..bot import Bot
from .tips import Tips


async def setup(bot: Bot):
    await bot.add_cog(Tips(bot))
