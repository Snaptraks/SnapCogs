from .timestamps import Timestamps


async def setup(bot):
    await bot.add_cog(Timestamps(bot))
