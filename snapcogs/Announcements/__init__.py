from snapcogs import Bot
from .announcements import Announcements


async def setup(bot: Bot):
    await bot.add_cog(Announcements(bot))
