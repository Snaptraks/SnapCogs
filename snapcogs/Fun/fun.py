import asyncio
import io
import json
import logging
import random
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageSequence

from ..bot import Bot

LOGGER = logging.getLogger(__name__)
COG_PATH = Path(__file__).parent.resolve()

_max_img = 256
MAX_IMG_SIZE = (_max_img, _max_img)


class Fun(commands.Cog):
    """Collection of useless but fun commands."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @app_commands.command(name="8ball")
    @app_commands.describe(question="What do you want to ask the Magic 8 Ball?")
    async def _8ball(self, interaction: discord.Interaction, question: str):
        """Fortune-telling or advice seeking."""

        embed = discord.Embed(title="Ask the Magic 8 Ball").set_thumbnail(
            url="https://upload.wikimedia.org/wikipedia/commons/thumb/f/fd/8-Ball_Pool.svg/240px-8-Ball_Pool.svg.png"  # noqa: E501
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
            _bytes = await asyncio.to_thread(self._assemble_8ball_image, avatar)

            file = discord.File(_bytes, filename="8ball.png")
            embed.set_image(url=f"attachment://{file.filename}")
            embed.description = f"> {question}"

            await interaction.followup.send(embed=embed, file=file)

    @app_commands.command()
    @app_commands.describe(member="Member to bonk.", text="Text to add to the image.")
    async def bonk(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        text: str | None = None,
    ):
        """Bonk a member, and add a message!"""

        if member == member.guild.me:
            content = "Ha! I'm not bonking myself, I'm not an idiot."
        else:
            content = None

        await interaction.response.send_message(
            content=content,
            file=await self.create_bonk_file(member, text),
        )

    @bonk.error
    async def bonk_error(self, interaction: discord.Interaction, error: BaseException):
        """Error handler for the bonk command."""

        if isinstance(
            error, (commands.MemberNotFound, commands.MissingRequiredArgument)
        ):
            await interaction.response.send_message(error, ephemeral=True)

        else:
            interaction.extras["error_handled"] = False

    async def create_bonk_file(
        self, member: discord.Member, text: str | None = None
    ) -> discord.File:
        """Common funtion to fetch the member avatar, and create the file to send."""

        avatar = io.BytesIO(await member.display_avatar.read())
        if member == member.guild.me:
            # self bonk
            _bytes = await asyncio.to_thread(self._assemble_self_bonk_image, avatar)
        else:
            _bytes = await asyncio.to_thread(self._assemble_bonk_image, avatar, text)

        return discord.File(_bytes, filename="bonk.png")

    @app_commands.command()
    @app_commands.describe(member="Member to lick.")
    async def lick(self, interaction: discord.Interaction, member: discord.Member):
        """Lick a member! It's not as lewd as it sounds..."""

        _bytes = await asyncio.to_thread(
            self._assemble_lick_gif,
            io.BytesIO(await member.display_avatar.read()),
        )
        file = discord.File(_bytes, filename="lick.gif")

        await interaction.response.send_message(file=file)

    @app_commands.command()
    @app_commands.describe(member="Member for Kirby to eat.")
    async def kirby(self, interaction: discord.Interaction, member: discord.Member):
        """Feed a member to Kirby!"""

        _bytes = await asyncio.to_thread(
            self._assemble_kirby_image,
            io.BytesIO(await member.display_avatar.read()),
        )
        file = discord.File(_bytes, filename="kirby.png")

        await interaction.response.send_message(file=file)

    def _assemble_8ball_image(self, avatar_bytes) -> io.BytesIO:
        # needed files
        avatar = Image.open(avatar_bytes)
        template = Image.open(COG_PATH / "8ball_filter.png")
        new = Image.new("RGBA", template.size)

        # big profile picture
        big = avatar.resize((375, 375))
        new.paste(big, (349, 70))

        # small profile picture
        small = avatar.resize((204, 204))
        new.paste(small, (105, 301))

        new.paste(template, mask=template)
        _bytes = io.BytesIO()
        new.save(_bytes, format="png")
        _bytes.seek(0)

        return _bytes

    def _assemble_bonk_image(self, avatar_bytes: io.BytesIO, text=None) -> io.BytesIO:
        avatar = Image.open(avatar_bytes)
        template = Image.open(COG_PATH / "bonk_template.png")

        new = Image.new("RGBA", template.size)

        # under the bat
        head = avatar.resize((200, 200))
        new.paste(head, (425, 235))

        new.paste(template, mask=template)

        if text is not None:
            # add text
            draw = ImageDraw.Draw(new)
            font = ImageFont.truetype("impact.ttf", 46)
            stroke_width = 2
            left, top, right, bottom = font.getbbox(text, stroke_width=stroke_width)
            w = right - left
            h = bottom - top
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

        new.thumbnail(MAX_IMG_SIZE)
        edited = io.BytesIO()
        new.save(edited, format="png")
        edited.seek(0)

        return edited

    def _assemble_self_bonk_image(self, avatar_bytes: io.BytesIO) -> io.BytesIO:
        avatar = Image.open(avatar_bytes)
        template = Image.open(COG_PATH / "self_bonk.png")

        avatar_left = avatar.resize((250, 250))
        avatar_right = avatar_left.transpose(Image.FLIP_LEFT_RIGHT)

        template.paste(avatar_left, (175, -20), mask=avatar_left)
        template.paste(avatar_right, (1028, 16), mask=avatar_right)

        template.thumbnail(MAX_IMG_SIZE)
        edited = io.BytesIO()
        template.save(edited, format="png")
        edited.seek(0)

        return edited

    def _assemble_lick_gif(self, avatar_bytes: io.BytesIO) -> io.BytesIO:
        avatar = Image.open(avatar_bytes)
        lick_gif = Image.open(COG_PATH / "lick_template.gif")
        size = (lick_gif.size[1], lick_gif.size[1])

        mask = Image.new("RGBA", size)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0) + size, fill=(0, 0, 0, 255))
        avatar = ImageOps.fit(avatar, mask.size)

        frames = []
        for frame in ImageSequence.Iterator(lick_gif):
            frame = frame.convert("RGBA")
            box = (frame.size[0] - frame.size[1] - 50, 0, *frame.size)
            frame = frame.crop(box=box)
            base = Image.new("RGBA", frame.size)
            base.paste(avatar)
            base.paste(frame, mask=frame)
            base.thumbnail(MAX_IMG_SIZE)
            frames.append(base)

        _bytes = io.BytesIO()
        frames[0].save(
            _bytes, save_all=True, append_images=frames[1:], loop=0, format="gif"
        )
        _bytes.seek(0)

        return _bytes

    def _assemble_kirby_image(self, avatar_bytes: io.BytesIO) -> io.BytesIO:
        avatar = Image.open(avatar_bytes)
        template = Image.open(COG_PATH / "kirby_template.png")

        new = Image.new("RGBA", (464, 351))
        head = avatar.resize((300, 300))
        new.paste(head, (164, 51))

        new.paste(template, mask=template)
        new.thumbnail(MAX_IMG_SIZE)

        edited = io.BytesIO()
        new.save(edited, format="png")
        edited.seek(0)
        return edited
