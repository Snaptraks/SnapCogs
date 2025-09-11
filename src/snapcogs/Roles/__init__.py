from ..bot import Bot
from .roles import Roles


async def setup(bot: Bot) -> None:
    await bot.add_cog(Roles(bot))
