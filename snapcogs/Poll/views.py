import asyncio
from collections import Counter
from dataclasses import dataclass
import io

import discord
from discord import ui
import matplotlib.pyplot as plt


@dataclass
class _ProxyTextInput:
    value: str


class PollYesNoCreate(ui.Modal, title="Poll Creation"):
    question = ui.TextInput(
        label="Question", placeholder="What is your Yes or No question?", required=True
    )
    options = _ProxyTextInput("Yes\nNo")

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("Poll created", ephemeral=True)


class PollCreate(ui.Modal, title="Poll Creation"):
    question = ui.TextInput(
        label="Question", placeholder="What do you want to ask about?", required=True
    )
    options = ui.TextInput(
        label="Options",
        placeholder="Enter one option per line (max 25)",
        required=True,
        style=discord.TextStyle.paragraph,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("Poll created", ephemeral=True)


class PollInput(ui.View):
    def __init__(self, *, author: discord.Member, modal: ui.Modal, max_values: int):
        super().__init__(timeout=None)
        self.author = author
        self.question = modal.question
        self.options = {}  # options to vote for
        self.results = {}  # what users voted for

        for i, option in enumerate(modal.options.value.split("\n")):
            value = str(i + 1)
            self.options[value] = option
            self.on_vote.add_option(label=option, value=value)

        self.on_vote.max_values = max_values

    @ui.select()
    async def on_vote(self, interaction: discord.Interaction, select: ui.Select):
        self.results[interaction.user.id] = select.values
        await self.update_message(interaction)

    @ui.button(label="Clear My Vote", style=discord.ButtonStyle.gray)
    async def on_clear(self, interaction: discord.Interaction, button: ui.Button):
        del self.results[interaction.user.id]
        await self.update_message(interaction)

    @ui.button(label="Stop Poll", style=discord.ButtonStyle.red)
    async def on_stop(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id == self.author.id:
            await interaction.response.edit_message(view=None)
            self.stop()

        else:
            await interaction.response.send_message(
                "Only the poll author can stop the voting.", ephemeral=True
            )

    async def update_message(self, interaction):
        embed, graph = await self.build_embed()
        await interaction.response.edit_message(embed=embed, attachments=[graph])

    async def build_embed(self):
        results = self._count_results()
        total_votes = len(self.results)
        top_answer = results.most_common(1)
        if top_answer:
            top_answer = top_answer[0][1]
        else:
            top_answer = None

        def bold(i, option):
            if results[i] == top_answer:
                return f"**{option}**"
            else:
                return option

        description = "\n".join(
            f"`{i:>2}.` {bold(i, option)}" for i, option in self.options.items()
        )
        graph = await asyncio.get_running_loop().run_in_executor(None, self.build_graph)
        embed = (
            discord.Embed(
                title=self.question,
                description=description,
                color=discord.Color.blurple(),
            )
            .set_image(url=f"attachment://{graph.filename}")
            .set_author(
                name=self.author.display_name, icon_url=self.author.display_avatar.url
            )
            .set_footer(text=f"{total_votes} total users voted.")
        )

        return embed, graph

    def build_graph(self):
        results = self._count_results()
        fig, ax = plt.subplots()
        if results:
            labels = [
                f"{self.options[key]}\n({value} votes)"
                for key, value in results.items()
            ]
            ax.pie(results.values(), labels=labels, wedgeprops={"width": 0.5})
        else:
            text_kwargs = dict(ha="center", va="center", fontsize=28)
            ax.text(0.5, 0.5, "No votes yet!", **text_kwargs)
            ax.set_axis_off()

        buffer = io.BytesIO()
        fig.savefig(buffer, format="png")
        plt.close(fig=fig)
        buffer.seek(0)

        return discord.File(buffer, "poll_results.png")

    def _count_results(self):
        return Counter([v for votes in self.results.values() for v in votes])
