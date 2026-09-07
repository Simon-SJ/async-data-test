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
) -> tuple[int, str | None]:
    if manual_override is not None and names_override is not None:
        manual_list, name_overrides = manual_override, names_override
    else:
        fetched = await gist_store.get_files([GIST_MANUAL_FILE, GIST_NAMES_FILE], defaults={GIST_MANUAL_FILE: [], GIST_NAMES_FILE: {}})
        manual_list = manual_override if manual_override is not None else fetched[GIST_MANUAL_FILE]
        name_overrides = names_override if names_override is not None else fetched[GIST_NAMES_FILE]

    live_boosters = []
    processed_user_ids = set()  # Tracks users we already checked

    async with aiohttp.ClientSession() as session:
        for guild in client.guilds:
            for member in guild.members:
                # Skip if we already processed this user in another guild
                if member.id in processed_user_ids:
                    continue

                member_role_ids = {role.id for role in member.roles}
                if member.premium_since or BOOSTER_ROLE_ID in member_role_ids:
                    processed_user_ids.add(member.id)  # Mark as processed
                    
                    bloxlink_ID = None
                    try:
                        url = f"https://api.blox.link/v4/public/guilds/{ASYNC_SERVER_ID}/discord-to-roblox/{member.id}"
                        headers = {"Authorization": BLOXLINK_KEY, "Content-Type": "application/json"}
                        
                        async with session.get(url, headers=headers) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                bloxlink_ID = data.get("robloxID")
                            elif resp.status == 404:
                                print(f"Skipping {member.name} ({member.id}): Not linked on Bloxlink.")
                            else:
                                print(f"Bloxlink API returned status {resp.status} for {member.id}")

                    except aiohttp.ClientError as e:
                        print(f"Network error checking Bloxlink for {member.id}: {e}")

                    roblox_name = await roblox_api.resolve_user_name(bloxlink_ID or 0)
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
            GIST_MODERATORS_FILE: [],
        }
    )

    return len(final_output), None