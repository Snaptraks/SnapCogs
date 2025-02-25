from discord import app_commands


class TransformerMessageNotFound(app_commands.TransformerError):
    def __init__(self, value, opt_type, transformer, e):
        self.original = e

        super().__init__(value, opt_type, transformer)


class TransformerNotBotMessage(app_commands.AppCommandError):
    def __init__(self):
        super().__init__("Bot is not the author of the message.")
