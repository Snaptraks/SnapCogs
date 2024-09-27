import logging

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from ..bot import Bot
from ..utils.errors import TransformerMessageNotFound, TransformerNotBotMessage
from ..utils.transformers import BotMessageTransformer
from . import models, views

LOGGER = logging.getLogger(__name__)


class Roles(commands.Cog):
    roles = app_commands.Group(
        name="roles",
        description="Create a roles selection menu",
        default_permissions=discord.Permissions(manage_roles=True),
    )

    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self.persistent_views_loaded = False

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Load the persistent Views once, when the guild data is loaded in the bot."""

        if not self.persistent_views_loaded:
            await self.load_persistent_views()  # needs guild data, so we load this here
            self.persistent_views_loaded = True

    async def load_persistent_views(self) -> None:
        """Load all persistent Views."""

        for view_model in await self._get_all_views():
            view = await self.build_view(view_model)
            if view is not None:
                self.bot.add_view(
                    view,
                    message_id=view_model.message_id,
                )

    async def save_persistent_view(
        self, view: views.RolesView, message: discord.Message
    ) -> None:
        """Save a persistent View to the database."""

        assert message.guild is not None

        roles_view_model = models.View(
            guild_id=message.guild.id,
            message_id=message.id,
            toggle=view.toggle,
        )

        roles_view_model.components = [
            models.Component(
                name=key,
                component_id=val,
            )
            for key, val in view.components_id.items()
        ]

        roles_view_model.roles = [
            models.Role(
                role_id=role.id,
            )
            for role in view.roles
        ]

        await self._save_view(roles_view_model)

    async def build_view(self, view_model: models.View) -> views.RolesView | None:
        """Build a Discord View from database information."""

        guild = self.bot.get_guild(view_model.guild_id)

        if guild is None:
            # skip if we cannot find the guild (ie. the bot left the guild)
            return None

        # get the roles
        roles = [guild.get_role(role.role_id) for role in view_model.roles]
        roles = [r for r in roles if r is not None]  # remove None (missing roles)

        # get the components id
        components_id = {
            component.name: component.component_id
            for component in view_model.components
        }

        toggle = view_model.toggle

        view = views.RolesView(roles, toggle=toggle, components_id=components_id)

        return view

    async def roles_creation_selection(
        self,
        interaction: discord.Interaction,
        available_roles: list[discord.Role] | None = None,
        ignored_roles: list[discord.Role] | None = None,
    ) -> list[discord.Role]:
        """Send a selection menu to chose from the guild's roles."""

        guild = interaction.guild
        assert guild is not None
        assert isinstance(interaction.user, discord.Member)
        if available_roles is None:
            # ignore @everyone, managed roles, and roles above the bot's top role
            available_roles = [
                r
                for r in reversed(guild.roles[1:])
                if (r < guild.me.top_role) and not r.managed
            ]

        if ignored_roles is not None:
            available_roles = [r for r in available_roles if r not in ignored_roles]

        view = views.RolesCreateView(available_roles, author=interaction.user)
        await interaction.response.send_message(view=view)
        await view.wait()
        selected_roles = view.selected_roles
        embed = discord.Embed(
            title="Selected the following roles:",
            description="\n".join(r.mention for r in selected_roles),
            color=discord.Color.green(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        await interaction.delete_original_response()

        return selected_roles

    async def roles_creation_callback(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None,
        content: str,
        *,
        toggle: bool,
    ) -> None:
        """Generic callback to create a roles selection menu."""

        if channel is None:
            channel = interaction.channel  # type: ignore

        assert channel is not None

        selected_roles = await self.roles_creation_selection(interaction)

        view = views.RolesView(selected_roles, toggle=toggle)
        message = await channel.send(content=content, view=view)
        await self.save_persistent_view(view, message)

    @roles.command(name="select")
    @app_commands.describe(
        channel=(
            "Channel to send the roles selection menu to. "
            "Defaults to current channel."
        ),
        content="Text in the message to send with the roles selection menu.",
    )
    async def roles_select(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
        content: str = "Select from the following roles:",
    ) -> None:
        """Create a role selection menu, to select many roles from the list."""

        await self.roles_creation_callback(interaction, channel, content, toggle=False)

    @roles.command(name="toggle")
    @app_commands.describe(
        channel=(
            "Channel to send the roles selection menu to. "
            "Defaults to current channel."
        ),
        content="Text in the message to send with the roles selection menu.",
    )
    async def roles_toggle(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
        content: str = "Select one of the following roles:",
    ) -> None:
        """Create a role selection menu, to select *one* role from the list."""

        await self.roles_creation_callback(interaction, channel, content, toggle=True)

    @roles.command(name="add")
    @app_commands.describe(
        message="Link or ID of the message to add roles to. Must be the bot's!"
    )
    async def roles_add(
        self,
        interaction: discord.Interaction,
        message: app_commands.Transform[discord.Message, BotMessageTransformer],
    ) -> None:
        """Add a role to the selection menu."""

        assert interaction.guild is not None
        view_model = await self._get_view_from_message(message)
        current_selection_roles = [
            interaction.guild.get_role(role.role_id) for role in view_model.roles
        ]
        current_selection_roles = [r for r in current_selection_roles if r is not None]

        added_roles = await self.roles_creation_selection(
            interaction, ignored_roles=current_selection_roles
        )
        view_model.roles.extend([models.Role(role_id=r.id) for r in added_roles])
        await self._save_view(view_model)

        # update view model with added roles
        view_model = await self._get_view_from_message(message)

        await message.edit(view=await self.build_view(view_model))

        roles_str = ", ".join(role.mention for role in added_roles)
        embed = discord.Embed(
            color=discord.Color.green(),
            title="Successfully edited selection.",
            description=(
                f"Role(s) {roles_str} added to the " f"[message]({message.jump_url})."
            ),
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @roles.command(name="remove")
    @app_commands.describe(
        message="Link or ID of the message to remove roles from. Must be the bot's!"
    )
    async def roles_remove(
        self,
        interaction: discord.Interaction,
        message: app_commands.Transform[discord.Message, BotMessageTransformer],
    ) -> None:
        """Remove roles from the selection menu."""

        assert interaction.guild is not None
        view_model = await self._get_view_from_message(message)
        current_selection_roles = [
            interaction.guild.get_role(role.role_id) for role in view_model.roles
        ]
        current_selection_roles = [r for r in current_selection_roles if r is not None]

        removed_roles = await self.roles_creation_selection(
            interaction, available_roles=current_selection_roles
        )

        removed_role_models = [
            r for r in view_model.roles if r.role_id in [rr.id for rr in removed_roles]
        ]
        await self._delete_roles(removed_role_models)

        # update view model without removed roles
        view_model = await self._get_view_from_message(message)

        await message.edit(view=await self.build_view(view_model))

        roles_str = ", ".join(role.mention for role in removed_roles)
        embed = discord.Embed(
            color=discord.Color.green(),
            title="Successfully edited selection.",
            description=(
                f"Role(s) {roles_str} removed from the "
                f"[message]({message.jump_url})."
            ),
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @roles.command(name="edit")
    @app_commands.describe(
        message="Link or ID of the message to edit the content. Must be the bot's!",
        content="New content to edit in the message.",
    )
    async def roles_edit(
        self,
        interaction: discord.Interaction,
        message: app_commands.Transform[discord.Message, BotMessageTransformer],
        content: str,
    ) -> None:
        """Edit the content of a role selection menu message."""

        await message.edit(content=content)

        embed = discord.Embed(
            color=discord.Color.green(),
            title="Successfully edited message.",
            description=(
                f"[Message]({message.jump_url}) content was edited to\n"
                f"```\n{content}\n```"
            ),
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @roles.command(name="delete")
    @app_commands.describe(
        message="Link or ID of the message to remove. Must be the bot's!"
    )
    async def roles_delete(
        self,
        interaction: discord.Interaction,
        message: app_commands.Transform[discord.Message, BotMessageTransformer],
    ) -> None:
        """Delete a role selection menu message."""

        assert isinstance(message.channel, discord.abc.GuildChannel)
        await self._delete_view_from_message(message)
        await message.delete()

        embed = discord.Embed(
            color=discord.Color.green(),
            title="Successfully deleted selection.",
            description=(
                f"Message was deleted from {message.channel.mention}, "
                "and removed from memory."
            ),
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @roles_add.error
    @roles_remove.error
    @roles_edit.error
    @roles_delete.error
    async def roles_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        """Error handler for the roles subcommands."""

        if isinstance(error, TransformerMessageNotFound):
            msg = (
                f"{error} ({error.original})\n"
                "You might need to use the format `{channel ID}-{message ID}` "
                "(shift-clicking on “Copy ID”) or the message URL."
            )
            await interaction.response.send_message(msg, ephemeral=True)

        elif isinstance(error, TransformerNotBotMessage):
            await interaction.response.send_message(
                f"Cannot delete message. {error}", ephemeral=True
            )

        else:
            interaction.extras["error_handled"] = False

    async def _get_all_views(self) -> list[models.View]:
        """Select all registered Views from the database."""

        async with self.bot.db.session() as session:
            roles_view_models = await session.scalars(
                select(models.View).options(
                    joinedload(models.View.components),
                    joinedload(models.View.roles),
                )
            )

        return list(roles_view_models.unique())

    async def _get_view_from_message(self, message: discord.Message) -> models.View:
        """Get the View data associated with a Message."""

        async with self.bot.db.session() as session:
            view_model = await session.scalar(
                select(models.View)
                .where(models.View.message_id == message.id)
                .options(
                    joinedload(models.View.components),
                    joinedload(models.View.roles),
                )
            )

        assert view_model is not None
        return view_model

    async def _save_view(self, role_view: models.View) -> None:
        """Save the View information."""

        async with self.bot.db.session() as session:
            async with session.begin():
                session.add(role_view)

    async def _delete_roles(self, role_models: list[models.Role]) -> None:
        """Delete roles information from the Database."""

        async with self.bot.db.session() as session:
            async with session.begin():
                for role in role_models:
                    await session.delete(role)

    async def _delete_view_from_message(self, message: discord.Message) -> None:
        """Delete the view and all the referencing rows in the other tables."""

        # delete should cascade
        async with self.bot.db.session() as session:
            async with session.begin():
                view_model = await session.scalar(
                    select(models.View).where(models.View.message_id == message.id)
                )

                await session.delete(view_model)
