from .poll import Poll


async def setup(bot):
    await bot.add_cog(Poll(bot))
