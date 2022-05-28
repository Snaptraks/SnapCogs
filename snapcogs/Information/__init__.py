from .information import Information


async def setup(bot):
    await bot.add_cog(Information(bot))
