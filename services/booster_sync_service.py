"""
Keeps the booster list pushed to the gist in sync with:
  - members currently boosting the server (or holding BOOSTER_ROLE_ID)
  - the manually-added list (/user add)
  - manual display-name overrides (/user update)
"""

import discord
import aiohttp

from config import BOOSTER_ROLE_ID, GIST_DATA_FILE, GIST_MANUAL_FILE, GIST_MODERATORS_FILE, GIST_NAMES_FILE, ASYNC_SERVER_ID, BLOXLINK_KEY
from services import gist_store
from services import roblox_api


async def sync_and_publish(
    client: discord.Client,
    manual_override: list | None = None,
    names_override: dict | None = None,
) -> int:
    """Recompute the combined booster list and push it (plus the manual
    list and name overrides) to the gist. Returns the number of users in
    the final list.

    NOTE: this pushes moderators.json as an empty list every time, same as
    the original — nothing anywhere in the bot ever populates a moderators
    list, so every sync currently overwrites that file with []. Left as-is
    rather than guessing what should go there; flagged in chat.
    """
    if manual_override is not None and names_override is not None:
        manual_list, name_overrides = manual_override, names_override
    else:
        fetched = await gist_store.get_files([GIST_MANUAL_FILE, GIST_NAMES_FILE], defaults={GIST_MANUAL_FILE: [], GIST_NAMES_FILE: {}})
        manual_list = manual_override if manual_override is not None else fetched[GIST_MANUAL_FILE]
        name_overrides = names_override if names_override is not None else fetched[GIST_NAMES_FILE]

    live_boosters = []
    for guild in client.guilds:
        for member in guild.members:
            member_role_ids = {role.id for role in member.roles}
            if member.premium_since or BOOSTER_ROLE_ID in member_role_ids:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(f"https://api.blox.link/v4/public/guilds/{ASYNC_SERVER_ID}/discord-to-roblox/{member.id}", headers={"Authorization": BLOXLINK_KEY, "Content-Type": "application/json"}) as resp:
                            if resp.status != 200:
                                return None, f"Failed to contact BloxLink API. Status: {resp.status}"
                            bloxlink_ID = (await resp.json()).get("robloxID")
                except aiohttp.ClientError as e:
                    return None, f"Failed to contact with BloxLink API: {e}"

                name = await roblox_api.resolve_user_name(bloxlink_ID or 0)
                live_boosters.append((str(member.id), member.display_name))

    combined = {user_id: name for user_id, name in manual_list}
    for user_id, name in live_boosters:
        combined[user_id] = name

    final_output = [[user_id, name_overrides.get(user_id, name)] for user_id, name in combined.items()]

    await gist_store.put_files(
        {
            GIST_DATA_FILE: final_output,
            GIST_MANUAL_FILE: manual_list,
            GIST_NAMES_FILE: name_overrides,
            GIST_MODERATORS_FILE: [],  # see note above
        }
    )

    return len(final_output)