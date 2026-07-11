"""
/user add|update|delete — manage the manual booster list.
/sync — force an immediate resync.
Plus the automatic resync on startup and on relevant member updates.

Booster status is inherently per-guild, so unlike the other cogs this one
stays guild-only — /user update and /user delete take a discord.Member
parameter, which Discord can only resolve inside a guild anyway.
"""
import discord
from discord import app_commands
from discord.ext import commands

from config import GIST_MANUAL_FILE, GIST_NAMES_FILE
from services import booster_sync_service
from services import gist_store
from utils.install_contexts import GUILD_ONLY_CONTEXTS, GUILD_ONLY_INSTALLS
from utils.permissions import require_admin


class BoosterSync(commands.Cog):
    user_group = app_commands.Group(
        name="user",
        description="Manage booster list",
        allowed_installs=GUILD_ONLY_INSTALLS,
        allowed_contexts=GUILD_ONLY_CONTEXTS,
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        count = await booster_sync_service.sync_and_publish(self.bot)
        print(f"[booster_sync] Initial sync complete: {count} users in the booster list.")

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if (
            before.premium_since != after.premium_since
            or before.display_name != after.display_name
            or before.roles != after.roles
        ):
            await booster_sync_service.sync_and_publish(self.bot)

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
