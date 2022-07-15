from collections import defaultdict
import logging
import random
import string

import discord
from discord import app_commands
from discord.ext import commands

from ..utils.views import confirm_prompt


LOGGER = logging.getLogger(__name__)


class Link(commands.Cog):
    """Module that allows syncing channel messages across Discord servers."""

    link = app_commands.Group(
        name="link",
        description="Manage links between channels of different servers.",
        default_permissions=discord.Permissions(manage_messages=True),
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.webhooks: dict[int, discord.Webhook] = defaultdict(
            lambda: None
        )  # for caching
        self.link_codes: dict[int, discord.abc.GuildChannel] = defaultdict(lambda: None)

    async def cog_load(self):
        await self._create_tables()

    async def create_webhook(self, channel: discord.abc.GuildChannel):
        """Create a webhook in the requested channel, and save it to database."""

        LOGGER.info(f"Webhook for {channel.id=} does not exist. Creating a new one.")
        webhook = await channel.create_webhook(
            name=f"{self.bot.user.name} - Link",
            avatar=await self.bot.user.display_avatar.read(),
        )
        await self._save_webhook(webhook)
        return webhook

    async def get_channel_webhook(
        self, channel: discord.abc.GuildChannel
    ) -> discord.Webhook:
        """Get the webhook associated to the channel, and create one if it does not
        already exist.
        """
        if self.webhooks[channel.id] is None:
            row = await self._get_webhook(channel)
            try:
                webhook = discord.Webhook.from_url(
                    row["url"], session=self.bot.http_session
                )
                self.webhooks[channel.id] = await webhook.fetch()
            except (TypeError, discord.NotFound):
                self.webhooks[channel.id] = await self.create_webhook(channel)

        return self.webhooks[channel.id]

    async def send_to_webhooks(self, message: discord.Message, group: list[int]):
        """Send the message to the other channels through their webhooks."""

        channels = [
            self.bot.get_channel(ch_id)
            for ch_id in group
            if ch_id != message.channel.id
        ]
        for channel in channels:
            webhook = await self.get_channel_webhook(channel)
            LOGGER.debug(
                f"Sending message from {message.channel.name} " f"to {channel.name}"
            )
            message_data = dict(
                content=message.content,
                username=message.author.display_name,
                avatar_url=message.author.display_avatar.url,
                files=[
                    await attachment.to_file() for attachment in message.attachments
                ],
                tts=message.tts,
            )
            try:
                await webhook.send(**message_data)

            except discord.NotFound:
                self.webhooks[channel.id] = await self.create_webhook(channel)
                await webhook.send(**message_data)

    def get_link_code(self) -> str:
        """Generate a unique random link code"""

        def generate_code(length: int = 6) -> str:
            return "".join(
                random.choices(string.ascii_uppercase + string.digits, k=length)
            )

        while (code := generate_code()) in self.link_codes.values():
            pass

        return code

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Transfer messages sent in registered channels to the others in its group."""

        author = message.author
        ctx = await self.bot.get_context(message)
        if author.bot or ctx.valid:
            # do not send bot messages, nor valid text-commands
            return

        if group := await self._get_channels_group(message.channel):
            await self.send_to_webhooks(message, group)

    @link.command(name="create")
    @app_commands.describe(code="Unique pairing code.")
    async def link_create(self, interaction: discord.Interaction, code: str = None):
        """Get the linking code for this channel or link to a group.

        This marks the channel as ready for pairing. Simply use the command with the
        code in another channel to create a channel group where messages sent in one
        will be propagated to the other channels.
        """
        webhook = await self.get_channel_webhook(interaction.channel)
        LOGGER.debug(
            f"Using webhook {webhook.id} for channel {interaction.channel.name}"
        )
        if code is None:
            # start linking channels
            if interaction.channel.id in self.link_codes.values():
                await interaction.response.send_message(
                    "You are already setting up this channel.\n"
                    f"Use `/{interaction.command.qualified_name} code: "
                    f"{self.link_codes[interaction.channel.id]}` "
                    "in another channel to link them together."
                )

            else:
                link_code = self.get_link_code()
                self.link_codes[link_code] = interaction.channel
                LOGGER.debug(
                    f"Generating link code {link_code} for "
                    f"channel {interaction.channel.id}"
                )

                await interaction.response.send_message(
                    "You started setup for linkling this channel with others!\n"
                    f"Use `/{interaction.command.qualified_name} code: {link_code}` "
                    "in another channel to link them together."
                )

        else:
            # linking with another channel
            other_channel = self.link_codes[code]
            channels = [interaction.channel, other_channel]
            groups = [await self._get_group_id(channel) for channel in channels]
            if other_channel is None:
                await interaction.response.send_message(
                    f"There is no channel currently being setup with code `{code}`."
                )

            elif groups[0] == groups[1] and groups[0] is not None:
                await interaction.response.send_message(
                    f"{channels[0].name} and {channels[1]} are already linked."
                )

            else:
                try:
                    group_id = min(g for g in groups if g is not None)
                except ValueError:
                    # empty sequence
                    group_id = await self._create_group()

                for channel in channels:
                    await self._save_webhook_group(self.webhooks[channel.id], group_id)

                await interaction.response.send_message(
                    f"Successfully linked channels {channels[0].name} and "
                    f"{channels[1].name} together!"
                )
                LOGGER.debug(f"Removing used link_code for {other_channel.name}.")
                del self.link_codes[code]

    @link.command(name="remove")
    async def link_remove(self, interaction: discord.Interaction):
        """Remove the link between this channel and the others from the group."""

        group = await self._get_channels_group(interaction.channel)
        n_other = len(group) - 1
        confirm = await confirm_prompt(
            interaction,
            "Do you really want to remove the link between this "
            f"channel and the {n_other} others?",
        )
        if confirm:
            # remove webhook from channel
            # remove webhook from DB
            webhook = self.webhooks[interaction.channel.id]
            if webhook is None:
                webhook = await self.get_channel_webhook(interaction.channel)
            await webhook.delete()
            await self._delete_webhook(interaction.channel)
            del self.webhooks[interaction.channel.id]
            LOGGER.debug(
                f"Removed link between {interaction.channel.name} and {n_other} others"
            )

            await interaction.followup.send(
                f"Link between this channel and {n_other} others removed!"
            )

    @link.command(name="check")
    async def link_check(self, interaction: discord.Interaction):
        """Check the links between this channel and the others from the group."""

        channels = [
            self.bot.get_channel(ch_id)
            for ch_id in await self._get_channels_group(interaction.channel)
            if ch_id != interaction.channel.id
        ]
        embed = discord.Embed(title="Link", color=discord.Color.blurple())
        if channels:
            description = (
                "This channel is currently linked with "
                f"{len(channels)} other channel(s)."
            )
            embed.add_field(
                name="Channels",
                value="\n".join(
                    f"**#{channel.name}** from {channel.guild.name}"
                    for channel in channels
                ),
            )

        else:
            description = "This channel is not linked to other channels."

        embed.description = description

        await interaction.response.send_message(embed=embed)

    async def _create_tables(self):
        """Create the necessary database tables."""

        await self.bot.db.execute(
            """
            CREATE TABLE IF NOT EXISTS link_group(
                group_id INTEGER NOT NULL PRIMARY KEY
            )
            """
        )
        await self.bot.db.execute(
            """
            CREATE TABLE IF NOT EXISTS link_webhook(
                channel_id INTEGER NOT NULL,
                group_id   INTEGER,
                url        TEXT NOT NULL,
                UNIQUE (channel_id),
                FOREIGN KEY (group_id)
                    REFERENCES link_group (group_id)
            )
            """
        )
        await self.bot.db.commit()

    async def _create_group(self) -> int:
        """Create a new group, with auto-incremented ID."""

        row = await self.bot.db.execute_insert(
            """
             INSERT INTO link_group
            DEFAULT VALUES
            """
        )
        LOGGER.debug(f"Created link_group with ID {row[0]}.")
        await self.bot.db.commit()
        return row[0]

    async def _get_group_id(self, channel: discord.abc.GuildChannel) -> int:
        """Get the group ID of a channel, or None if not in a group."""

        async with self.bot.db.execute(
            """
            SELECT group_id
              FROM link_webhook
             WHERE channel_id=:channel_id
            """,
            dict(channel_id=channel.id),
        ) as c:
            row = await c.fetchone()

        if row:
            return row["group_id"]
        else:
            return None

    async def _get_channels_group(self, channel: discord.abc.GuildChannel) -> list[int]:
        """Get the IDs of the channels in the same group as the requested channel."""

        rows = await self.bot.db.execute_fetchall(
            """
            SELECT channel_id
              FROM link_webhook
             WHERE group_id=(
                SELECT group_id
                  FROM link_webhook
                 WHERE channel_id=:channel_id
             )
            """,
            dict(channel_id=channel.id),
        )
        return [row["channel_id"] for row in rows]

    async def _get_webhook(self, channel: discord.abc.GuildChannel):
        """Get webhook information associated with the requested channel."""

        async with self.bot.db.execute(
            """
            SELECT *
              FROM link_webhook
             WHERE channel_id=:channel_id
            """,
            dict(channel_id=channel.id),
        ) as c:
            row = await c.fetchone()

        return row

    async def _save_webhook(self, webhook: discord.Webhook):
        """Save or update the webhook information associated to a channel."""

        await self.bot.db.execute(
            """
            INSERT INTO link_webhook(channel_id,
                                     url)
            VALUES (:channel_id,
                    :url)
                ON CONFLICT(channel_id) DO
            UPDATE SET url=:url
             WHERE channel_id=:channel_id
            """,
            dict(channel_id=webhook.channel_id, url=webhook.url),
        )
        await self.bot.db.commit()

    async def _save_webhook_group(self, webhook: discord.Webhook, group_id: int):
        """Update the webhook with the group ID."""

        await self.bot.db.execute(
            """
            UPDATE link_webhook
               SET group_id=:group_id
             WHERE channel_id=:channel_id
            """,
            dict(channel_id=webhook.channel_id, group_id=group_id),
        )
        await self.bot.db.commit()

    async def _delete_webhook(self, channel: discord.abc.GuildChannel):
        """Remove webhook information from the database."""

        await self.bot.db.execute(
            """
            DELETE FROM link_webhook
             WHERE channel_id=:channel_id
            """,
            dict(channel_id=channel.id),
        )
        await self.bot.db.commit()
