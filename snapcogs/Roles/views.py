import logging
from collections.abc import Iterable
from secrets import token_hex

import discord
from discord import ButtonStyle, Color
from discord.ui import Button, Item, Select, View

LOGGER = logging.getLogger(__name__)


class RolesCreateSelect(Select):
    """Select menu to select which roles will be available to select in the message."""

    def __init__(self, roles: list[discord.Role]):
        options = [discord.SelectOption(label=role.name) for role in roles]
        self._roles = roles
        self.view: RolesCreateView
        super().__init__(
            placeholder="Select roles from the available list.",
            options=options,
            max_values=len(options),
        )

    async def callback(self, interaction: discord.Interaction):
        selected_roles = [
            discord.utils.get(self._roles, name=value) for value in self.values
        ]
        self.view.selected_roles = sorted(
            [r for r in selected_roles if r is not None],
            reverse=True,
        )
        await interaction.response.defer()
        self.view.stop()


class RolesCreateView(View):
    """View sent to create a roles selection menu for members."""

    selected_roles: list[discord.Role]

    def __init__(self, roles: list[discord.Role], *, author: discord.Member):
        super().__init__()
        self.author = author
        select = RolesCreateSelect(roles)
        self.add_item(select)

    async def interaction_check(self, interaction: discord.Interaction):
        """Only the command author can use the View."""

        return interaction.user == self.author


class RolesSelect(Select):
    """Select menu with the list of assignable roles."""

    def __init__(self, roles: Iterable[discord.Role], *, toggle: bool, custom_id: str):
        roles = sorted(roles, reverse=True)
        options = [discord.SelectOption(label=role.name) for role in roles]
        self._roles = roles
        super().__init__(
            placeholder="Select roles",
            options=options,
            max_values=1 if toggle else len(options),
            custom_id=custom_id,
        )

    async def callback(self, interaction: discord.Interaction):
        """Edit the roles of the member, removing unselected roles
        and adding the selected ones
        """

        member = interaction.user
        assert isinstance(member, discord.Member)

        selected_roles = [
            discord.utils.get(self._roles, name=value) for value in self.values
        ]
        selected_roles = [r for r in selected_roles if r is not None]
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
                color=Color.green(),
            ),
            ephemeral=True,
        )


class RolesView(View):
    """User facing View where they can select roles to assign themselves."""

    def __init__(
        self,
        roles: Iterable[discord.Role],
        *,
        toggle=False,
        components_id: dict[str, str] | None = None,
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
        """Remove the roles in the select menu from the member."""

        member = interaction.user
        assert isinstance(member, discord.Member)
        removed_roles = [r for r in self.roles if r in member.roles]

        if removed_roles:
            removed_roles_str = ", ".join(r.name for r in removed_roles)
            LOGGER.debug(
                f"Removing roles {removed_roles_str} " f"from {interaction.user}"
            )
            await member.remove_roles(*removed_roles)

        await interaction.response.send_message(
            embed=discord.Embed(
                title=("Cleared your roles."),
                color=Color.green(),
            ),
            ephemeral=True,
        )

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: Item
    ):
        if isinstance(error, KeyError):
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="There was an error, you need to select at least one role.",
                    color=Color.red(),
                ),
                ephemeral=True,
            )
        else:
            raise error
