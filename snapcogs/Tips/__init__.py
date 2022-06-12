from .tips import Tips


async def setup(bot):
    await bot.add_cog(Tips(bot))
