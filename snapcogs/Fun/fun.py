import asyncio
import io
import json
from pathlib import Path
import random

import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageSequence


COG_PATH = Path(__file__).parent.resolve()


class Fun(commands.Cog):
    """Collection of useless but fun commands."""

    def __init__(self, bot):
        self.bot = bot

        self.bonk_context_menu = app_commands.ContextMenu(
            name="Bonk", callback=self._bonk_context_menu,
        )
        self.bot.tree.add_command(self.bonk_context_menu)

        self.lick_context_menu = app_commands.ContextMenu(
            name="Lick", callback=self._lick_context_menu,
        )
        self.bot.tree.add_command(self.lick_context_menu)

    @app_commands.command(name="8ball")
    @app_commands.describe(question="The question to ask the Magic 8 Ball.")
    async def _8ball(self, interaction: discord.Interaction, question: str):
        """Fortune-telling or advice seeking."""

        embed = discord.Embed(title="Ask the Magic 8 Ball").set_thumbnail(
            url="https://emojipedia-us.s3.dualstack.us-west-1.amazonaws.com/thumbs/120/twitter/322/pool-8-ball_1f3b1.png"  # noqa: E501
        )

        await interaction.response.defer(thinking=True)

        r = random.randrange(50)
        if r != 0:
            with open(COG_PATH / "8ball_answers.json", "r") as f:
                answers = json.load(f)
            _question = tuple(sorted(question))
            i = hash(_question) % len(answers)
            answer = answers[i]

            embed.description = f"> {question}\n\n**{answer}**"

            await asyncio.sleep(1.5)
            await interaction.followup.send(embed=embed)

        else:
            # sends a fun picture!
            avatar = io.BytesIO(await interaction.user.display_avatar.read())

            # Edit template with avatar
            bytes = await self.bot.loop.run_in_executor(
                None, self._assemble_8ball_image, avatar
            )

            file = discord.File(bytes, filename="8ball.png")
            embed.set_image(url=f"attachment://{file.filename}")
            embed.description = f"> {question}"

            await interaction.followup.send(embed=embed, file=file)

    @commands.hybrid_command(name="bonk")
    @app_commands.describe(member="Member to bonk", text="Text to add to the image")
    async def bonk_command(self, ctx, member: discord.Member, *, text: str = None):
        """Bonk a member, and add a message!
        Due to the member argument not being last, you will have to
        use a mention (@User Here) or quote "User Here" their name
        if it contains spaces.
        """

        await ctx.reply(file=await self.create_bonk_file(member, text))

    @bonk_command.error
    async def bonk_error(self, ctx, error):
        """Error handler for the bonk command."""

        if isinstance(
            error, (commands.MemberNotFound, commands.MissingRequiredArgument)
        ):
            await ctx.reply(error)

        else:
            raise error

    async def _bonk_context_menu(
        self, interaction: discord.Interaction, member: discord.Member
    ):
        """Bonk a member!"""

        await interaction.response.send_message(
            file=await self.create_bonk_file(member, None)
        )

    async def create_bonk_file(self, member, text=None):
        """Common funtion to fetch the member avatar, and create the file to send."""

        avatar = io.BytesIO(await member.display_avatar.read())
        bytes = await self.bot.loop.run_in_executor(
            None, self._assemble_bonk_image, avatar, text
        )
        return discord.File(bytes, filename="bonk.png")

    async def _lick_context_menu(
        self, interaction: discord.Interaction, member: discord.Member
    ):
        bytes = await self.bot.loop.run_in_executor(
            None,
            self._assemble_lick_gif,
            io.BytesIO(await member.display_avatar.read()),
        )

        file = discord.File(bytes, filename="lick.gif")

        await interaction.response.send_message(file=file)

    def _assemble_8ball_image(self, avatar_bytes):
        # needed files
        avatar = Image.open(avatar_bytes)
        template = Image.open(COG_PATH / "8ball_filter.png")
        new = Image.new("RGBA", template.size)

        # big profile picture
        big = avatar.resize((375, 375), Image.ANTIALIAS)
        new.paste(big, (349, 70))

        # small profile picture
        small = avatar.resize((204, 204), Image.ANTIALIAS)
        new.paste(small, (105, 301))

        new.paste(template, mask=template)
        bytes = io.BytesIO()
        new.save(bytes, format="png")
        bytes.seek(0)

        return bytes

    def _assemble_bonk_image(self, avatar_bytes, text=None):
        avatar = Image.open(avatar_bytes)
        template = Image.open(COG_PATH / "bonk_template.png")

        new = Image.new("RGBA", template.size)

        # under the bat
        head = avatar.resize((200, 200), Image.ANTIALIAS)
        new.paste(head, (425, 235))

        new.paste(template, mask=template)

        if text is not None:
            # add text
            draw = ImageDraw.Draw(new)
            font = ImageFont.truetype("impact.ttf", 38)
            stroke_width = 2
            w, h = font.getsize(text, stroke_width=stroke_width)
            mx, my = (380, 60)  # middle
            x, y = mx - w // 2, my - h // 2

            draw.text(
                (x, y),
                text,
                font=font,
                fill=(255, 255, 255),
                stroke_width=stroke_width,
                stroke_fill=(0, 0, 0),
            )

        edited = io.BytesIO()
        new.save(edited, format="png")
        edited.seek(0)

        return edited

    def _assemble_lick_gif(self, avatar_bytes):
        avatar = Image.open(avatar_bytes)
        lick_gif = Image.open(COG_PATH / "lick_template.gif")
        size = (lick_gif.size[1], lick_gif.size[1])

        mask = Image.new("RGBA", size)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0) + size, fill=(0, 0, 0, 255))
        avatar = ImageOps.fit(avatar, mask.size)

        frames = []
        for i, frame in enumerate(ImageSequence.Iterator(lick_gif)):
            frame = frame.convert("RGBA")
            box = (frame.size[0] - frame.size[1] - 50, 0, *frame.size)
            frame = frame.crop(box=box)
            base = Image.new("RGBA", frame.size)
            base.paste(avatar)
            base.paste(frame, mask=frame)
            frames.append(base)

        bytes = io.BytesIO()
        frames[0].save(
            bytes, save_all=True, append_images=frames[1:], loop=0, format="gif"
        )
        bytes.seek(0)

        return bytes
