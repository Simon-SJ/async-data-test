"""/ea suspend, unsuspend, blacklist, unblacklist, list."""
import time
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from config import BLACKLIST_DATASTORE_ID, EA_SERVER_ID, EA_SUSPENDED_ROLE_ID, SUSPENSION_DATASTORE_ID
from services import roblox_api
from utils.install_contexts import EVERYWHERE_CONTEXTS, EVERYWHERE_INSTALLS
from utils.logging import log_action
from utils.permissions import require_admin, require_ea_mod


class EaModeration(commands.Cog):
    ea_group = app_commands.Group(
        name="ea",
        description="for mods",
        allowed_installs=EVERYWHERE_INSTALLS,
        allowed_contexts=EVERYWHERE_CONTEXTS,
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _set_suspended_role(self, discord_account: discord.User, *, add: bool, reason: str) -> str | None:
        """Add/remove the EA-suspended role for `discord_account` in the EA server.
        Returns an error string to show the moderator, or None on success.

        NOTE: the original suspend/unsuspend commands handled a missing home
        guild/member differently — suspend reported an error, unsuspend quietly
        continued and still reported success. Standardized on the stricter
        suspend behavior for both here; flagged in chat.
        """
        home_guild = self.bot.get_guild(EA_SERVER_ID)
        if home_guild is None:
            return "couldn't find the EA server."

        member = home_guild.get_member(discord_account.id)
        if member is None:
            return f"`{discord_account}` is not in the EA server."

        role = home_guild.get_role(EA_SUSPENDED_ROLE_ID)
        if role is None:
            # Matches the original: if the role no longer exists, there's
            # nothing to assign, but this still isn't treated as failure.
            return None

        try:
            if add:
                await member.add_roles(role, reason=reason)
            elif role in member.roles:
                await member.remove_roles(role, reason=reason)
        except discord.Forbidden:
            return "missing permissions to change that role."

        return None

    @ea_group.command(name="suspend", description="Suspend a user from EA")
    @app_commands.describe(target="Roblox Username or ID", duration_days="How many days to suspend (leave empty for permanent)")
    @require_ea_mod()
    async def suspend(
        self,
        interaction: discord.Interaction,
        discord_account: discord.User,
        target: str,
        duration_days: Optional[int] = None,
    ):
        await interaction.response.defer(ephemeral=True)

        user_id, error = await roblox_api.resolve_user_id(target)
        if error:
            await interaction.followup.send(error)
            return

        suspension_data = {
            "suspended": True,
            "expires_at": int(time.time()) + (duration_days * 86400) if duration_days else None,
            "duration_days": duration_days,
        }
        ok, detail = await roblox_api.put_datastore_entry(SUSPENSION_DATASTORE_ID, str(user_id), suspension_data)
        if not ok:
            await interaction.followup.send(f"Failed to update Roblox DataStore. {detail}")
            return

        role_error = await self._set_suspended_role(discord_account, add=True, reason=f"EA suspended by {interaction.user}")
        if role_error:
            await interaction.followup.send(f"Suspended in DataStore but {role_error}")
            return

        duration_text = f"**{duration_days} day(s)**" if duration_days else "**permanently**"
        await interaction.followup.send(
            f"Successfully suspended `{target}` (ID: `{user_id}`) {duration_text} "
            f"and assigned suspended role to {discord_account.mention}."
        )

    @ea_group.command(name="unsuspend", description="Remove an EA suspension from a Roblox user")
    @app_commands.describe(target="Roblox Username or ID to unsuspend")
    @require_ea_mod()
    async def unsuspend(self, interaction: discord.Interaction, discord_account: discord.User, target: str):
        await interaction.response.defer(ephemeral=True)

        user_id, error = await roblox_api.resolve_user_id(target)
        if error:
            await interaction.followup.send(error)
            return

        ok, status = await roblox_api.delete_datastore_entry(SUSPENSION_DATASTORE_ID, str(user_id))
        if status == 404:
            await interaction.followup.send(f"User `{target}` is not currently suspended.")
            return
        if not ok:
            await interaction.followup.send(f"API Error. Status: {status}")
            return

        role_error = await self._set_suspended_role(discord_account, add=False, reason=f"EA unsuspended by {interaction.user}")
        if role_error:
            await interaction.followup.send(f"Unsuspended in DataStore but {role_error}")
            return

        await interaction.followup.send(
            f"Successfully unsuspended `{target}` (ID: `{user_id}`) and removed suspended role from {discord_account.mention}."
        )

    @ea_group.command(name="blacklist", description="Blacklist a user from specific entities")
    @app_commands.describe(
        target="Roblox Username or ID",
        entities="Entity names separated by commas (e.g. Titan, Dragon)",
        duration_days="Days until expiry (leave empty for permanent)",
    )
    @require_ea_mod()
    async def blacklist(self, interaction: discord.Interaction, target: str, entities: str, duration_days: Optional[int] = None):
        await interaction.response.defer(ephemeral=True)

        user_id, error = await roblox_api.resolve_user_id(target)
        if error:
            await interaction.followup.send(error)
            return

        _, current_data = await roblox_api.get_datastore_entry(BLACKLIST_DATASTORE_ID, str(user_id))
        current_data = current_data or {}

        entity_list = [e.strip() for e in entities.split(",")]
        expiry = int(time.time()) + (duration_days * 86400) if duration_days else None
        for entity in entity_list:
            current_data[entity] = expiry

        ok, detail = await roblox_api.put_datastore_entry(BLACKLIST_DATASTORE_ID, str(user_id), current_data)
        if not ok:
            await interaction.followup.send(f"Failed to update DataStore. {detail}")
            return

        dur_text = f"{duration_days} days" if duration_days else "Permanent"
        await interaction.followup.send(f"Blacklisted `{target}` from: **{', '.join(entity_list)}** (Duration: {dur_text})")
        await log_action(
            self.bot,
            title="EA Blacklist Added",
            description=(
                f"**User:** {target} ({user_id})\n**Entities:** {', '.join(entity_list)}\n"
                f"**Duration:** {dur_text}\n**Moderator:** {interaction.user.mention}"
            ),
            color=discord.Color.orange(),
        )

    @ea_group.command(name="unblacklist", description="Remove a blacklist for specific entities")
    @app_commands.describe(
        target="Roblox Username or ID",
        entities="Entity names to remove, separated by commas. Use 'ALL' to clear everything.",
    )
    @require_ea_mod()
    async def unblacklist(self, interaction: discord.Interaction, target: str, entities: str):
        await interaction.response.defer(ephemeral=True)

        user_id, error = await roblox_api.resolve_user_id(target)
        if error:
            await interaction.followup.send(error)
            return

        status, current_data = await roblox_api.get_datastore_entry(BLACKLIST_DATASTORE_ID, str(user_id))
        if status != 200:
            await interaction.followup.send("This user has no active blacklists.")
            return
        if not current_data:
            await interaction.followup.send("No entity data found for this user.")
            return

        if entities.upper() == "ALL":
            removed = ["ALL"]
            ok, _ = await roblox_api.delete_datastore_entry(BLACKLIST_DATASTORE_ID, str(user_id))
        else:
            to_remove = [e.strip() for e in entities.split(",")]
            removed = [e for e in to_remove if e in current_data]
            if not removed:
                await interaction.followup.send(f"User wasn't blacklisted from any of: {entities}")
                return
            for e in removed:
                del current_data[e]

            if not current_data:
                ok, _ = await roblox_api.delete_datastore_entry(BLACKLIST_DATASTORE_ID, str(user_id))
            else:
                ok, _ = await roblox_api.put_datastore_entry(BLACKLIST_DATASTORE_ID, str(user_id), current_data)

        if not ok:
            await interaction.followup.send("Error updating Roblox DataStore.")
            return

        await interaction.followup.send(f"Removed blacklist from **{', '.join(removed)}** for `{target}`.")
        await log_action(
            self.bot,
            title="🔓 EA Blacklist Removed",
            description=f"**User:** {target} ({user_id})\n**Removed:** {', '.join(removed)}\n**Moderator:** {interaction.user.mention}",
            color=discord.Color.blue(),
        )

    @ea_group.command(name="list", description="debug cmd, does not do shit")
    @require_admin()
    async def list_suspended(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        entries = await roblox_api.list_datastore_entries(SUSPENSION_DATASTORE_ID)
        print(entries)
        await interaction.followup.send("Entries printed to console.")


async def setup(bot: commands.Bot):
    await bot.add_cog(EaModeration(bot))