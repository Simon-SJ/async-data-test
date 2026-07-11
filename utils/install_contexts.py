"""
Shared install/context presets for slash command Groups.

Discord has two separate settings for an app-installable command:
  - *install type*: who can add it — a guild admin (guild install) and/or
    any individual user to their own account (user install).
  - *context*: where an already-installed command can be run — inside a
    guild, in a DM with the bot, and/or in a group DM ("private channel").

Getting a command to work in a DM with the bot only needs guild install +
dm context, as long as the invoking user shares a server with the bot.
Group DMs are different: Discord only allows a command there if the user
has *user-installed* the app to their own account — there's no way to
scope that to "only my server's staff". EVERYWHERE below opts into that
tradeoff. Execution is still gated by utils.permissions — this only
controls where a command shows up, not who's allowed to run it.
"""
from discord import app_commands

# Usable in the home server, in a DM with the bot, and in group DMs — and,
# because user-installed commands travel with the account, technically
# visible to whoever installs it even in servers this bot isn't in.
EVERYWHERE_INSTALLS = app_commands.AppInstallationType(guild=True, user=True)
EVERYWHERE_CONTEXTS = app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True)

# Traditional behavior: only usable inside guilds this bot is added to.
GUILD_ONLY_INSTALLS = app_commands.AppInstallationType(guild=True, user=False)
GUILD_ONLY_CONTEXTS = app_commands.AppCommandContext(guild=True, dm_channel=False, private_channel=False)
