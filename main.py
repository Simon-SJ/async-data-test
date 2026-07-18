"""
Entry point. Builds the bot, loads every cog, runs it.

Adding a new feature = one new file in cogs/ + one line in COGS below.
Nothing else in this file needs to change.
"""
import discord
from discord import app_commands
from discord.ext import commands

import config
from services import gist_store

COGS = (
    "cogs.booster_sync",
    "cogs.roblox_moderation",
    "cogs.discord_moderation",
    "cogs.ea_moderation",
    "cogs.moon_control",
    "cogs.dm_tools",
)


class ModBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        # No prefix commands are used anywhere (everything is a slash
        # command) — command_prefix is required by the base class but
        # will never actually match anything real.
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)

    async def setup_hook(self):
        for extension in COGS:
            await self.load_extension(extension)

        synced = await self.tree.sync()
        print(f"Synced {len(synced)} top-level slash commands.")

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id}).")

    async def close(self):
        await gist_store.close_session()
        await super().close()


bot = ModBot()


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        message = "No permission."
    else:
        command_name = interaction.command.qualified_name if interaction.command else "?"
        print(f"Unhandled error in /{command_name}: {error!r}")
        message = "Something went wrong running that command."

    send = interaction.followup.send if interaction.response.is_done() else interaction.response.send_message
    try:
        await send(message, ephemeral=True)
    except discord.HTTPException:
        pass


def main():
    config.validate()
    bot.run(config.DISCORD_TOKEN)


if __name__ == "__main__":
    main()