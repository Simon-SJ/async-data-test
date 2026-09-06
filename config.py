"""
Central configuration.

Secrets come from environment variables (see .env.example). Every Discord/
Roblox ID the bot cares about lives here so there's exactly one place to
look when something needs to change.
"""
import os

from dotenv import load_dotenv

load_dotenv()

# --- Secrets ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
ROBLOX_API_KEY = os.getenv("ROBLOX_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GIST_ID = os.getenv("GIST_ID")

# --- Roblox ---
UNIVERSE_ID = 3467628732

ROBLOX_CLOUD_BASE_URL = "https://apis.roblox.com/cloud/v2"
ROBLOX_DATASTORE_BASE_URL = "https://apis.roblox.com/datastores/v1"
ROBLOX_USERNAME_LOOKUP_URL = "https://users.roblox.com/v1/usernames/users"

SUSPENSION_DATASTORE_ID = "SuspendedEA"
BLACKLIST_DATASTORE_ID = "EntityBlacklists"

# --- Discord: home guild ---
# The one server where the EA-suspended role lives, and where /ea
# suspend|unsuspend assigns/removes it. This is a single-guild feature by
# nature (a role only exists in one server), unlike the permission role
# maps below. Was two separate constants with the same value in the old
# bot (EA_SUSPENSION_GUILD_ID / ALLOWED_GUILD_ID) — merged since they
# always pointed at the same server.
ASYNC_SERVER_ID = 1091729426330419283
SCRIPTO_SERVER_ID = 1470530239359750287
EA_SERVER_ID = 1270991212811391060
SUPPORT_SERVER_ID = 1516935929854693478

ADMIN_IDS = {
    595524051208765442, # simonsj
    554691397601591306, # guy
    781870312194703380, # scripto
   # 465161449359147010, # pesty
    659284243951910933, # morta
    910102167199838229, # hatemails
    369855611191558145, # mightymails
    818509530539098112, # Mythical
    335575721986752512, # hayden
    298786408125169677, # rey
    305530043461795841, # val
}

# Role IDs are unique per guild, so "check multiple servers for roles"
# means a mapping of guild_id -> that guild's role IDs, not one flat set.
# utils/permissions.py checks every guild listed here and grants access if
# the user holds a matching role in ANY of them. To add another server:
# turn on Developer Mode in Discord (User Settings > Advanced), right-click
# the role(s) you want to count as admin/EA-mod in that server, "Copy
# Role ID", and add an entry below keyed by that server's guild ID.
ADMIN_ROLES_BY_GUILD = {
    ASYNC_SERVER_ID: {
        1279483933943136368, # Discord Mod
        1279558024758820974, # Discord Administrator
    },
    SCRIPTO_SERVER_ID: {
        1518726629436690534, # baldi's hammer 
    },
    # SECOND_GUILD_ID: {role_id_1, role_id_2},
}
EA_ROLES_BY_GUILD = {
    SCRIPTO_SERVER_ID: {
        1518726629436690534, # baldi's hammer 
    },
    EA_SERVER_ID: {
        1270998010502844449, # actor orginiser 
        1270993277834760243, # Director
        1522421015815131176, # actor supervisor
    },
    # SECOND_GUILD_ID: {role_id_1},
}

EA_SUSPENDED_ROLE_ID = 1417249050616664094

BOOSTER_ROLE_ID = 1115343914275180564  # treated as a booster alongside real Nitro boosts

# --- Discord: channels ---
LOG_CHANNEL_ID = 1525409312120504413
DM_FORWARD_CHANNEL_ID = 1470330654448156672

# --- Gist file names ---
GIST_DATA_FILE = "data.json"
GIST_MANUAL_FILE = "manual.json"
GIST_NAMES_FILE = "names.json"
GIST_MODERATORS_FILE = "moderators.json"
GIST_BRIDGE_FILE = "ExternalBridge.json"


def validate() -> None:
    """Fail fast on a missing secret instead of an unclear error later,
    e.g. an aiohttp 401 three commands deep."""
    missing = [
        name
        for name, value in (
            ("DISCORD_TOKEN", DISCORD_TOKEN),
            ("ROBLOX_API_KEY", ROBLOX_API_KEY),
            ("GITHUB_TOKEN", GITHUB_TOKEN),
            ("GIST_ID", GIST_ID),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")