from ..bot import Bot
from .fun import Fun


async def setup(bot: Bot) -> None:
    await bot.add_cog(Fun(bot))
