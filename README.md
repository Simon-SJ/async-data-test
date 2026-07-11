# Discord Bot — restructured

## Folder structure

The download gives you flat files (no folders), so place each one here manually:

```
discord_bot/
├── main.py
├── config.py
├── requirements.txt
├── .env.example
├── smoke_test.py
├── utils/
│   ├── permissions.py
│   ├── install_contexts.py
│   └── logging.py
├── services/
│   ├── gist_store.py
│   ├── roblox_api.py
│   └── booster_sync_service.py
└── cogs/
    ├── booster_sync.py
    ├── roblox_moderation.py
    ├── discord_moderation.py
    ├── ea_moderation.py
    ├── moon_control.py
    └── dm_tools.py
```

`utils/`, `services/`, and `cogs/` need to actually be folders — the imports (`from services import gist_store`, `from utils.permissions import require_admin`, `load_extension("cogs.booster_sync")`) depend on it. No `__init__.py` needed in any of them; Python 3.3+ treats a plain folder as a package automatically.

## What each layer does

- **`config.py`** — every ID, URL, and env var, in one place.
- **`utils/`** — cross-cutting helpers with no Roblox/Discord-business-logic of their own: permission checks, the log-channel embed helper, and the DM/group-DM install presets.
- **`services/`** — talks to the outside world (Gist, Roblox APIs) and holds the actual sync logic. No Discord objects in here except where `booster_sync_service` needs `client.guilds`.
- **`cogs/`** — one file per feature area. Each is a self-contained slice: its commands, its listeners, its `setup()`. This is the layer you'll touch 95% of the time.

## Setup

**1. Discord Developer Portal** (discord.com/developers/applications → your app)

- **Bot tab**: enable **Server Members Intent** and **Message Content Intent** (same two the old bot needed). Grab your `DISCORD_TOKEN` here.
- **Installation tab**: check both **Guild Install** and **User Install**. This is what actually lets commands work in DMs and group DMs, not just your server — see the note below.

**2. Environment** — copy `.env.example` to `.env` and fill in the four values (same four as before; the two Ollama ones are gone):

```
DISCORD_TOKEN=
ROBLOX_API_KEY=
GITHUB_TOKEN=
GIST_ID=
```

**3. Install & run**

```
pip install -r requirements.txt
python main.py
```

You should see `Synced N top-level slash commands.` in the console. `python smoke_test.py` also works without a real token — useful for checking a new cog loads before you actually connect.

## Adding a new feature

Say you want a `/warn` command. You don't touch `main.py`, `config.py`, or anything existing — just:

```python
# cogs/warnings.py
import discord
from discord import app_commands
from discord.ext import commands

from utils.permissions import require_admin

class Warnings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="warn", description="Warn a user")
    @require_admin()
    async def warn(self, interaction: discord.Interaction, user: discord.User, reason: str):
        await interaction.response.send_message(f"Warned {user.mention}: {reason}")

async def setup(bot: commands.Bot):
    await bot.add_cog(Warnings(bot))
```

Then add `"cogs.warnings"` to the `COGS` tuple at the top of `main.py`. That's the whole integration surface — `python smoke_test.py` will tell you immediately if something's wrong.

## Things worth knowing

**AI/Ollama is gone entirely** — `prompt_ollama`, the Gist-fetched system instructions, the `/settings` command group, and the mention-triggered reply in `on_message` are all removed. `on_message` now only forwards DMs to the log channel.

**The permission system is centralized.** The old bot repeated an `if not IsAdmin(...): ... return` block at the top of ~15 commands. Every command here is decorated with `@require_admin()` or `@require_ea_mod()` instead (`utils/permissions.py`), and `main.py` has one global error handler that turns a failed check into the same "No permission." reply. `/ea list` still specifically requires full admin while the other `/ea` commands only require the EA-suspension mod role — that distinction from the original is preserved.

**Why DM/group-DM support needed a code change, not just a Discord setting.** `interaction.user.roles` only exists on a `discord.Member`; in a DM it's a `discord.User`, which doesn't have that attribute, so the old permission checks would have thrown outright if ever run outside a server. Every permission check now looks up the invoking user's membership in your home server directly (`utils/permissions.py`'s `_resolve_home_member`), regardless of where the command was actually run. Booster-list management (`/user update`, `/user delete`) is the one exception left guild-only, since it targets a `discord.Member` and boosting is inherently a per-server thing anyway.

**The User Install tradeoff, restated concretely:** because it's enabled, `/roblox`, `/discord`, `/ea`, `/moon`, and `/dm` will show up for *anyone* who installs the app to their own Discord account, in any server or DM, even ones this bot was never added to. They just get "No permission." if they try to run one and aren't in your `ADMIN_IDS` or the right role in the home server. If you'd rather not have the commands visible to non-staff at all, swap `EVERYWHERE_INSTALLS`/`EVERYWHERE_CONTEXTS` for `GUILD_ONLY_INSTALLS`/`GUILD_ONLY_CONTEXTS` (both already defined in `utils/install_contexts.py`) in whichever cogs you want to pull back — that gets you server + DMs-with-the-bot, just not group DMs.

**Three behavioral things flagged, not silently changed:**
1. `moderators.json` gets pushed as `[]` on every single sync, same as the original — nothing anywhere ever populates a real moderators list, so this was already a no-op file wipe. Left as-is in `services/booster_sync_service.py` (clearly commented) rather than guessing what should go there.
2. The original `/ea suspend` errored out if it couldn't find the home guild/member, but `/ea unsuspend` silently ignored the same failure and still reported success. Both now behave like the stricter `suspend` version (`EaModeration._set_suspended_role` in `cogs/ea_moderation.py`).
3. `get_gist_file`, `push_all_to_gist`, `clear_external_bridge`, and `add_command_to_queue` all used the blocking `requests` library from inside `async def` command handlers, which stalls the bot's entire event loop for the duration of every Gist call. `sync_and_publish`'s own callers had already been fixed for this per your notes — `services/gist_store.py` now does it everywhere, on aiohttp, consistently.

## Verified before handing off

Loaded all six cogs into a real (disconnected) `Bot` instance and confirmed: every command/group registers with the right name, every check (`require_admin`/`require_ea_mod`) is actually attached, `self` inside each command correctly binds to the cog instance (not the `Group`), install/context settings resolve to what's intended per cog, and the `on_ready`/`on_member_update`/`on_message` listeners are all present. Couldn't test an actual Discord connection from here (no network path to Discord's gateway in this environment) — that part's on you once you drop in a real token.
