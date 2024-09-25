import asyncio
import logging
import random
import string

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands, tasks
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError

from ..bot import Bot
from ..utils import relative_dt
from ..utils.checks import has_guild_permissions
from ..utils.views import confirm_prompt
from . import views
from .models import Tip, TipCounts

LOGGER = logging.getLogger(__name__)


def rank_emoji(n: int):
    """Return emojis from one (gold medal) to ten.
    To be used with enumerate(), therefore index 0 returns :first_place: and index 9
    returns :ten:.
    """

    if 0 <= n <= 2:
        # :first_place: == \U0001f947 == chr(129351)
        return chr(129351 + n)

    elif 3 <= n <= 8:
        # :four: == \u0034\ufe0f\u20e3 == chr(52)\ufe0f\u20e3
        return f"{chr(52 + n - 3)}\ufe0f\u20e3"

    elif n == 9:
        return "\N{KEYCAP TEN}"

    else:
        raise ValueError


class Tips(commands.Cog):
    tip = app_commands.Group(
        name="tip",
        description="Save and share tips for people on the server!",
        guild_only=True,
    )

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def tip_name_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[Choice[str]]:
        tips = await self._get_tips_names_like(interaction, current)
        suggestions = [Choice(name=tip.name, value=tip.name) for tip in tips]

        LOGGER.debug(
            f"tip_name_autocomplete: {current=}, {len(suggestions)} suggestions"
        )

        return suggestions

    async def tip_name_from_author_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[Choice[str]]:
        tips = await self._get_tips_names_like(interaction, current)
        suggestions = [
            app_commands.Choice(name=tip.name, value=tip.name)
            for tip in tips
            if tip.author_id == interaction.user.id
        ][:25]

        LOGGER.debug(
            f"tip_name_from_author_autocomplete: {current=}, "
            f"{len(suggestions)} suggestions"
        )

        return suggestions

    @tip.command(name="create")
    async def tip_create(self, interaction: discord.Interaction) -> None:
        """Create a new tip for the current server, owned by you."""

        LOGGER.debug(f"Creating a tip in guild {interaction.guild}.")
        modal = views.TipCreate()
        await interaction.response.send_modal(modal)
        await modal.wait()
        LOGGER.debug(f"Tip {modal.name.value!r} received.")

        assert interaction.guild is not None

        tip = Tip(
            author_id=interaction.user.id,
            content=modal.content.value,
            created_at=interaction.created_at,
            guild_id=interaction.guild.id,
            last_edited=interaction.created_at,
            name=modal.name.value,
        )

        try:
            await self._save_tip(tip)

        except IntegrityError:
            # unique constraint failed
            content = f"There is already a tip named `{tip.name}` here."

        else:
            content = f"Tip `{tip.name}` created!"
        await interaction.followup.send(content, ephemeral=True)

    @tip.command(name="show")
    @app_commands.describe(name="Name of the tip.")
    @app_commands.autocomplete(name=tip_name_autocomplete)
    async def tip_show(self, interaction: discord.Interaction, name: str) -> None:
        """Show a tip in the current channel."""

        assert interaction.guild is not None

        tip = await self._get_tip_by_name(interaction, name)

        if tip is None:
            await interaction.response.send_message(
                f"No tip named `{name}` here!", ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"Tip {tip.name}",
            description=tip.content,
            color=discord.Color.blurple(),
            timestamp=tip.last_edited,
        )
        tip_author = await self.bot.get_or_fetch_member(
            interaction.guild, tip.author_id
        )
        if tip_author is not None:
            embed.set_author(name=tip_author, icon_url=tip_author.display_avatar.url)

        await interaction.response.send_message(embed=embed)

        await self._increase_tip_uses(tip)

    @tip.command(name="edit")
    @app_commands.describe(name="Name of the tip.")
    @app_commands.autocomplete(name=tip_name_from_author_autocomplete)
    async def tip_edit(self, interaction: discord.Interaction, name: str) -> None:
        """Modify the content of a tip that you own."""

        tip = await self._get_member_tip_by_name(interaction, name)

        if tip is None:
            await interaction.response.send_message(
                f"No tip named `{name}` here!", ephemeral=True
            )
            return

        LOGGER.debug(f"Editing tip {name} in {interaction.guild}")
        modal = views.TipEdit(tip)
        await interaction.response.send_modal(modal)
        await modal.wait()

        new_content = modal.content.value
        new_name = modal.name.value

        try:
            await self._edit_tip(
                tip,
                content=new_content,
                name=new_name,
            )

        except IntegrityError:
            # unique constraint failed
            await interaction.followup.send(
                f"There is already a tip named `{new_name}` here.",
                ephemeral=True,
            )

        else:
            await interaction.followup.send(f"Tip `{new_name}` edited!", ephemeral=True)

    @tip.command(name="info")
    @app_commands.describe(name="Name of the tip.")
    @app_commands.autocomplete(name=tip_name_autocomplete)
    async def tip_info(self, interaction: discord.Interaction, name: str) -> None:
        """Get information about a tip."""

        assert interaction.guild is not None

        tip = await self._get_tip_by_name(interaction, name)

        if tip is None:
            await interaction.response.send_message(
                f"No tip named `{name}` here!", ephemeral=True
            )
            return

        tip_author = interaction.guild.get_member(tip.author_id)
        embed = (
            discord.Embed(
                title=f"Tip {tip.name} Information",
                color=discord.Color.blurple(),
            )
            .add_field(
                name="Author",
                value=tip_author.mention
                if tip_author is not None
                else f"<@{tip.author_id}>",
            )  # user might have left the server
            .add_field(name="Uses", value=f"`{tip.uses}`")
            .add_field(name="Created", value=relative_dt(tip.created_at))
            .add_field(name="Last Edited", value=relative_dt(tip.last_edited))
            .add_field(name="Tip ID", value=f"`{tip.id}`")
        )
        if tip_author is not None:
            embed.set_author(name=tip_author, icon_url=tip_author.display_avatar.url)

        await interaction.response.send_message(embed=embed)

    @tip.command(name="raw")
    @app_commands.describe(name="Name of the tip.")
    @app_commands.autocomplete(name=tip_name_autocomplete)
    async def tip_raw(self, interaction: discord.Interaction, name: str) -> None:
        """Get the raw content of a tip, escaping markdown."""

        tip = await self._get_tip_by_name(interaction, name)

        if tip is None:
            await interaction.response.send_message(
                f"No tip named `{name}` here!", ephemeral=True
            )
            return

        raw_content = discord.utils.escape_mentions(
            discord.utils.escape_markdown(tip.content)
        )

        embed = discord.Embed(
            title=f"Raw content of tip {tip.name}",
            color=discord.Color.blurple(),
            description=raw_content,
        )
        await interaction.response.send_message(embed=embed)

    @tip.command(name="delete")
    @app_commands.describe(name="Name of the tip.")
    @app_commands.autocomplete(name=tip_name_from_author_autocomplete)
    async def tip_delete(self, interaction: discord.Interaction, name: str) -> None:
        """Delete a tip that you wrote."""

        assert isinstance(interaction.user, discord.Member)

        bypass_author_check = (
            await self.bot.is_owner(interaction.user)
            or interaction.user.guild_permissions.manage_messages
        )

        if bypass_author_check:
            # can delete tips not owned
            tip = await self._get_tip_by_name(interaction, name)

        else:
            # can only delete own tip
            tip = await self._get_member_tip_by_name(interaction, name)

        if tip is None:
            content = f"No tip named `{name}` here!"
        else:
            await self._delete_tip(tip)
            content = f"Tip `{tip.name}` successfully deleted."

        await interaction.response.send_message(content, ephemeral=True)

    @tip.command(name="purge")
    @app_commands.describe(member="The author of the tips to delete.")
    @has_guild_permissions(manage_messages=True)
    async def tip_purge(
        self, interaction: discord.Interaction, member: discord.Member
    ) -> None:
        """Delete all tips from the given member in this server."""

        tip_counts = await self._get_member_totals(member)
        if tip_counts.tips == 0:
            await interaction.response.send_message(
                f"{member.mention} does not have any tips on this server.",
                ephemeral=True,
            )
            return

        confirm = await confirm_prompt(
            interaction, f"Purging {tip_counts.tips} tips from {member.mention}?"
        )
        if not confirm:
            # send cancelation message within the view
            return

        await self._delete_member_tips(member)
        await confirm.interaction.response.send_message(
            f"Purged {tip_counts.tips} tips from {member.mention}.", ephemeral=True
        )

    @tip_purge.error
    async def tip_purge_error(
        self, interaction: discord.Interaction, error: BaseException
    ) -> None:
        """Error handler for the tip purge command."""

        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(error, ephemeral=True)

        else:
            interaction.extras["error_handled"] = False

    @tip.command(name="transfer")
    @app_commands.describe(
        name="Name of the tip.", member="Member to transfer the tip to."
    )
    @app_commands.autocomplete(name=tip_name_from_author_autocomplete)
    async def tip_transfer(
        self, interaction: discord.Interaction, name: str, member: discord.Member
    ) -> None:
        """Transfer tip ownership to another member."""

        if member.bot or (interaction.user.id == member.id):
            await interaction.response.send_message(
                "Cannot transfer ownership of the tip to this member.", ephemeral=True
            )
            return

        tip = await self._get_member_tip_by_name(interaction, name)

        if tip is None:
            await interaction.response.send_message(
                f"No tip named `{name}` here!", ephemeral=True
            )
            return

        await self._edit_tip(
            tip,
            author_id=member.id,
        )
        await interaction.response.send_message(
            f"Transferring tip `{name}` to {member.mention}",
        )
        LOGGER.debug(f"Tip {name} transfered to {member}")

    @tip.command(name="claim")
    @app_commands.describe(name="Name of the tip.")
    @app_commands.autocomplete(name=tip_name_autocomplete)
    async def tip_claim(self, interaction: discord.Interaction, name: str) -> None:
        """Claim a tip where the author has left the server."""

        assert interaction.guild is not None

        tip = await self._get_tip_by_name(interaction, name)

        if tip is None:
            await interaction.response.send_message(
                f"No tip named `{name}` here!", ephemeral=True
            )
            return

        member = await self.bot.get_or_fetch_member(interaction.guild, tip.author_id)
        if member is not None:
            await interaction.response.send_message(
                "The tip author is still in the server.", ephemeral=True
            )
            return

        # all checks passed, claiming the tip
        await self._edit_tip(
            tip,
            author_id=interaction.user.id,
        )
        await interaction.response.send_message(
            f"Claiming tip `{name}` for yourself.", ephemeral=True
        )
        LOGGER.debug(f"Tip {name} claimed by {interaction.user}")

    @tip.command(name="list")
    @app_commands.describe(member="Author of the tips.")
    async def tip_list(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ) -> None:
        """List all the tips that you, or someone else, wrote."""

        assert interaction.guild is not None

        if member is None:
            assert isinstance(interaction.user, discord.Member)
            member = interaction.user

        tips = await self._get_member_tips(member)
        LOGGER.debug(f"Listing {len(tips)} tips for {interaction.guild.name}")

        if tips:
            # todo: have a paginated version
            embed = discord.Embed(
                title="List of Tips",
                color=discord.Color.blurple(),
                description="\n".join(tip.name for tip in tips),
            ).set_author(name=member.display_name, icon_url=member.display_avatar.url)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(
                f"Member {member} did not write any tips.", ephemeral=True
            )

    @tip.command(name="all")
    async def tip_all(self, interaction: discord.Interaction) -> None:
        """List all the tips from this server."""

        assert interaction.guild is not None

        tips = await self._get_guild_tips(interaction.guild)
        LOGGER.debug(f"Listing {len(tips)} tips for {interaction.guild.name}")

        if tips:
            max_id_length = max(len(str(tip.id)) for tip in tips)
            # todo: have a paginated version
            embed = discord.Embed(
                title="List of Tips",
                color=discord.Color.blurple(),
                description="\n".join(
                    (
                        f"`{tip.id:>{max_id_length}d}` {tip.name} "
                        f"(<@{tip.author_id}>)"
                    )
                    for tip in tips
                ),
            ).set_author(
                name=interaction.guild.name,
                icon_url=getattr(interaction.guild.icon, "url", ""),
            )
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(
                "There are no tips here.", ephemeral=True
            )

    async def tip_stats_guild(self, guild: discord.Guild) -> discord.Embed:
        """Build the embed for guild statistics."""

        embed = (
            discord.Embed(title="Server Tips Statistics", color=discord.Color.blurple())
            .set_author(
                name=guild.name,
                icon_url=(getattr(guild.icon, "url", "")),
            )
            .set_footer(text="Server-wide statistics")
        )

        # total tips
        # total tip uses
        tip_counts = await self._get_guild_totals(guild)
        embed.add_field(name="Total Tips", value=tip_counts.tips)
        embed.add_field(name="Total Tip Uses", value=tip_counts.uses)

        # top 3 tips most used
        top_tips = await self._get_guild_top_tips(guild)
        embed.add_field(
            name="Top Tips",
            value="\n".join(
                (
                    f"{rank_emoji(n)}: {tip.name} "
                    f"(<@{tip.author_id}>, {tip.uses} uses)"
                )
                for n, tip in enumerate(top_tips)
            ),
            inline=False,
        )

        # top 3 authors (most written tips)
        top_authors = await self._get_guild_top_authors(guild)
        embed.add_field(
            name="Top Tip Authors",
            value="\n".join(
                f"{rank_emoji(n)}: <@{author.author_id}> ({author.tips} tips)"
                for n, author in enumerate(top_authors)
            ),
            inline=False,
        )

        return embed

    async def tip_stats_member(self, member: discord.Member) -> discord.Embed:
        """Build the embed for member statistics."""

        embed = (
            discord.Embed(title="Member Tips Statistics", color=discord.Color.blurple())
            .set_author(name=member, icon_url=member.display_avatar.url)
            .set_footer(text=f"Statistics for server {member.guild.name}")
        )

        # tips owned
        # tip owned uses
        tip_counts = await self._get_member_totals(member)
        embed.add_field(name="Total Tips", value=tip_counts.tips)
        embed.add_field(name="Total Tip Uses", value=tip_counts.uses)

        # top 3 tips most used
        top_tips = await self._get_member_top_tips(member)
        embed.add_field(
            name="Top Tips",
            value="\n".join(
                f"{rank_emoji(n)}: {tip.name} ({tip.uses} uses)"
                for n, tip in enumerate(top_tips)
            ),
            inline=False,
        )

        return embed

    @tip.command(name="stats")
    @app_commands.describe(member="Statistics of the member, or server if ommited.")
    async def tip_stats(
        self, interaction: discord.Interaction, member: discord.Member | None = None
    ) -> None:
        """Get statistics for a member or the whole server."""

        assert interaction.guild is not None

        if member is None:
            # guild stats
            embed = await self.tip_stats_guild(interaction.guild)
            LOGGER.debug(f"Sending tip stats for guild {interaction.guild.name}")
        else:
            # member stats
            embed = await self.tip_stats_member(member)
            LOGGER.debug(
                f"Sending tip stats for member {member} in {member.guild.name}"
            )

        await interaction.response.send_message(embed=embed)

    async def _save_tip(self, tip: Tip) -> None:
        """Save a tip to the database."""

        async with self.bot.db.session() as session:
            async with session.begin():
                session.add(tip)

        LOGGER.debug(f"Tip {tip.name} saved.")

    async def _edit_tip(
        self,
        tip: Tip,
        author_id: int | None = None,
        content: str | None = None,
        name: str | None = None,
    ) -> None:
        """Edit a tip in the database."""

        async with self.bot.db.session() as session:
            async with session.begin():
                await session.execute(
                    update(Tip)
                    .values(
                        author_id=author_id or tip.author_id,
                        content=content or tip.content,
                        name=name or tip.name,
                        last_edited=discord.utils.utcnow(),
                    )
                    .where(Tip.id == tip.id)
                )

        LOGGER.debug(f"Tip {tip.id} edited.")

    async def _get_tip_by_name(
        self, interaction: discord.Interaction, name: str
    ) -> Tip | None:
        """Get a tip by its name in the current guild."""

        assert interaction.guild is not None

        async with self.bot.db.session() as session:
            tip = await session.scalar(
                select(Tip).where(
                    Tip.guild_id == interaction.guild.id,
                    Tip.name == name,
                )
            )

        if tip is None:
            log = f"No tip named {name!r} in guild {interaction.guild.id}"

        else:
            log = f"Found tip {tip.name!r} for guild {tip.guild_id}"

        LOGGER.debug(log)

        return tip

    async def _get_member_tip_by_name(
        self, interaction: discord.Interaction, name: str
    ) -> Tip | None:
        """Get a tip by its name in the current guild, owned by a given member."""

        assert interaction.guild is not None

        async with self.bot.db.session() as session:
            tip = await session.scalar(
                select(Tip).where(
                    Tip.guild_id == interaction.guild.id,
                    Tip.author_id == interaction.user.id,
                    Tip.name == name,
                )
            )

        if tip is not None:
            log = (
                f"Found tip {tip.name} "
                f"for member {tip.author_id} "
                f"and guild {tip.guild_id}."
            )
        else:
            log = (
                f"No tip named {name} for member {interaction.user.id} "
                f"in guild {interaction.guild.id}"
            )

        LOGGER.debug(log)
        return tip

    async def _get_tips_names_like(
        self, interaction: discord.Interaction, substring: str
    ) -> list[Tip]:
        """Get a list of tip names that contain substring."""

        assert interaction.guild is not None

        async with self.bot.db.session() as session:
            tips = await session.scalars(
                select(Tip)
                .where(Tip.guild_id == interaction.guild.id)
                .filter(Tip.name.icontains(substring))
            )

        LOGGER.debug(
            f"Searched tip names like {substring} in guild {interaction.guild}"
        )
        return list(tips)

    async def _get_member_tips(self, member: discord.Member) -> list[Tip]:
        """Get all tips owned by a member in a specific server."""

        async with self.bot.db.session() as session:
            tips = await session.scalars(
                select(Tip).where(
                    Tip.guild_id == member.guild.id,
                    Tip.author_id == member.id,
                )
            )

        LOGGER.debug(f"Searched all tips from member {member}")
        return list(tips)

    async def _get_guild_tips(self, guild: discord.Guild) -> list[Tip]:
        """Get all tips saved in the given server."""

        async with self.bot.db.session() as session:
            tips = await session.scalars(
                select(Tip).where(Tip.guild_id == guild.id).order_by(Tip.id)
            )

        LOGGER.debug(f"Searched all tips for guild {guild}")
        return list(tips)

    async def _get_guild_totals(self, guild: discord.Guild) -> TipCounts:
        """Get count of tips and total uses for the given server."""

        async with self.bot.db.session() as session:
            results = await session.execute(
                select(func.count(), func.sum(Tip.uses))
                .select_from(Tip)
                .where(Tip.guild_id == guild.id)
            )

        result = next(results)
        totals = TipCounts(tips=result[0], uses=result[1])
        LOGGER.debug(f"Found {result} tips from guild {guild}")
        return totals

    async def _get_guild_top_tips(
        self, guild: discord.Guild, amount: int = 3
    ) -> list[Tip]:
        """Get the top tips by uses for the given server."""

        async with self.bot.db.session() as session:
            top_tips = await session.scalars(
                select(Tip)
                .where(Tip.guild_id == guild.id)
                .order_by(Tip.uses.desc())
                .limit(amount)
            )

        LOGGER.debug(f"Searched top tips for guild {guild}")
        return list(top_tips)

    async def _get_guild_top_authors(
        self, guild: discord.Guild, amount: int = 3
    ) -> list[TipCounts]:
        """Get the top tip authors by number of tips for the given server."""

        async with self.bot.db.session() as session:
            results = await session.execute(
                select(Tip.author_id, func.count())
                .select_from(Tip)
                .where(Tip.guild_id == guild.id)
                .group_by(Tip.author_id)
                .order_by(func.count().desc())
                .limit(amount)
            )

        top_authors = [
            TipCounts(author_id=result[0], tips=result[1]) for result in results
        ]
        return top_authors

    async def _get_member_totals(self, member: discord.Member) -> TipCounts:
        """Get count of tips and total uses from the given member."""

        async with self.bot.db.session() as session:
            results = await session.execute(
                select(func.count(), func.sum(Tip.uses))
                .select_from(Tip)
                .where(
                    Tip.guild_id == member.guild.id,
                    Tip.author_id == member.id,
                )
            )

        result = next(results)
        totals = TipCounts(tips=result[0], uses=result[1])
        LOGGER.debug(f"Found {result} tips from member {member}")
        return totals

    async def _get_member_top_tips(
        self, member: discord.Member, amount: int = 3
    ) -> list[Tip]:
        """Get the top tips by uses from the given member."""

        async with self.bot.db.session() as session:
            top_tips = await session.scalars(
                select(Tip)
                .where(
                    Tip.guild_id == member.guild.id,
                    Tip.author_id == member.id,
                )
                .order_by(Tip.uses.desc())
                .limit(amount)
            )

        LOGGER.debug(f"Searched top tips for member {member}")
        return list(top_tips)

    async def _increase_tip_uses(self, tip: Tip) -> None:
        """Increase the use of tip with tip_id by 1."""

        async with self.bot.db.session() as session:
            async with session.begin():
                await session.execute(
                    update(Tip).where(Tip.id == tip.id).values(uses=tip.uses + 1)
                )

        LOGGER.debug(f"Increased uses for {tip.id=}")

    async def _delete_tip(self, tip: Tip) -> None:
        """Delete a tip from the database."""

        async with self.bot.db.session() as session:
            async with session.begin():
                await session.execute(delete(Tip).where(Tip.id == tip.id))

        LOGGER.debug(f"Deleted tip with {tip.id=}")

    async def _delete_member_tips(self, member: discord.Member) -> None:
        """Delete all tips from a member, in a specific server."""

        async with self.bot.db.session() as session:
            async with session.begin():
                result = await session.execute(
                    delete(Tip).where(
                        Tip.guild_id == member.guild.id,
                        Tip.author_id == member.id,
                    )
                )

        deleted = result.rowcount

        LOGGER.debug(f"Deleted {deleted} tips from {member=}")
