import discord
from discord import app_commands
from discord.ext import commands

from .errors import TransformerMessageNotFound, TransformerNotBotMessage


class MessageTransformer(app_commands.Transformer):
    """Transformer that wraps a MessageConverter to allow convertion in AppCommands."""

    @classmethod
    async def transform(cls, interaction: discord.Interaction, value: str):
        ctx = await commands.Context.from_interaction(interaction)
        try:
            msg = await commands.MessageConverter().convert(ctx, value)
        except commands.BadArgument as e:
            raise TransformerMessageNotFound(value, cls.type(), cls, e)
        return msg


class BotMessageTransformer(MessageTransformer):
    """MessageTransformer that raises an error if the message is not from the bot."""

    @classmethod
    async def transform(cls, interaction: discord.Interaction, value: str):
        msg = await super().transform(interaction, value)

        if msg.author != interaction.guild.me:
            raise TransformerNotBotMessage()
