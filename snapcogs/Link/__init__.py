from .link import Link


async def setup(bot):
    await bot.add_cog(Link(bot))
