from secrets import token_hex

import discord
from discord import ButtonStyle
from discord.ui import View, Button, Select, Item


class RolesSelect(Select):
    placeholder = "Select roles"

    def __init__(self, roles, *, custom_id, toggle=False):
        options = [discord.SelectOption(label=role.name) for role in roles]
        self.id_map = {role.name: role.id for role in roles}
        super().__init__(
            placeholder=self.placeholder,
            options=options,
            max_values=1 if toggle else len(options),
            custom_id=custom_id,
        )

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        selected_roles = [guild.get_role(self.id_map[name]) for name in self.values]
        self.view.selected_roles[interaction.user] = selected_roles


class RolesView(View):
    def __init__(self, roles: list[discord.Role], components_id: dict[str, str] = None):
        super().__init__(timeout=None)

        if components_id is None:
            components_id = {
                "select": token_hex(16),
                "add": token_hex(16),
                "remove": token_hex(16),
            }
        self.components_id = components_id
        self.roles = roles

        select = RolesSelect(roles, custom_id=components_id["select"])
        self.add_item(select)
        self.selected_roles = {}

        add = Button(
            label="Add",
            style=ButtonStyle.green,
            emoji="\N{HEAVY PLUS SIGN}",
            custom_id=components_id["add"],
            row=4,
        )
        add.callback = self.button_callback("add_roles")
        self.add_item(add)

        remove = Button(
            label="Remove",
            style=ButtonStyle.red,
            emoji="\N{HEAVY MINUS SIGN}",
            custom_id=components_id["remove"],
            row=4,
        )
        remove.callback = self.button_callback("remove_roles")
        self.add_item(remove)

    def button_callback(self, method: str):
        async def callback(interaction: discord.Interaction):
            member = interaction.user
            add_remove_roles = getattr(member, method)
            await add_remove_roles(*self.selected_roles[member])
            roles_str = ", ".join(role.mention for role in self.selected_roles[member])
            await interaction.response.send_message(
                f"Changing roles {roles_str} for member {member.mention}.",
                ephemeral=True,
            )

        return callback

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


class RolesToggleSelect(RolesSelect):
    placeholder = "Select one role"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, toggle=True)

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user
        roles = [guild.get_role(id) for id in self.id_map.values()]
        # always exactly one value selected
        selected_role = guild.get_role(self.id_map[self.values[0]])

        await member.remove_roles(*roles)
        await member.add_roles(selected_role)

        await interaction.response.send_message(
            f"Setting role {selected_role.mention} for member {member.mention}.",
            ephemeral=True,
        )


class RolesToggleView(View):
    def __init__(self, roles: list[discord.Role], components_id: dict[str, str] = None):
        super().__init__(timeout=None)

        if components_id is None:
            components_id = {
                "select": token_hex(16),
                "clear": token_hex(16),
            }
        self.components_id = components_id
        self.roles = roles

        select = RolesToggleSelect(roles, custom_id=components_id["select"])
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
        await member.remove_roles(*self.roles)
        await interaction.response.send_message(
            f"Cleared the roles for member {member.mention}.", ephemeral=True,
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
