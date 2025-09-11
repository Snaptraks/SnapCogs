from ..bot import Bot
from .admin import Admin


async def setup(bot: Bot) -> None:
    await bot.add_cog(Admin(bot))
