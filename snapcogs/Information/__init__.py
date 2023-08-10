from ..bot import Bot
from .information import Information


async def setup(bot: Bot):
    await bot.add_cog(Information(bot))
