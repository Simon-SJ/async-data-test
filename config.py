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
# The one server where staff roles are defined. Permission checks resolve
# membership here regardless of where a command is actually invoked, which
# is what lets moderation commands work from DMs/group DMs (see
# utils/permissions.py). This was two separate constants with the same
# value in the old bot (EA_SUSPENSION_GUILD_ID / ALLOWED_GUILD_ID) — merged
# since they always pointed at the same server.
HOME_GUILD_ID = 1091729426330419283

ADMIN_IDS = {
    595524051208765442,
    554691397601591306,
    781870312194703380,
    465161449359147010,
    659284243951910933,
}
MODERATOR_ROLE_IDS = {
    1271205269183139891,
    1091729426850521105,
    1271208960463999079,
    1145150303210049576,
    1411096066602045533,
    1271202265688051722,
    1518726629436690534,
}
EA_SUSPENSION_ROLE_IDS = {1270993277834760243, 1270998010502844449}
EA_SUSPENDED_ROLE_ID = 1417249050616664094

BOOSTER_ROLE_ID = 1091729426829557850  # treated as a booster alongside real Nitro boosts

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
