from typing import Optional, Literal

import discord
from discord.ext import commands


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author)

    @commands.command()
    async def sync(
        self,
        ctx: commands.Context,
        guilds: commands.Greedy[discord.Object],
        spec: Optional[Literal["~"]] = None,
    ) -> None:
        """Sync AppCommands to guilds, or globally.
        Umbra's sync command.
        """
        if not guilds:
            if spec == "~":
                ctx.bot.tree.copy_global_to(guild=ctx.guild)
                fmt = await ctx.bot.tree.sync(guild=ctx.guild)
            else:
                fmt = await ctx.bot.tree.sync()

            await ctx.send(
                f"Synced {len(fmt)} commands "
                f"{'globally' if spec is None else 'to the current guild.'}"
            )
            return

        fmt = 0
        for guild in guilds:
            try:
                await ctx.bot.tree.sync(guild=guild)
            except discord.HTTPException:
                pass
            else:
                fmt += 1

        await ctx.reply(f"Synced the tree to {fmt}/{len(guilds)} guilds.")

    @commands.command()
    async def clear(
        self,
        ctx: commands.Context,
        guilds: commands.Greedy[discord.Object],
        spec: Optional[Literal["~"]] = None,
    ) -> None:
        """Clear AppCommands of guild, or globally."""

        if not guilds:
            if spec == "~":
                ctx.bot.tree.clear_commands(guild=ctx.guild)
                await ctx.bot.tree.sync(guild=ctx.guild)
            else:
                ctx.bot.tree.clear_commands(guild=None)
                await ctx.bot.tree.sync()

            await ctx.send(
                f"Cleared commands "
                f"{'globally' if spec is None else 'in the current guild.'}"
            )
            return

        fmt = 0
        for guild in guilds:
            try:
                ctx.bot.tree.clear_commands(guild=guild)
                await ctx.bot.tree.sync(guild=guild)
            except discord.HTTPException:
                pass
            else:
                fmt += 1

        await ctx.reply(f"Cleared the tree of {fmt}/{len(guilds)} guilds.")
