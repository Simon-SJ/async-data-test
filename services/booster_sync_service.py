"""
Keeps the booster list pushed to the gist in sync with:
  - members currently boosting the server (or holding BOOSTER_ROLE_ID)
  - the manually-added list (/user add)
  - manual display-name overrides (/user update)
"""
import discord

from config import BOOSTER_ROLE_ID, GIST_DATA_FILE, GIST_MANUAL_FILE, GIST_MODERATORS_FILE, GIST_NAMES_FILE
from services import gist_store


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
    manual_list = manual_override if manual_override is not None else await gist_store.get_file(GIST_MANUAL_FILE, default=[])
    name_overrides = names_override if names_override is not None else await gist_store.get_file(GIST_NAMES_FILE, default={})

    live_boosters = []
    for guild in client.guilds:
        for member in guild.members:
            member_role_ids = {role.id for role in member.roles}
            if member.premium_since or BOOSTER_ROLE_ID in member_role_ids:
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
