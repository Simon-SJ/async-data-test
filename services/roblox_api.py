"""
Wrapper around the two Roblox HTTP APIs the bot talks to:
  - users.roblox.com, for username -> user ID lookups
  - Roblox Open Cloud (v2 for bans, v1 datastores for EA suspensions/blacklists)
"""
import json

import aiohttp

from config import (
    ROBLOX_API_KEY,
    ROBLOX_CLOUD_BASE_URL,
    ROBLOX_DATASTORE_BASE_URL,
    ROBLOX_USER_INFO_URL,
    ROBLOX_USERNAME_LOOKUP_URL,
    UNIVERSE_ID,
)

_CLOUD_HEADERS = {"x-api-key": ROBLOX_API_KEY, "content-type": "application/json"}


async def resolve_user_id(target: str) -> tuple[str | None, str | None]:
    """Accepts a numeric Roblox user ID or a username. Returns (user_id, error)."""
    if target.isdigit():
        return target, None

    payload = {"usernames": [target], "excludeBannedUsers": False}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(ROBLOX_USERNAME_LOOKUP_URL, json=payload) as resp:
                if resp.status != 200:
                    return None, f"Failed to contact Roblox API. Status: {resp.status}"
                data = await resp.json()
    except aiohttp.ClientError as e:
        return None, f"Failed to contact Roblox API: {e}"

    users = data.get("data", [])
    if not users:
        return None, f"No Roblox user found with username `{target}`."
    return str(users[0]["id"]), None

async def resolve_user_name(user_id: int) -> str:
    """Accepts a numeric Roblox user ID, returns username"""

    payload = {"userIds": [user_id], "excludeBannedUsers": False}
    try:
       async with aiohttp.ClientSession() as session:
            async with session.post(ROBLOX_USER_INFO_URL, json=payload) as resp:
                   if resp.status != 200:
                       return None, f"Failed to contact Roblox API. Status: {resp.status}"
                   data = await resp.json()
    except aiohttp.ClientError as e:
           return None, f"Failed to contact Roblox API: {e}"
   
    users = data.get("data", [])
    if not users:
           return None, f"No Roblox user found with user id `{user_id}`."
    return str(users[0]["name"]), None

    return data.get("name")

async def set_ban(
    user_id: str,
    *,
    active: bool,
    reason: str = "",
    public_reason: str | None = None,
    duration_minutes: float | None = None,
    moderator: str = "",
) -> tuple[bool, str]:
    """Set or clear a game-join restriction. Returns (ok, detail)."""
    url = f"{ROBLOX_CLOUD_BASE_URL}/universes/{UNIVERSE_ID}/user-restrictions/{user_id}"

    if active:
        body = {
            "gameJoinRestriction": {
                "active": True,
                "duration": f"{duration_minutes * 60}s" if duration_minutes else None,
                "privateReason": f"Banned by {moderator}: {reason}",
                "displayReason": public_reason or "You have been banned.",
                "excludeAltAccounts": False,
            }
        }
    else:
        body = {"gameJoinRestriction": {"active": False}}

    async with aiohttp.ClientSession() as session:
        async with session.patch(url, headers=_CLOUD_HEADERS, json=body) as resp:
            if resp.status == 200:
                return True, ""
            return False, f"Status {resp.status}: {await resp.text()}"


async def get_datastore_entry(datastore_name: str, entry_key: str) -> tuple[int, dict | list | None]:
    """Returns (http_status, decoded_json_or_None)."""
    url = f"{ROBLOX_DATASTORE_BASE_URL}/universes/{UNIVERSE_ID}/standard-datastores/datastore/entries/entry"
    params = {"datastoreName": datastore_name, "entryKey": entry_key}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=_CLOUD_HEADERS, params=params) as resp:
            if resp.status != 200:
                return resp.status, None
            try:
                return resp.status, await resp.json()
            except (aiohttp.ContentTypeError, json.JSONDecodeError):
                return resp.status, None


async def put_datastore_entry(datastore_name: str, entry_key: str, data) -> tuple[bool, str]:
    url = f"{ROBLOX_DATASTORE_BASE_URL}/universes/{UNIVERSE_ID}/standard-datastores/datastore/entries/entry"
    params = {"datastoreName": datastore_name, "entryKey": entry_key}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=_CLOUD_HEADERS, params=params, data=json.dumps(data)) as resp:
            if resp.status == 200:
                return True, ""
            return False, f"Status {resp.status}: {await resp.text()}"


async def delete_datastore_entry(datastore_name: str, entry_key: str) -> tuple[bool, int]:
    """Returns (ok, http_status) — status is returned separately so callers
    can special-case 404 ("wasn't there to begin with")."""
    url = f"{ROBLOX_DATASTORE_BASE_URL}/universes/{UNIVERSE_ID}/standard-datastores/datastore/entries/entry"
    params = {"datastoreName": datastore_name, "entryKey": entry_key}
    async with aiohttp.ClientSession() as session:
        async with session.delete(url, headers=_CLOUD_HEADERS, params=params) as resp:
            return resp.status in (200, 204), resp.status


async def list_datastore_entries(datastore_name: str):
    """Used by the /ea list debug command."""
    url = f"{ROBLOX_CLOUD_BASE_URL}/universes/{UNIVERSE_ID}/data-stores/{datastore_name}/entries"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=_CLOUD_HEADERS) as resp:
            return await resp.json()
