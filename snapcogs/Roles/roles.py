import logging
import traceback

import discord
from discord import app_commands
from discord.ext import commands

from . import views
from ..utils.transformers import BotMessageTransformer
from ..utils.errors import TransformerMessageNotFound, TransformerNotBotMessage

LOGGER = logging.getLogger(__name__)


class Roles(commands.Cog):
    roles = app_commands.Group(
        name="roles", description="Create a roles selection menu"
    )
    roles.default_permissions = discord.Permissions(manage_roles=True)

    def __init__(self, bot):
        self.bot = bot
        self.persistent_views_loaded = False

    async def cog_load(self):
        await self._create_tables()

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.persistent_views_loaded:
            await self.load_persistent_views()  # needs guild data, so we load this here
            self.persistent_views_loaded = True

    async def load_persistent_views(self):
        for view_data in await self._get_all_views():
            self.bot.add_view(
                await self.build_view(view_data), message_id=view_data["message_id"],
            )

    async def save_persistent_view(self, view, message):
        view_payload = dict(
            guild_id=message.guild.id, message_id=message.id, toggle=view.toggle
        )

        view_id = await self._save_view(view_payload)

        components_payload = [
            dict(name=key, component_id=val, view_id=view_id)
            for key, val in view.components_id.items()
        ]
        await self._save_components(components_payload)

        roles_payload = [dict(role_id=role.id, view_id=view_id) for role in view.roles]
        await self._save_roles(roles_payload)

    async def build_view(self, view_data):
        guild = self.bot.get_guild(view_data["guild_id"])

        # get the roles
        roles = [
            guild.get_role(row["role_id"])
            for row in await self._get_roles(view_data["view_id"])
        ]

        # get the components id
        components_id = {
            row["name"]: row["component_id"]
            for row in await self._get_components(view_data["view_id"])
        }

        toggle = view_data["toggle"]

        view = views.RolesView(roles, toggle=toggle, components_id=components_id)

        return view

    async def roles_creation_selection(
        self, interaction: discord.Interaction
    ) -> list[discord.Role]:
        """Send a selection menu to chose from the guild's roles."""

        guild = interaction.guild
        # ignore @everyone, managed roles, and roles above the bot's top role
        available_roles = [
            r
            for r in reversed(guild.roles[1:])
            if (r < guild.me.top_role) and not r.managed
        ]

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
        await interaction.delete_original_message()

        return selected_roles

    async def roles_creation_callback(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        content: str,
        *,
        toggle: bool,
    ):
        """Generic callback to create a roles selection menu."""

        if channel is None:
            channel = interaction.channel

        selected_roles = await self.roles_creation_selection(interaction)

        view = views.RolesView(selected_roles, toggle=toggle)
        message = await channel.send(content=content, view=view)
        await self.save_persistent_view(view, message)

    def roles_add_remove(self, method):
        async def execute(message, roles):
            view_data = await self._get_view_from_message(message)
            LOGGER.debug(f"{method}d roles for view_id {view_data['view_id']}")

            rows = await self._get_roles(view_data["view_id"])
            current_roles = {row["role_id"] for row in rows}
            # if method == "save"
            dismissed_roles = [r for r in roles if r.id in current_roles]
            roles = [r for r in roles if r.id not in current_roles]

            if method == "delete":
                # if we remove / delete the role from the menu, we want to remove roles
                # that are in the menu, and dismiss those that are not
                roles, dismissed_roles = dismissed_roles, roles

            dismissed_roles_str = ", ".join(r.mention for r in dismissed_roles)

            await getattr(self, f"_{method}_roles")(
                [dict(role_id=role.id, view_id=view_data["view_id"]) for role in roles]
            )
            LOGGER.debug(f"Editing message {message.id}")
            await message.edit(view=await self.build_view(view_data))

            roles_str = ", ".join(role.mention for role in roles)
            verb = dict(delete="removed from", save="added to")
            embed = discord.Embed(
                color=discord.Color.green(),
                title="Successfully edited selection.",
                description=(
                    f"Role(s) {roles_str} {verb[method]} the "
                    f"[message]({message.jump_url})."
                ),
            )
            if method == "save" and dismissed_roles:
                embed.add_field(
                    name="The following roles were already in the menu:",
                    value=dismissed_roles_str,
                )

            return embed

        return execute

    @roles.command(name="select")
    @app_commands.describe(
        channel=(
            "Channel to send the roles selection menu to. "
            "Defaults to current channel."
        ),
        content="Text to send with the roles selection menu",
    )
    async def _roles_select(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel = None,
        content: str = "Select from the following roles:",
    ):
        """Create a role selection menu, to select many roles from the list."""

        await self.roles_creation_callback(interaction, channel, content, toggle=False)

    @roles.command(name="toggle")
    @app_commands.describe(
        channel=(
            "Channel to send the roles selection menu to. "
            "Defaults to current channel."
        ),
        content="Text to send with the roles selection menu",
    )
    async def _roles_toggle(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel = None,
        content: str = "Select one of the following roles:",
    ):
        """Create a role selection menu, to select *one* role from the list."""

        await self.roles_creation_callback(interaction, channel, content, toggle=True)

    @roles.command(name="add")
    @app_commands.describe(
        message="Link or ID of the message to add roles to. Must be the bot's!"
    )
    async def _roles_add(
        self,
        interaction: discord.Interaction,
        message: app_commands.Transform[discord.Message, BotMessageTransformer],
    ):
        """Add a role to the selection menu."""

        roles = await self.roles_creation_selection(interaction)

        execute = self.roles_add_remove("save")
        embed = await execute(message, roles)

        await interaction.followup.send(embed=embed, ephemeral=True)

    @roles.command(name="remove")
    @app_commands.describe(
        message="Link or ID of the message to add roles to. Must be the bot's!"
    )
    async def _roles_remove(
        self,
        interaction: discord.Interaction,
        message: app_commands.Transform[discord.Message, BotMessageTransformer],
    ):
        """Remove a role to the selection menu."""

        roles = await self.roles_creation_selection(interaction)

        execute = self.roles_add_remove("delete")
        embed = await execute(message, roles)

        await interaction.followup.send(embed=embed, ephemeral=True)

    @roles.command(name="edit")
    @app_commands.describe(
        message="Link or ID of the message to add roles to. Must be the bot's!",
        content="New content to edit in the message.",
    )
    async def _roles_edit(
        self,
        interaction: discord.Interaction,
        message: app_commands.Transform[discord.Message, BotMessageTransformer],
        content: str,
    ):
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
        message="Link or ID of the message to add roles to. Must be the bot's!"
    )
    async def _roles_delete(
        self,
        interaction: discord.Interaction,
        message: app_commands.Transform[discord.Message, BotMessageTransformer],
    ):
        """Delete a role selection menu message."""

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

    @_roles_add.error
    @_roles_remove.error
    @_roles_edit.error
    @_roles_delete.error
    async def _roles_error(self, interaction: discord.Interaction, error: Exception):
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
            LOGGER.error("There was an error in a roles command.")
            LOGGER.error(traceback.format_exc())

    async def _create_tables(self):
        await self.bot.db.execute(
            """
            CREATE TABLE IF NOT EXISTS roles_view(
                guild_id   INTEGER NOT NULL,
                message_id INTEGER NOT NULL UNIQUE,
                toggle     BOOLEAN NOT NULL,
                view_id    INTEGER NOT NULL PRIMARY KEY
            )
            """
        )

        await self.bot.db.execute(
            """
            CREATE TABLE IF NOT EXISTS roles_component(
                component_id TEXT NOT NULL,
                name         TEXT NOT NULL,
                view_id      INTEGER NOT NULL,
                FOREIGN KEY (view_id)
                    REFERENCES roles_view (view_id)
                    ON DELETE  CASCADE
            )
            """
        )

        await self.bot.db.execute(
            """
            CREATE TABLE IF NOT EXISTS roles_role(
                role_id INTEGER NOT NULL,
                view_id INTEGER NOT NULL,
                FOREIGN KEY (view_id)
                    REFERENCES roles_view (view_id)
                    ON DELETE  CASCADE
            )
            """
        )

    async def _get_all_views(self):
        return await self.bot.db.execute_fetchall(
            """
            SELECT *
              FROM roles_view
            """
        )

    async def _get_view_from_message(self, message):
        async with self.bot.db.execute(
            """
            SELECT *
              FROM roles_view
             WHERE message_id=:message_id
            """,
            dict(message_id=message.id),
        ) as c:
            row = await c.fetchone()

        return row

    async def _get_roles(self, view_id):
        return await self.bot.db.execute_fetchall(
            """
            SELECT *
              FROM roles_role
             WHERE view_id=:view_id
            """,
            dict(view_id=view_id),
        )

    async def _get_components(self, view_id):
        return await self.bot.db.execute_fetchall(
            """
            SELECT *
              FROM roles_component
             WHERE view_id=:view_id
            """,
            dict(view_id=view_id),
        )

    async def _save_view(self, payload):
        row = await self.bot.db.execute_insert(
            """
            INSERT INTO roles_view(guild_id,
                                   message_id,
                                   toggle)
            VALUES (:guild_id,
                    :message_id,
                    :toggle)
            """,
            payload,
        )

        await self.bot.db.commit()

        view_id = row[0]
        return view_id

    async def _save_components(self, payload):
        await self.bot.db.executemany(
            """
            INSERT INTO roles_component
            VALUES (:component_id,
                    :name,
                    :view_id)
            """,
            payload,
        )

        await self.bot.db.commit()

    async def _save_roles(self, payload):
        await self.bot.db.executemany(
            """
            INSERT INTO roles_role
            VALUES (:role_id,
                    :view_id)
            """,
            payload,
        )

        await self.bot.db.commit()

    async def _delete_roles(self, payload):
        await self.bot.db.executemany(
            """
            DELETE FROM roles_role
             WHERE role_id=:role_id
            """,
            payload,
        )

        await self.bot.db.commit()

    async def _delete_view_from_message(self, message):
        """Delete the view and all the referencing rows in the other tables."""

        # delete should cascade
        await self.bot.db.execute(
            """
            DELETE FROM roles_view
             WHERE message_id=:message_id
            """,
            dict(message_id=message.id),
        )

        await self.bot.db.commit()
