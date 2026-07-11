"""/moon set — pushes a command onto the ExternalBridge gist queue for the game to pick up."""
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from config import GIST_BRIDGE_FILE
from services import gist_store
from utils.install_contexts import EVERYWHERE_CONTEXTS, EVERYWHERE_INSTALLS
from utils.permissions import require_admin


class MoonControl(commands.Cog):
    moon_group = app_commands.Group(
        name="moon",
        description="Control the game atmosphere",
        allowed_installs=EVERYWHERE_INSTALLS,
        allowed_contexts=EVERYWHERE_CONTEXTS,
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        ok = await gist_store.clear_file(GIST_BRIDGE_FILE)
        if ok:
            print("[moon_control] Cleared the moon-command queue.")

    @moon_group.command(name="set", description="Trigger a blackout or change the moon style with a delay")
    @app_commands.describe(
        delay="Set a delay in seconds before the moon triggers",
        debug="Makes the command only trigger in private servers and studio",
    )
    @require_admin()
    async def set_moon(
        self,
        interaction: discord.Interaction,
        enabled: bool,
        style: Literal["blood", "fun", "hallow", "blackout"],
        delay: int,
        debug: bool,
    ):
        await interaction.response.defer()

        queue = await gist_store.get_file(GIST_BRIDGE_FILE, default=[])
        queue.append(
            {
                "bool": enabled,
                "style": style,
                "delay": delay,
                "timestamp": discord.utils.utcnow().timestamp(),
                "debug": debug,
            }
        )

        ok = await gist_store.put_files({GIST_BRIDGE_FILE: queue})
        if ok:
            status_text = "ENABLED" if enabled else "DISABLED"
            await interaction.followup.send(
                f"**{style.upper()}** moon set to **{status_text}** in **{delay} seconds**. Pushed to Gist."
            )
        else:
            await interaction.followup.send("Gist update failed.")


async def setup(bot: commands.Bot):
    await bot.add_cog(MoonControl(bot))
