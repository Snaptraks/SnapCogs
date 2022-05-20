from typing import Union

import discord
from discord.ext import commands, tasks
from . import views


class RolesCreateFlags(commands.FlagConverter):
    channel: discord.TextChannel = commands.flag(default=lambda ctx: ctx.channel)
    content: str = commands.flag(
        default="Select from the following roles:", aliases=["message"]
    )
    roles: tuple[discord.Role, ...]  # able to add more than one with the flag


class RolesAddRemoveFlags(commands.FlagConverter):
    message: Union[discord.Message, discord.PartialMessage]
    roles: tuple[discord.Role, ...]  # able to add more than one with the flag


class Roles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.persistent_views_added = False
        self._create_tables.start()

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.persistent_views_added:

            await self.load_persistent_views()
            self.persistent_views_added = True

    @commands.has_guild_permissions(manage_roles=True)
    @commands.group(aliases=["role"])
    async def roles(self, ctx):
        """Commands to create and manage role selection menus."""

        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @roles.command(name="select")
    async def roles_select(self, ctx, *, flags: RolesCreateFlags):
        """Create a role selection menu, to select many roles from the list.
        Members can select many roles from the list to assign to themselves.

        Flags:
            channel: The channel to send the message to. Channel name, ID or
                     mention works
            content: The content of the message to be sent.
                alias: message
            roles: A space-separated list of roles. Role name, ID or mention works.

        Ex: roles select roles: @Role1 @Role2 message: Select some roles!
            channel: #general
        """
        view = views.RolesView(flags.roles)
        message = await flags.channel.send(flags.content, view=view)
        await self.save_persistent_view(view, message)

    @roles.command(name="toggle")
    async def roles_toggle(self, ctx, *, flags: RolesCreateFlags):
        """Create a role toggle menu, to select only one role from the list.
        Members can select only one role from the list to assign to themselves.

        Flags:
            channel: The channel to send the message to. Channel name, ID or
                     mention works
            content: The content of the message to be sent.
                alias: message
            roles: A space-separated list of roles. Role name, ID or mention works.

        Ex: roles toggle roles: @Role1 @Role2 message: Select one roles!
            channel: #general
        """

        view = views.RolesToggleView(flags.roles)
        message = await flags.channel.send(flags.content, view=view)
        await self.save_persistent_view(view, message)

    @roles.command(name="add")
    async def roles_add(self, ctx, *, flags: RolesAddRemoveFlags):
        """Add a role to the selection list.

        Flags:
            message: ID or URL to the message containing a selection menu.
            roles: A space-separated list of roles. Role name, ID or mention works.

        Ex: roles add message: 123456789123456789 roles: @Role1 @Role2
        """

        execute = self.roles_add_remove("save")
        embed = await execute(flags.message, flags.roles)

        await ctx.reply(embed=embed)

    @roles.command(name="remove")
    async def roles_remove(self, ctx, *, flags: RolesAddRemoveFlags):
        """Remove a role from the selection list.

        Flags:
            message: ID or URL to the message containing a selection menu.
            roles: A space-separated list of roles. Role name, ID or mention works.

        Ex: roles remove message: 123456789123456789 roles: @Role1 @Role2
        """

        execute = self.roles_add_remove("delete")
        embed = await execute(flags.message, flags.roles)

        await ctx.reply(embed=embed)

    def roles_add_remove(self, method):
        async def execute(message, roles):

            view_data = await self._get_view_from_message(message)
            await getattr(self, f"_{method}_roles")(
                [dict(role_id=role.id, view_id=view_data["view_id"]) for role in roles]
            )
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

            return embed

        return execute

    @roles_add.error
    @roles_remove.error
    async def roles_add_remove_error(self, ctx, error):
        if isinstance(error, (commands.RoleNotFound, commands.MissingFlagArgument,),):
            await ctx.reply(error)

        elif isinstance(error, commands.BadUnionArgument):
            await ctx.reply(
                "Message not found. "
                "You might need to use the format `{channel ID}-{message ID}` "
                "(shift-clicking on “Copy ID”) or the message URL."
            )

        else:
            raise error

    @roles.command(name="delete")
    async def roles_delete(
        self, ctx, message: Union[discord.Message, discord.PartialMessage]
    ):
        """Delete a selection menu and its message.
        Argument `message` needs to be the mesage ID or URL.
        """

        await self._delete_view_from_message(message)
        await message.delete()

        embed = discord.Embed(
            color=discord.Color.green(),
            title="Successfully deleted selection.",
            description="Message was deleted, and removed from memory.",
        )

        await ctx.reply(embed=embed)

    @roles.command(name="edit")
    async def roles_edit(
        self,
        ctx,
        message: Union[discord.Message, discord.PartialMessage],
        *,
        content: str,
    ):
        """Edit the content of a role selection message.
        Argument `message` needs to be the mesage ID or URL. It must be a
        message sent by the bot!
        """

        await message.edit(content=content)

        embed = discord.Embed(
            color=discord.Color.green(),
            title="Successfully edited message.",
            description=(
                f"[Message]({message.jump_url}) content was edited to\n"
                f"```\n{content}\n```"
            ),
        )

        await ctx.reply(embed=embed)

    async def load_persistent_views(self):
        for view_data in await self._get_all_views():
            self.bot.add_view(
                await self.build_view(view_data), message_id=view_data["message_id"],
            )

    async def save_persistent_view(self, view, message):
        view_payload = dict(guild_id=message.guild.id, message_id=message.id)

        if isinstance(view, views.RolesView):
            view_payload["view_type"] = "select"
        elif isinstance(view, views.RolesToggleView):
            view_payload["view_type"] = "toggle"

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

        if view_data["view_type"] == "select":
            view_type = views.RolesView

        elif view_data["view_type"] == "toggle":
            view_type = views.RolesToggleView

        view = view_type(roles, components_id=components_id)

        return view

    @tasks.loop(count=1)
    async def _create_tables(self):
        await self.bot.db.execute(
            """
            CREATE TABLE IF NOT EXISTS roles_view(
                guild_id   INTEGER NOT NULL,
                message_id INTEGER NOT NULL UNIQUE,
                view_id    INTEGER NOT NULL PRIMARY KEY,
                view_type  TEXT    NOT NULL
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

    async def _get_view_from_id(self, view_id):
        async with self.bot.db.execute(
            """
            SELECT *
              FROM roles_view
             WHERE view_id=:message_id
            """,
            dict(message_id=view_id),
        ) as c:
            row = await c.fetchone()

        return row

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
                                   view_type)
            VALUES (:guild_id,
                    :message_id,
                    :view_type)
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
