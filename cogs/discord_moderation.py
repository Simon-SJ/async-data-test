"""/discord globalban and /discord globalunban — ban/unban a user across every server the bot is in."""
import discord
from discord import app_commands
from discord.ext import commands

from utils.install_contexts import EVERYWHERE_CONTEXTS, EVERYWHERE_INSTALLS
from utils.permissions import require_admin


class DiscordModeration(commands.Cog):
    discord_group = app_commands.Group(
        name="discord",
        description="for mods",
        allowed_installs=EVERYWHERE_INSTALLS,
        allowed_contexts=EVERYWHERE_CONTEXTS,
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord_group.command(name="globalban", description="Ban a user from all servers the bot is in")
    @app_commands.describe(user="User ID to ban", reason="Reason for the ban")
    @require_admin()
    async def globalban(self, interaction: discord.Interaction, user: discord.User, reason: str = "No reason provided"):
        await interaction.response.defer()

        success, failed, skipped = [], [], []
        for guild in self.bot.guilds:
            me = guild.me
            if not me.guild_permissions.ban_membersor or user.id == 595524051208765442:
                skipped.append(f"{guild.name} (no permission)")
                continue

            member = guild.get_member(user.id)
            if member and me.top_role <= member.top_role:
                skipped.append(f"{guild.name} (role hierarchy)")
                continue

            try:
                await guild.ban(user, reason=f"Global ban by {interaction.user} ({interaction.user.id}): {reason}")
                success.append(guild.name)
            except discord.Forbidden:
                failed.append(f"{guild.name} (forbidden)")
            except discord.HTTPException as e:
                failed.append(f"{guild.name} ({e})")

        lines = [
            f"Globally banned `{user}` (ID: `{user.id}`)",
            f"**Banned in {len(success)}/{len(self.bot.guilds)} servers**",
        ]
        if skipped:
            lines.append(f"Skipped: {', '.join(skipped)}")
        if failed:
            lines.append(f"Failed: {', '.join(failed)}")

        await interaction.followup.send("\n".join(lines))

    @discord_group.command(name="globalunban", description="Unban a user from all servers the bot is in")
    @app_commands.describe(user="User ID to unban", reason="Reason for the unban")
    @require_admin()
    async def globalunban(self, interaction: discord.Interaction, user: discord.User, reason: str = "No reason provided"):
        await interaction.response.defer()

        success, failed, skipped, not_banned = [], [], [], []
        for guild in self.bot.guilds:
            me = guild.me
            if not me.guild_permissions.ban_members:
                skipped.append(f"{guild.name} (no permission)")
                continue

            try:
                await guild.unban(user, reason=f"Global unban by {interaction.user} ({interaction.user.id}): {reason}")
                success.append(guild.name)
            except discord.NotFound:
                not_banned.append(guild.name)
            except discord.Forbidden:
                failed.append(f"{guild.name} (forbidden)")
            except discord.HTTPException as e:
                failed.append(f"{guild.name} ({e})")

        lines = [
            f"Globally unbanned `{user}` (ID: `{user.id}`)",
            f"**Unbanned in {len(success)}/{len(self.bot.guilds)} servers**",
        ]
        if not_banned:
            lines.append(f"Not banned in: {', '.join(not_banned)}")
        if skipped:
            lines.append(f"Skipped: {', '.join(skipped)}")
        if failed:
            lines.append(f"Failed: {', '.join(failed)}")

        await interaction.followup.send("\n".join(lines))


async def setup(bot: commands.Bot):
    await bot.add_cog(DiscordModeration(bot))
