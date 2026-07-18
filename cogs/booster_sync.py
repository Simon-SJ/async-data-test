"""
/user add|update|delete — manage the manual booster list.
/sync — force an immediate resync.
Plus the automatic resync on startup and on relevant member updates.

Booster status is inherently per-guild, so unlike the other cogs this one
stays guild-only — /user update and /user delete take a discord.Member
parameter, which Discord can only resolve inside a guild anyway.
"""
import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from config import BOOSTER_ROLE_ID, GIST_MANUAL_FILE, GIST_NAMES_FILE
from services import booster_sync_service
from services import gist_store
from utils.install_contexts import GUILD_ONLY_CONTEXTS, GUILD_ONLY_INSTALLS
from utils.permissions import require_admin

# How long to wait after the last relevant member update before actually
# syncing. Coalesces a burst of updates (e.g. several people boosting
# around the same time) into one Gist write instead of one per event.
_DEBOUNCE_SECONDS = 8.0


def _is_boosting(member: discord.Member) -> bool:
    return member.premium_since is not None or BOOSTER_ROLE_ID in {r.id for r in member.roles}


class BoosterSync(commands.Cog):
    user_group = app_commands.Group(
        name="user",
        description="Manage booster list",
        allowed_installs=GUILD_ONLY_INSTALLS,
        allowed_contexts=GUILD_ONLY_CONTEXTS,
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._debounce_task: asyncio.Task | None = None

    def cog_unload(self):
        if self._debounce_task is not None:
            self._debounce_task.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        count = await booster_sync_service.sync_and_publish(self.bot)
        print(f"[booster_sync] Initial sync complete: {count} users in the booster list.")

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        # This used to fire a full Gist sync (2 GETs + 1 PATCH) on ANY
        # role change for ANY member — including things with nothing to do
        # with boosting, like an EA suspension role or another bot's role
        # management. Across several servers with normal activity, that
        # was hitting GitHub's Gist API far more than it can sustain,
        # which is what the 409/503 flood actually was. Now it only
        # reacts to changes that can actually affect the booster list:
        # boost status flipping, or a *current* booster's display name
        # changing (a name change on a non-booster can't change the
        # output either way).
        was_boosting = _is_boosting(before)
        is_boosting = _is_boosting(after)

        relevant = was_boosting != is_boosting or (is_boosting and before.display_name != after.display_name)
        if relevant:
            self._schedule_sync()

    def _schedule_sync(self):
        """Debounce: cancel any pending sync and schedule a fresh one.
        A burst of N relevant updates in quick succession now costs one
        sync a few seconds after the last of them, not N syncs."""
        if self._debounce_task is not None and not self._debounce_task.done():
            self._debounce_task.cancel()
        self._debounce_task = asyncio.create_task(self._debounced_sync())

    async def _debounced_sync(self):
        try:
            await asyncio.sleep(_DEBOUNCE_SECONDS)
        except asyncio.CancelledError:
            return
        count = await booster_sync_service.sync_and_publish(self.bot)
        print(f"[booster_sync] Synced after member update(s): {count} users in the booster list.")

    @app_commands.command(name="sync", description="Force an immediate sync between Discord and Gist")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @require_admin()
    async def sync(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            count = await booster_sync_service.sync_and_publish(self.bot)
            await interaction.followup.send(f"Force sync complete. Data pushed to Gist. Total users: {count}")
        except Exception as e:
            await interaction.followup.send(f"Sync failed: {e}")

    @user_group.command(name="add", description="Add a user to the manual list")
    @require_admin()
    async def add(self, interaction: discord.Interaction, user_id: str, roblox_name: str):
        await interaction.response.defer()
        manual_data = await gist_store.get_file(GIST_MANUAL_FILE, default=[])
        name_overrides = await gist_store.get_file(GIST_NAMES_FILE, default={})

        for entry in manual_data:
            if entry[0] == user_id:
                entry[1] = roblox_name
                break
        else:
            manual_data.append([user_id, roblox_name])

        count = await booster_sync_service.sync_and_publish(
            self.bot, manual_override=manual_data, names_override=name_overrides
        )
        await interaction.followup.send(f"Added **{user_id}** as '{roblox_name}'. Total: {count}")

    @user_group.command(name="update", description="Update a user's Roblox name")
    @require_admin()
    async def update(self, interaction: discord.Interaction, member: discord.Member, roblox_name: str):
        await interaction.response.defer()
        manual_data = await gist_store.get_file(GIST_MANUAL_FILE, default=[])
        names = await gist_store.get_file(GIST_NAMES_FILE, default={})

        names[str(member.id)] = roblox_name

        await booster_sync_service.sync_and_publish(self.bot, manual_override=manual_data, names_override=names)
        await interaction.followup.send(f"Updated **{member.name}** to Roblox name **{roblox_name}**.")

    @user_group.command(name="delete", description="Remove a user from manual list and name overrides")
    @require_admin()
    async def delete(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.defer()
        manual_data = await gist_store.get_file(GIST_MANUAL_FILE, default=[])
        names = await gist_store.get_file(GIST_NAMES_FILE, default={})
        user_id_str = str(member.id)

        manual_data = [entry for entry in manual_data if entry[0] != user_id_str]
        names.pop(user_id_str, None)

        count = await booster_sync_service.sync_and_publish(
            self.bot, manual_override=manual_data, names_override=names
        )
        await interaction.followup.send(f"🗑️ Removed **{member.name}** from all manual lists. Total: {count}")


async def setup(bot: commands.Bot):
    await bot.add_cog(BoosterSync(bot))