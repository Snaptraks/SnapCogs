from ..bot import Bot
from .announcements import Announcements


async def setup(bot: Bot) -> None:
    await bot.add_cog(Announcements(bot))
