import discord
from discord import app_commands
import requests
import os
import json
import random
import aiohttp
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# --- CONFIG ---
UNIVERSE_ID = 3467628732
ROBLOX_API_KEY = os.getenv("ROBLOX_API_KEY")
TOKEN = os.getenv("DISCORD_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GIST_ID = os.getenv("GIST_ID")
ADMIN_IDs = {595524051208765442, 554691397601591306 , 781870312194703380, 465161449359147010 }
MODERATOR_ROLE_IDS = {1271205269183139891, 1091729426850521105, 1271208960463999079, 1145150303210049576, 1411096066602045533, 1271202265688051722}
suspension_dataStore_ID = 'SuspendedEA'
base_url = 'https://apis.roblox.com/cloud/v2/'

class MyClient(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True 
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        print("Slash commands synced.")

client = MyClient()

# --- HELPER FUNCTIONS ---

def IsAdmin(user):
    if user.id in ADMIN_IDs:
        return True
    if any(role.id in MODERATOR_ROLE_IDS for role in user.roles):
            return True
    return False

def get_gist_file(filename):
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    try:
        r = requests.get(url, headers=headers)
        files = r.json().get('files', {})
        if filename in files:
            return json.loads(files[filename]['content'])
        return {} if "names" in filename else []
    except:
        return {} if "names" in filename else []

def push_all_to_gist(final_data, manual_data, name_overrides, moderator_data):
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    payload = {
        "files": {
            "data.json": {"content": json.dumps(final_data, indent=2)},
            "manual.json": {"content": json.dumps(manual_data, indent=2)},
            "names.json": {"content": json.dumps(name_overrides, indent=2)},
            "moderators.json": {"content": json.dumps(moderator_data, indent=2)} # New file
        }
    }
    requests.patch(url, headers=headers, json=payload)

def sync_and_publish(manual_override=None, names_override=None):
    manual_list = manual_override if manual_override is not None else get_gist_file("manual.json")
    name_overrides = names_override if names_override is not None else get_gist_file("names.json")

    live_boosters = []
    moderators = [] # Initialize moderator list

    for guild in client.guilds:
        for member in guild.members:
            # Check for Boosters
            if member.premium_since:
                live_boosters.append([str(member.id), member.display_name])

    # Combine Booster/Manual logic
    combined = {entry[0]: entry[1] for entry in manual_list}
    for b_id, b_name in live_boosters:
        combined[b_id] = b_name

    final_output = []
    for user_id, current_name in combined.items():
        name_to_use = name_overrides.get(user_id, current_name)
        final_output.append([user_id, name_to_use])

    # Push all 4 files now
    push_all_to_gist(final_output, manual_list, name_overrides, moderators)
    return len(final_output)

# --- SLASH COMMANDS ---
class UserGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="user", description="Manage booster list")

    @app_commands.command(name="add", description="Add a user to the manual list")
    async def add(self, interaction: discord.Interaction, member: discord.Member, roblox_name: str):
        if not IsAdmin(interaction.user):
            await interaction.response.send_message("❌ No permission.", ephemeral=True)
            return

        await interaction.response.defer()
        manual_data = get_gist_file("manual.json")
        name_overrides = get_gist_file("names.json")
        
        display_name = roblox_name if roblox_name else member.display_name
        user_id_str = str(member.id)

        found = False
        for entry in manual_data:
            if entry[0] == user_id_str:
                entry[1] = display_name
                found = True
                break
        if not found:
            manual_data.append([user_id_str, display_name])

        count = sync_and_publish(manual_override=manual_data, names_override=name_overrides)
        await interaction.followup.send(f"✅ Added **{member.name}** as '{display_name}'. Total: {count}")

    @app_commands.command(name="update", description="Update a user's Roblox name")
    async def update(self, interaction: discord.Interaction, member: discord.Member, roblox_name: str):
        if not IsAdmin(interaction.user):
            await interaction.response.send_message("❌ No permission.", ephemeral=True)
            return

        await interaction.response.defer()
        manual_data = get_gist_file("manual.json")
        names = get_gist_file("names.json")
        
        names[str(member.id)] = roblox_name
        
        count = sync_and_publish(manual_override=manual_data, names_override=names)
        await interaction.followup.send(f"✅ Updated **{member.name}** to Roblox name **{roblox_name}**.")

    @app_commands.command(name="delete", description="Remove a user from manual list and name overrides")
    async def delete(self, interaction: discord.Interaction, member: discord.Member):
        if not IsAdmin(interaction.user):
            await interaction.response.send_message("❌ No permission.", ephemeral=True)
            return

        await interaction.response.defer()
        manual_data = get_gist_file("manual.json")
        names = get_gist_file("names.json")
        user_id_str = str(member.id)

        # Filter out the user from manual data
        new_manual = [entry for entry in manual_data if entry[0] != user_id_str]
        
        # Remove from name overrides if present
        if user_id_str in names:
            del names[user_id_str]

        count = sync_and_publish(manual_override=new_manual, names_override=names)
        await interaction.followup.send(f"🗑️ Removed **{member.name}** from all manual lists. Total: {count}")

@client.tree.command(name="sync", description="Force an immediate sync between Discord and Gist")
async def force_sync(interaction: discord.Interaction):
    if not IsAdmin(interaction.user):
            await interaction.response.send_message("❌ No permission.", ephemeral=True)
            return

    await interaction.response.defer()
    try:
        count = sync_and_publish()
        await interaction.followup.send(f"🔄 Force sync complete. Data pushed to Gist. Total users: {count}")
    except Exception as e:
        await interaction.followup.send(f"❌ sync failed: {e}")

# Register commands
user_group = UserGroup()
client.tree.add_command(user_group)

# --- EVENTS ---

@client.event
async def on_ready():
    print(f'Logged in as {client.user}. Initial Sync...')
    count = sync_and_publish()
    print(f"Sync complete. {count} total users in list.")

@client.event
async def on_member_update(before, after):
    # Sync if Boost status, Nickname, OR Roles change
    if (before.premium_since != after.premium_since) or \
       (before.display_name != after.display_name) or \
       (before.roles != after.roles):
        sync_and_publish()


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.guild is None:
        DmChannel = client.get_channel(1470330654448156672)
        if DmChannel:
            await DmChannel.send(f"{message.content} from {message.author}")

    if f"<@{client.user.id}>" in message.content:
        await message.channel.send(random.choice(["hello", "hi", "What's up"]))

class robloxmoderationGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="roblox", description="for mods")

    async def resolve_user_id(self, target: str) -> tuple[str | None, str | None]:
        """Returns (user_id, error_message). Accepts a numeric ID or a username."""
        if target.isdigit():
            return target, None

        # Username lookup via Roblox API
        url = "https://users.roblox.com/v1/usernames/users"
        payload = {"usernames": [target], "excludeBannedUsers": False}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    return None, f"Failed to contact Roblox API. Status: {response.status}"
                
                data = await response.json()
                users = data.get("data", [])

                if not users:
                    return None, f"No Roblox user found with username `{target}`."

                return str(users[0]["id"]), None

    @app_commands.command(name="ban", description="Ban a Roblox user by ID or username")
    @app_commands.describe( target="The Roblox username or user ID to ban.", reason="The reason for the ban.",time_minutes="Duration of the ban in minutes. Leave empty for a permanent ban.")
    async def ban(self, interaction: discord.Interaction, target: str, reason: str, time_minutes: Optional[float] = None):
        if not IsAdmin(interaction.user):
            await interaction.response.send_message("❌ No permission.", ephemeral=True)
            return

        await interaction.response.defer()

        user_id, error = await self.resolve_user_id(target)
        if error:
            await interaction.followup.send(f"❌ {error}")
            return

        duration_string = None
        if time_minutes:
            duration_string = f"{time_minutes * 60}s"

        url = f"https://apis.roblox.com/cloud/v2/universes/{UNIVERSE_ID}/user-restrictions/{user_id}"

        headers = {
            "x-api-key": ROBLOX_API_KEY,
            "content-type": "application/json"
        }

        payload = {
            "gameJoinRestriction": {
                "active": True,
                "duration": duration_string,
                "privateReason": f"Banned by {interaction.user} ({interaction.user.id}): {reason}",
                "displayReason": "You have been banned.",
                "excludeAltAccounts": False
            }
        }

        async with aiohttp.ClientSession() as session:
            async with session.patch(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    label = f"`{target}` (ID: `{user_id}`)" if not target.isdigit() else f"ID `{user_id}`"
                    followUpMsg = f"✅ Successfully banned {label} for {time_minutes} minutes."

                    if not time_minutes:
                        followUpMsg = f"✅ Successfully banned {label} permanently."
                        
                    await interaction.followup.send(followUpMsg)
                else:
                    error_text = await response.text()
                    await interaction.followup.send(f"❌ Failed to ban. Status: {response.status}\n`{error_text}`")

        
    @app_commands.command(name="unban", description="Unban a Roblox user by ID or username")
    async def unban(self, interaction: discord.Interaction, target: str):
        if not IsAdmin(interaction.user):
            await interaction.response.send_message("❌ No permission.", ephemeral=True)
            return

        await interaction.response.defer()

        user_id, error = await self.resolve_user_id(target)
        if error:
            await interaction.followup.send(f"❌ {error}")
            return

        url = f"https://apis.roblox.com/cloud/v2/universes/{UNIVERSE_ID}/user-restrictions/{user_id}"

        headers = {
            "x-api-key": ROBLOX_API_KEY,
            "content-type": "application/json"
        }

        payload = {
            "gameJoinRestriction": {
                "active": False,
            }
        }

        async with aiohttp.ClientSession() as session:
            async with session.patch(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    label = f"`{target}` (ID: `{user_id}`)" if not target.isdigit() else f"ID `{user_id}`"
                    await interaction.followup.send(f"✅ Successfully unbanned {label}.")
                else:
                    error_text = await response.text()
                    await interaction.followup.send(f"❌ Failed to unban. Status: {response.status}\n`{error_text}`")

roblox_mod_group = robloxmoderationGroup()
client.tree.add_command(roblox_mod_group)

class discordmoderationGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="discord", description="for mods")

    @app_commands.command(name="globalban", description="Ban a user from all servers the bot is in")
    @app_commands.describe(user="User ID to ban", reason="Reason for the ban")
    async def globalban(self, interaction: discord.Interaction, user: discord.User, reason: str = "No reason provided"):
        if not IsAdmin(interaction.user):
            await interaction.response.send_message("❌ No permission.", ephemeral=True)
            return

        await interaction.response.defer()

        success, failed, skipped = [], [], []

        for guild in client.guilds:
            me = guild.me
            if not me.guild_permissions.ban_members:
                skipped.append(f"{guild.name} (no permission)")
                continue

            # Avoid banning someone with a higher/equal role than the bot
            member = guild.get_member(user.id)
            if member and me.top_role <= member.top_role:
                skipped.append(f"{guild.name} (role hierarchy)")
                continue

            try:
                await guild.ban(user, reason=f"Global ban by {interaction.user} ({interaction.user.id}): {reason}")
                success.append(guild.name)
            except discord.Forbidden:
                failed.append(f"{guild.name} (forbidden)")
            except discord.HTTPException as e:
                failed.append(f"{guild.name} ({e})")

        lines = [f"✅ Globally banned `{user}` (ID: `{user.id}`)"]
        lines.append(f"**Banned in {len(success)}/{len(client.guilds)} servers**")
        if skipped:
            lines.append(f"⏭️ Skipped: {', '.join(skipped)}")
        if failed:
            lines.append(f"❌ Failed: {', '.join(failed)}")

        await interaction.followup.send("\n".join(lines))


    @app_commands.command(name="globalunban", description="Unban a user from all servers the bot is in")
    @app_commands.describe(user="User ID to unban", reason="Reason for the unban")
    async def globalunban(self, interaction: discord.Interaction, user: discord.User, reason: str = "No reason provided"):
        if not IsAdmin(interaction.user):
            await interaction.response.send_message("❌ No permission.", ephemeral=True)
            return

        await interaction.response.defer()

        success, failed, skipped, not_banned = [], [], [], []

        for guild in client.guilds:
            me = guild.me
            if not me.guild_permissions.ban_members:
                skipped.append(f"{guild.name} (no permission)")
                continue

            try:
                await guild.unban(user, reason=f"Global unban by {interaction.user} ({interaction.user.id}): {reason}")
                success.append(guild.name)
            except discord.NotFound:
                not_banned.append(guild.name)
            except discord.Forbidden:
                failed.append(f"{guild.name} (forbidden)")
            except discord.HTTPException as e:
                failed.append(f"{guild.name} ({e})")

        lines = [f"✅ Globally unbanned `{user}` (ID: `{user.id}`)"]
        lines.append(f"**Unbanned in {len(success)}/{len(client.guilds)} servers**")
        if not_banned:
            lines.append(f"ℹ️ Not banned in: {', '.join(not_banned)}")
        if skipped:
            lines.append(f"⏭️ Skipped: {', '.join(skipped)}")
        if failed:
            lines.append(f"❌ Failed: {', '.join(failed)}")

        await interaction.followup.send("\n".join(lines))

discord_mod_group = discordmoderationGroup()
client.tree.add_command(discord_mod_group)

class EAmoderationGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="ea", description="for mods")

    async def resolve_user_id(self, target: str) -> tuple[str | None, str | None]:
        if target.isdigit():
            return target, None

        url = "https://users.roblox.com/v1/usernames/users"
        payload = {"usernames": [target], "excludeBannedUsers": False}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    return None, f"Failed to contact Roblox API. Status: {response.status}"
                
                data = await response.json()
                users = data.get("data", [])
                if not users:
                    return None, f"No Roblox user found with username `{target}`."

                return str(users[0]["id"]), None

    # Note: Use aiohttp here instead of requests to prevent blocking
    async def get_entries(self):
        list_path = f'universes/{UNIVERSE_ID}/data-stores/{suspension_dataStore_ID}/entries'
        url = base_url + list_path
        headers = {'x-api-key': ROBLOX_API_KEY}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                return await response.json()

    @app_commands.command(name="suspend", description="Suspend a user from EA")
    @app_commands.describe(
        target="Roblox Username or ID", 
        time_minutes="Minutes until suspension expires (leave empty for perm)", 
        reason="Why are they being suspended?"
    )
    async def suspend(self, interaction: discord.Interaction, target: str, time_minutes: Optional[int] = None, reason: str = "No reason provided"):
        if not IsAdmin(interaction.user):
            await interaction.response.send_message("❌ No permission.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        user_id, error = await self.resolve_user_id(target)
        if error:
            await interaction.followup.send(f"❌ {error}")
            return

        suspension_data = {
            "moderator_id": str(interaction.user.id),
            "moderator_name": f'{interaction.user.display_name} ({interaction.user.name})',
            "reason": reason,
            "suspended_at": int(discord.utils.utcnow().timestamp()),
            "expires_at": int(discord.utils.utcnow().timestamp() + (time_minutes * 60)) if time_minutes else "Permanent"
        }

        entry_key = f"{user_id}"
        url = f"{base_url}universes/{UNIVERSE_ID}/data-stores/{suspension_dataStore_ID}/entries/{entry_key}"
        
        headers = {
            "x-api-key": str(ROBLOX_API_KEY),
            "content-type": "application/json"
        }
        
        payload = json.dumps({"value": suspension_data})

        async with aiohttp.ClientSession() as session:
            async with session.patch(url, headers=headers, data=payload) as response:
                if response.status in [200, 201]:
                    duration_text = f"{time_minutes}m" if time_minutes else "Permanent"
                    await interaction.followup.send(f"✅ Successfully suspended Roblox ID `{user_id}` for `{duration_text}`.\n**Reason:** {reason}")
                else:
                    err_body = await response.text()
                    await interaction.followup.send(f"❌ Failed to update Roblox DataStore. Status: {response.status}\n`{err_body}`")

    @app_commands.command(name="unsuspend", description="Remove an EA suspension from a Roblox user")
    @app_commands.describe(target="Roblox Username or ID to unsuspend")
    async def unsuspend(self, interaction: discord.Interaction, target: str):
        if not IsAdmin(interaction.user):
            await interaction.response.send_message("❌ No permission.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        user_id, error = await self.resolve_user_id(target)
        if error:
            await interaction.followup.send(f"❌ {error}")
            return

        entry_key = f"user_{user_id}"
        url = f"{base_url}universes/{UNIVERSE_ID}/data-stores/{suspension_dataStore_ID}/entries/{entry_key}"
        
        headers = {
            "x-api-key": str(ROBLOX_API_KEY)
        }

        async with aiohttp.ClientSession() as session:
            async with session.delete(url, headers=headers) as response:
                if response.status == 204:
                    await interaction.followup.send(f"✅ Successfully unsuspended `{target}` (ID: `{user_id}`).")
                elif response.status == 404:
                    await interaction.followup.send(f"ℹ️ User `{target}` is not currently suspended.")
                else:
                    err_body = await response.text()
                    await interaction.followup.send(f"❌ Failed to unsuspend. Status: {response.status}\n`{err_body}`")

    @app_commands.command(name="list", description="debug cmd, does not do shit")
    async def list_suspended(self, interaction: discord.Interaction):
        if not IsAdmin(interaction.user):
            await interaction.response.send_message("❌ No permission.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        entries = await self.get_entries()
        print(entries)
        await interaction.followup.send("Entries printed to console.")

EA_mod_group = EAmoderationGroup()
client.tree.add_command(EA_mod_group)


client.run(TOKEN)