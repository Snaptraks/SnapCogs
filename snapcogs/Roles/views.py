import logging
from secrets import token_hex

import discord
from discord import ButtonStyle
from discord.ui import View, Button, Select, Item


LOGGER = logging.getLogger(__name__)


class RolesCreateSelect(Select):
    """Select menu to select which roles will be available to select in the message."""

    def __init__(self, roles: list[discord.Role]):
        options = [discord.SelectOption(label=role.name) for role in roles]
        self._roles = roles
        super().__init__(
            placeholder="Select roles from the available list.",
            options=options,
            max_values=len(options),
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_roles = sorted(
            [discord.utils.get(self._roles, name=value) for value in self.values],
            reverse=True,
        )
        await interaction.response.defer()
        self.view.stop()


class RolesCreateView(View):
    """View sent to create a roles selection menu for members."""

    def __init__(self, roles: list[discord.Role], *, author: discord.Member):
        super().__init__()
        self.author = author
        select = RolesCreateSelect(roles)
        self.add_item(select)

    async def interaction_check(self, interaction: discord.Interaction):
        """Only the command author can use the View."""

        return interaction.user == self.author


class RolesSelect(Select):
    placeholder = "Select roles"

    def __init__(self, roles, *, toggle: bool, custom_id: str):
        roles = sorted(roles, reverse=True)
        options = [discord.SelectOption(label=role.name) for role in roles]
        self._roles = roles
        super().__init__(
            placeholder=self.placeholder,
            options=options,
            max_values=1 if toggle else len(options),
            custom_id=custom_id,
        )

    async def callback(self, interaction: discord.Interaction):
        # guild = interaction.guild
        member = interaction.user

        selected_roles = [
            discord.utils.get(self._roles, name=value) for value in self.values
        ]
        added_roles = [role for role in selected_roles if role not in member.roles]
        removed_roles = [
            role
            for role in self._roles
            if (role in member.roles) and (role not in selected_roles)
        ]

        if removed_roles:
            LOGGER.debug(
                f"Removing roles {', '.join([str(r) for r in removed_roles])} "
                f"to {member}"
            )
            await member.remove_roles(*removed_roles)

        if added_roles:
            added_roles_str = ", ".join([r.name for r in added_roles])
            LOGGER.debug(f"Adding roles {added_roles_str} to {member}")
            await member.add_roles(*added_roles)

        await interaction.response.send_message(
            embed=discord.Embed(
                title=(
                    "Setting your roles to "
                    f"{', '.join(r.name for r in selected_roles)}."
                ),
                color=discord.Color.green(),
            ),
            ephemeral=True,
        )


class RolesView(View):
    def __init__(
        self,
        roles: list[discord.Role],
        *,
        toggle=False,
        components_id: dict[str, str] = None,
    ):
        super().__init__(timeout=None)

        if components_id is None:
            components_id = {
                "select": token_hex(16),
                "clear": token_hex(16),
            }
        self.toggle = toggle
        self.components_id = components_id
        self.roles = roles

        select = RolesSelect(roles, toggle=toggle, custom_id=components_id["select"])
        self.add_item(select)

        clear = Button(
            label="Clear",
            style=ButtonStyle.red,
            emoji="\N{HEAVY MINUS SIGN}",
            custom_id=components_id["clear"],
            row=4,
        )
        clear.callback = self.clear_callback
        self.add_item(clear)

    async def clear_callback(self, interaction: discord.Interaction):
        member = interaction.user
        removed_roles = [r for r in self.roles if r in member.roles]

        if removed_roles:
            removed_roles_str = ", ".join(r.name for r in removed_roles)
            LOGGER.debug(
                f"Removing roles {removed_roles_str} " f"from {interaction.user}"
            )
            await member.remove_roles(*removed_roles)

        await interaction.response.send_message(
            "Cleared your roles.", ephemeral=True,
        )

    async def on_error(
        self, error: Exception, item: Item, interaction: discord.Interaction
    ):
        if isinstance(error, KeyError):
            await interaction.response.send_message(
                "There was an error. You need to select at least one role.",
                ephemeral=True,
            )
        else:
            raise error
