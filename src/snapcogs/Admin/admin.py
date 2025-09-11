from __future__ import annotations

import inspect
import io
import traceback
from contextlib import redirect_stdout
from typing import TYPE_CHECKING, Literal

import discord
from discord.ext import commands

from ..utils import cleanup_code

if TYPE_CHECKING:
    from discord.ext.commands import Context

    from ..bot import Bot


def get_syntax_error(e: SyntaxError) -> str:
    if e.text is None:
        return f"```py\n{e.__class__.__name__}: {e}\n```"
    return f"```py\n{e.text}{'^':>{e.offset}}\n{e.__class__.__name__}: {e}```"


class Admin(commands.Cog):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def cog_check(self, ctx: Context) -> bool:  # type: ignore[reportIncompatibleMethodOverride]
        return await self.bot.is_owner(ctx.author)

    @commands.command()
    @commands.guild_only()
    @commands.is_owner()
    async def sync(
        self,
        ctx: Context,
        guilds: commands.Greedy[discord.Object],
        spec: Literal["~", "*", "^"] | None = None,
    ) -> None:
        """Sync AppCommands to guilds, or globally.
        The `spec` argument works as follow:
            - `None`: to sync all *global* commands within the CommandTree.
            - `~`: to sync all guild commands for the current context's guild.
            - `*`: to copy all global commands to the current guild.
            - `^`: to remove all guild commands from the CommandTree.

        Umbra's sync command.
        https://about.abstractumbra.dev/discord.py/2023/01/29/sync-command-example.html
        """
        if not guilds:
            if spec == "~":
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == "*":
                ctx.bot.tree.copy_global_to(guild=ctx.guild)
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == "^":
                ctx.bot.tree.clear_commands(guild=ctx.guild)
                await ctx.bot.tree.sync(guild=ctx.guild)
                synced = []
            else:
                synced = await ctx.bot.tree.sync()

            await ctx.send(
                f"Synced {len(synced)} commands "
                f"{'globally' if spec is None else 'to the current guild.'}"
            )
            return

        ret = 0
        for guild in guilds:
            try:
                await ctx.bot.tree.sync(guild=guild)
            except discord.HTTPException:
                pass
            else:
                ret += 1

        await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")

    @commands.command()
    @commands.max_concurrency(1, commands.BucketType.channel)
    async def repl(self, ctx: Context) -> None:  # noqa: C901, PLR0912, PLR0915
        """Launch an interactive REPL session."""

        variables = {
            "ctx": ctx,
            "bot": ctx.bot,
            "message": ctx.message,
            "guild": ctx.guild,
            "channel": ctx.channel,
            "author": ctx.author,
            "_": None,
        }

        await ctx.reply(
            "Enter code to execute or evaluate. `exit()` or `quit` to exit."
        )

        def check(m: discord.Message) -> bool:
            return (
                m.author.id == ctx.author.id
                and m.channel.id == ctx.channel.id
                and m.content.startswith("`")
            )

        while True:
            try:
                response = await self.bot.wait_for(
                    "message", check=check, timeout=10.0 * 60.0
                )
            except TimeoutError:
                await ctx.reply("Exiting REPL session.")
                break

            cleaned = cleanup_code(response.content)

            if cleaned in ("quit", "exit", "exit()"):
                await response.reply("Exiting.")
                return

            executor = exec
            if cleaned.count("\n") == 0:
                # single statement, potentially 'eval'
                try:
                    code = compile(cleaned, "<repl session>", "eval")
                except SyntaxError:
                    pass
                else:
                    executor = eval

            if executor is exec:
                try:
                    code = compile(cleaned, "<repl session>", "exec")
                except SyntaxError as e:
                    await response.reply(get_syntax_error(e))
                    continue

            variables["message"] = response

            fmt = None
            stdout = io.StringIO()

            try:
                with redirect_stdout(stdout):
                    result = executor(code, variables)  # type: ignore[reportPossiblyUnboundVariable]
                    if inspect.isawaitable(result):
                        result = await result
            except Exception:  # noqa: BLE001
                value = stdout.getvalue()
                fmt = f"```py\n{value}{traceback.format_exc()}\n```"
            else:
                value = stdout.getvalue()
                if result is not None:
                    fmt = f"```py\n{value}{result}\n```"
                    variables["_"] = result
                elif value:
                    fmt = f"```py\n{value}\n```"

            try:
                if fmt is not None:
                    if len(fmt) > 2000:
                        await response.reply("Content too big to be printed.")
                    else:
                        await response.reply(fmt)
            except discord.Forbidden:
                pass
            except discord.HTTPException as e:
                await response.reply(f"Unexpected error: `{e}`")

    @repl.error
    async def repl_error(self, ctx: Context, error: Exception) -> None:
        """Error hangling for the repl command."""

        if isinstance(error, commands.MaxConcurrencyReached):
            await ctx.reply(
                "Already running a REPL session. Exit it with `exit` or `quit`."
            )

        else:
            raise error
