"""/roblox ban and /roblox unban."""
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from services import roblox_api
from utils.install_contexts import EVERYWHERE_CONTEXTS, EVERYWHERE_INSTALLS
from utils.logging import log_action
from utils.permissions import require_admin


class RobloxModeration(commands.Cog):
    roblox_group = app_commands.Group(
        name="roblox",
        description="for mods",
        allowed_installs=EVERYWHERE_INSTALLS,
        allowed_contexts=EVERYWHERE_CONTEXTS,
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @roblox_group.command(name="ban", description="Ban one or more Roblox users by ID or username")
    @app_commands.describe(
        targets="One or more Roblox usernames or user IDs, separated by commas or spaces.",
        reason="The reason for the ban.",
        time_minutes="Duration of the ban in minutes. Leave empty for a permanent ban.",
        public_reason="A message to be displayed for the banned user",
    )
    @require_admin()
    async def ban(
        self,
        interaction: discord.Interaction,
        targets: str,
        reason: str,
        time_minutes: Optional[float] = None,
        public_reason: Optional[str] = None,
    ):
        await interaction.response.defer()

        raw_targets = [t.strip() for t in targets.replace(",", " ").split() if t.strip()]
        if not raw_targets:
            await interaction.followup.send("No valid targets provided.")
            return

        successes, failures = [], []
        for target in raw_targets:
            user_id, error = await roblox_api.resolve_user_id(target)
            if error:
                failures.append((target, error))
                continue

            label = f"`{target}` (ID: `{user_id}`)" if not target.isdigit() else f"ID `{user_id}`"
            ok, detail = await roblox_api.set_ban(
                user_id,
                active=True,
                reason=reason,
                public_reason=public_reason,
                duration_minutes=time_minutes,
                moderator=f"{interaction.user} ({interaction.user.id})",
            )
            if ok:
                successes.append(label)
            else:
                failures.append((label, detail))

        log_time = f"{time_minutes} minutes" if time_minutes else "Permanently"
        summary_lines = []

        if successes:
            summary_lines.append(f"✅ Banned {log_time}: {', '.join(successes)}")
            await log_action(
                self.bot,
                title="🔨 Roblox User(s) Banned",
                description=(
                    f"**Targets:** {', '.join(successes)}\n"
                    f"**Moderator:** {interaction.user.mention}\n"
                    f"**Duration:** {log_time}\n"
                    f"**Reason:** {reason}"
                ),
                color=discord.Color.red(),
            )

        for label, detail in failures:
            summary_lines.append(f"❌ Failed to ban {label}: `{detail}`")

        await interaction.followup.send("\n".join(summary_lines))

    @roblox_group.command(name="unban", description="Unban a Roblox user by ID or username")
    @require_admin()
    async def unban(self, interaction: discord.Interaction, target: str):
        await interaction.response.defer(ephemeral=False)

        user_id, error = await roblox_api.resolve_user_id(target)
        if error:
            try:
                await interaction.followup.send(error)
            except discord.NotFound:
                print(f"Interaction expired while resolving user ID for target: {target}")
            return

        ok, detail = await roblox_api.set_ban(user_id, active=False)
        label = f"`{target}` (ID: `{user_id}`)" if not target.isdigit() else f"ID `{user_id}`"

        if ok:
            await log_action(
                self.bot,
                title="🔨 Roblox User Unbanned",
                description=f"**Target:** {label}\n**Moderator:** {interaction.user.mention}\n",
                color=discord.Color.green(),
            )
            try:
                await interaction.followup.send(f"Successfully unbanned {label}.")
            except discord.NotFound:
                print(f"Successfully unbanned {label}, but the interaction expired before confirmation could be sent.")
        else:
            try:
                await interaction.followup.send(f"Failed to unban. {detail}")
            except discord.NotFound:
                print(f"Interaction expired. Failed to unban {label}: {detail}")


async def setup(bot: commands.Bot):
    await bot.add_cog(RobloxModeration(bot))
