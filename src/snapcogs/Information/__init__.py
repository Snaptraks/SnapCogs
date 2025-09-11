from ..bot import Bot
from .information import Information


async def setup(bot: Bot) -> None:
    await bot.add_cog(Information(bot))
