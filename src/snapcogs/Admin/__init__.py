from ..bot import Bot
from .admin import Admin


async def setup(bot: Bot):
    await bot.add_cog(Admin(bot))
