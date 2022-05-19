from .fun import Fun


async def setup(bot):
    await bot.add_cog(Fun(bot))
