import discord
from discord import app_commands
import requests
import os
import json
import random
import aiohttp
from typing import Optional, Literal
from dotenv import load_dotenv
import time

load_dotenv()

# --- CONFIG ---
UNIVERSE_ID = 3467628732
ROBLOX_API_KEY = os.getenv("ROBLOX_API_KEY")
TOKEN = os.getenv("DISCORD_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GIST_ID = os.getenv("GIST_ID")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")  # e.g. http://192.168.1.50:11434
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")
ADMIN_IDs = {595524051208765442, 554691397601591306 , 781870312194703380, 465161449359147010, 659284243951910933 }
MODERATOR_ROLE_IDS = {1271205269183139891, 1091729426850521105, 1271208960463999079, 1145150303210049576, 1411096066602045533, 1271202265688051722}
EA_SUSPENSION_ROLE_IDS = {1270993277834760243, 1270998010502844449}
EA_SUSPENDED_ROLE_ID = 1417249050616664094
EA_SUSPENSION_GUILD_ID = 1270991212811391060
suspension_dataStore_ID = 'SuspendedEA'
blacklist_dataStore_ID = 'EntityBlacklists'
base_url = 'https://apis.roblox.com/cloud/v2/'
SYSTEM_INSTRUCTION_URL = "https://gist.githubusercontent.com/Simon-SJ/6b68ccd9b76b9287d8df562d24d8a1a9/raw/instructions.txt"
ALLOWED_GUILD_ID = 1270991212811391060

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

async def fetch_system_instruction() -> str:
    """Fetches the system instruction from the Gist, bypassing cache."""
    cache_buster = f"?t={int(time.time())}"
    fresh_url = SYSTEM_INSTRUCTION_URL + cache_buster
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(fresh_url) as resp:
                if resp.status == 200:
                    return await resp.text()
    except Exception as e:
        print(f"Error fetching system instructions: {e}")
    return "You are a helpful assistant."


async def prompt_ollama(user_message: str) -> str:
    """
    Sends a message to the local Ollama instance and returns the response text.
    Fetches the system instruction from GitHub Gist on every call.
    """
    system_instruction = await fetch_system_instruction()

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system",  "content": system_instruction},
            {"role": "user",    "content": user_message},
        ],
        "stream": False,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OLLAMA_HOST}/api/chat",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120),  # generous timeout for local inference
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["message"]["content"]
                else:
                    error_text = await resp.text()
                    print(f"Ollama error {resp.status}: {error_text}")
                    return f"⚠️ Ollama returned an error (status {resp.status})."
    except aiohttp.ClientConnectorError:
        return f"⚠️ Could not connect to Ollama at `{OLLAMA_HOST}`. Is it running?"
    except Exception as e:
        print(f"Unexpected Ollama error: {e}")
        return "⚠️ An unexpected error occurred while contacting the AI."


async def log_action(title: str, description: str, color: discord.Color = discord.Color.blue()):
        #Sends an embed log to the designated logging channel.
        LOG_CHANNEL_ID = 1496863034818433096
        channel = client.get_channel(LOG_CHANNEL_ID)
        
        if channel:
            embed = discord.Embed(
                title=title,
                description=description,
                color=color,
                timestamp=discord.utils.utcnow()
            )
            await channel.send(embed=embed)
        else:
            print(f"Could not find log channel with ID {LOG_CHANNEL_ID}")

def IsEASuspensionMod(user):
    if user.id in ADMIN_IDs:
        return True
    if any(role.id in EA_SUSPENSION_ROLE_IDS for role in user.roles):
        return True
    return False

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
            "moderators.json": {"content": json.dumps(moderator_data, indent=2)}
        }
    }
    requests.patch(url, headers=headers, json=payload)

def sync_and_publish(manual_override=None, names_override=None):
    manual_list = manual_override if manual_override is not None else get_gist_file("manual.json")
    name_overrides = names_override if names_override is not None else get_gist_file("names.json")

    TARGET_ROLE_ID = 1091729426829557850

    live_boosters = []
    moderators = []

    for guild in client.guilds:
        for member in guild.members:
            member_role_ids = [role.id for role in member.roles]
            if member.premium_since or TARGET_ROLE_ID in member_role_ids:
                live_boosters.append([str(member.id), member.display_name])

    combined = {entry[0]: entry[1] for entry in manual_list}
    for b_id, b_name in live_boosters:
        combined[b_id] = b_name

    final_output = []
    for user_id, current_name in combined.items():
        name_to_use = name_overrides.get(user_id, current_name)
        final_output.append([user_id, name_to_use])

    push_all_to_gist(final_output, manual_list, name_overrides, moderators)
    return len(final_output)

def clear_external_bridge():
    """Wipes the ExternalBridge.json file to an empty list."""
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    payload = {
        "files": {
            "ExternalBridge.json": {"content": json.dumps([], indent=2)}
        }
    }
    try:
        r = requests.patch(url, headers=headers, json=payload)
        if r.status_code == 200:
            print("Successfully cleared ExternalBridge.json queue.")
        else:
            print(f"Failed to clear queue: {r.status_code}")
    except Exception as e:
        print(f"Error clearing queue on startup: {e}")

# --- SLASH COMMANDS ---
class UserGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="user", description="Manage booster list")

    @app_commands.command(name="add", description="Add a user to the manual list")
    async def add(self, interaction: discord.Interaction, user_id: str, roblox_name: str):
        if not IsAdmin(interaction.user):
            await interaction.response.send_message("No permission.", ephemeral=True)
            return

        await interaction.response.defer()
        manual_data = get_gist_file("manual.json")
        name_overrides = get_gist_file("names.json")

        display_name = roblox_name if roblox_name else user_id

        found = False
        for entry in manual_data:
            if entry[0] == user_id:
                entry[1] = roblox_name
                found = True
                break
        if not found:
            manual_data.append([user_id, display_name])

        count = sync_and_publish(manual_override=manual_data, names_override=name_overrides)
        await interaction.followup.send(f"Added **{user_id}** as '{display_name}'. Total: {count}")

    @app_commands.command(name="update", description="Update a user's Roblox name")
    async def update(self, interaction: discord.Interaction, member: discord.Member, roblox_name: str):
        if not IsAdmin(interaction.user):
            await interaction.response.send_message("No permission.", ephemeral=True)
            return

        await interaction.response.defer()
        manual_data = get_gist_file("manual.json")
        names = get_gist_file("names.json")
        
        names[str(member.id)] = roblox_name
        
        count = sync_and_publish(manual_override=manual_data, names_override=names)
        await interaction.followup.send(f"Updated **{member.name}** to Roblox name **{roblox_name}**.")

    @app_commands.command(name="delete", description="Remove a user from manual list and name overrides")
    async def delete(self, interaction: discord.Interaction, member: discord.Member):
        if not IsAdmin(interaction.user):
            await interaction.response.send_message("No permission.", ephemeral=True)
            return

        await interaction.response.defer()
        manual_data = get_gist_file("manual.json")
        names = get_gist_file("names.json")
        user_id_str = str(member.id)

        new_manual = [entry for entry in manual_data if entry[0] != user_id_str]
        
        if user_id_str in names:
            del names[user_id_str]

        count = sync_and_publish(manual_override=new_manual, names_override=names)
        await interaction.followup.send(f"🗑️ Removed **{member.name}** from all manual lists. Total: {count}")

@client.tree.command(name="sync", description="Force an immediate sync between Discord and Gist")
async def force_sync(interaction: discord.Interaction):
    if not IsAdmin(interaction.user):
            await interaction.response.send_message("No permission.", ephemeral=True)
            return

    await interaction.response.defer()
    try:
        count = sync_and_publish()
        await interaction.followup.send(f"Force sync complete. Data pushed to Gist. Total users: {count}")
    except Exception as e:
        await interaction.followup.send(f"sync failed: {e}")

user_group = UserGroup()
client.tree.add_command(user_group)

# --- EVENTS ---

@client.event
async def on_ready():
    print(f'Logged in as {client.user}. Initial Sync...')
    print(f'AI backend: {OLLAMA_HOST} | Model: {OLLAMA_MODEL}')
    clear_external_bridge()
    count = sync_and_publish()
    print(f"Sync complete. {count} total users in list.")

@client.event
async def on_member_update(before, after):
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
        if message.guild.id != ALLOWED_GUILD_ID:
            return

        print(f"\r\n \r\n prompt: {message.content}")

        # Show a typing indicator while the model generates
        async with message.channel.typing():
            response = await prompt_ollama(message.content)

        print(f"response: {response}")

        # Discord messages have a 2000 char limit — chunk if needed
        if len(response) <= 2000:
            await message.channel.send(response)
        else:
            for i in range(0, len(response), 2000):
                await message.channel.send(response[i:i+2000])

class robloxmoderationGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="roblox", description="for mods")

    async def resolve_user_id(self, target: str) -> tuple[str | None, str | None]:
        """Returns (user_id, error_message). Accepts a numeric ID or a username."""
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

    @app_commands.command(name="ban", description="Ban a Roblox user by ID or username")
    @app_commands.describe(target="The Roblox username or user ID to ban.", reason="The reason for the ban.", time_minutes="Duration of the ban in minutes. Leave empty for a permanent ban.")
    async def ban(self, interaction: discord.Interaction, target: str, reason: str, time_minutes: Optional[float] = None):
        if not IsAdmin(interaction.user):
            await interaction.response.send_message("No permission.", ephemeral=True)
            return

        await interaction.response.defer()

        user_id, error = await self.resolve_user_id(target)
        if error:
            await interaction.followup.send(f"{error}")
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
                    followUpMsg = f"Successfully banned {label} for {time_minutes} minutes."

                    if not time_minutes:
                        followUpMsg = f"Successfully banned {label} permanently."

                    logTime = f"{time_minutes} minutes"

                    if not time_minutes:
                        logTime = "Permanently"

                    await log_action(
                        title="🔨 Roblox User Banned",
                        description=(
                            f"**Target:** {label}\n"
                            f"**Moderator:** {interaction.user.mention}\n"
                            f"**Duration:** {logTime}\n"
                            f"**Reason:** {reason}"
                        ),
                        color=discord.Color.red()
                    )

                    await interaction.followup.send(followUpMsg)
                else:
                    error_text = await response.text()
                    await interaction.followup.send(f"Failed to ban. Status: {response.status}\n`{error_text}`")

        
    @app_commands.command(name="unban", description="Unban a Roblox user by ID or username")
    async def unban(self, interaction: discord.Interaction, target: str):
        if not IsAdmin(interaction.user):
            await interaction.response.send_message("No permission.", ephemeral=True)
            return

        await interaction.response.defer()

        user_id, error = await self.resolve_user_id(target)
        if error:
            await interaction.followup.send(f"{error}")
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

                    await log_action(
                        title="🔨 Roblox User Unbanned",
                        description=(
                            f"**Target:** {label}\n"
                            f"**Moderator:** {interaction.user.mention}\n"
                        ),
                        color=discord.Color.green()
                    )
                    
                    await interaction.followup.send(f"Successfully unbanned {label}.")
                else:
                    error_text = await response.text()
                    await interaction.followup.send(f"Failed to unban. Status: {response.status}\n`{error_text}`")

roblox_mod_group = robloxmoderationGroup()
client.tree.add_command(roblox_mod_group)

class discordmoderationGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="discord", description="for mods")

    @app_commands.command(name="globalban", description="Ban a user from all servers the bot is in")
    @app_commands.describe(user="User ID to ban", reason="Reason for the ban")
    async def globalban(self, interaction: discord.Interaction, user: discord.User, reason: str = "No reason provided"):
        if not IsAdmin(interaction.user):
            await interaction.response.send_message("No permission.", ephemeral=True)
            return

        await interaction.response.defer()

        success, failed, skipped = [], [], []

        for guild in client.guilds:
            me = guild.me
            if not me.guild_permissions.ban_members:
                skipped.append(f"{guild.name} (no permission)")
                continue

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

        lines = [f"Globally banned `{user}` (ID: `{user.id}`)"]
        lines.append(f"**Banned in {len(success)}/{len(client.guilds)} servers**")
        if skipped:
            lines.append(f"Skipped: {', '.join(skipped)}")
        if failed:
            lines.append(f"Failed: {', '.join(failed)}")

        await interaction.followup.send("\n".join(lines))


    @app_commands.command(name="globalunban", description="Unban a user from all servers the bot is in")
    @app_commands.describe(user="User ID to unban", reason="Reason for the unban")
    async def globalunban(self, interaction: discord.Interaction, user: discord.User, reason: str = "No reason provided"):
        if not IsAdmin(interaction.user):
            await interaction.response.send_message("No permission.", ephemeral=True)
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

        lines = [f"Globally unbanned `{user}` (ID: `{user.id}`)"]
        lines.append(f"**Unbanned in {len(success)}/{len(client.guilds)} servers**")
        if not_banned:
            lines.append(f"Not banned in: {', '.join(not_banned)}")
        if skipped:
            lines.append(f"Skipped: {', '.join(skipped)}")
        if failed:
            lines.append(f"Failed: {', '.join(failed)}")

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
        duration_days="How many days to suspend (leave empty for permanent)"
    )
    async def suspend(self, interaction: discord.Interaction, discord_account: discord.User, target: str, duration_days: Optional[int] = None):
        if not IsEASuspensionMod(interaction.user):
            await interaction.response.send_message("No permission.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        user_id, error = await self.resolve_user_id(target)
        if error:
            await interaction.followup.send(f"{error}")
            return

        suspension_data = {
            "suspended": True,
            "expires_at": int(time.time()) + (duration_days * 86400) if duration_days else None,
            "duration_days": duration_days
        }

        entry_key = str(user_id)
        url = f"https://apis.roblox.com/datastores/v1/universes/{UNIVERSE_ID}/standard-datastores/datastore/entries/entry"
        params = {"datastoreName": suspension_dataStore_ID, "entryKey": entry_key}
        headers = {"x-api-key": ROBLOX_API_KEY, "content-type": "application/json"}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, params=params, data=json.dumps(suspension_data)) as response:
                if response.status == 200:
                    duration_text = f"**{duration_days} day(s)**" if duration_days else "**permanently**"

                    role_guild = client.get_guild(EA_SUSPENSION_GUILD_ID)
                    if not role_guild:
                        await interaction.followup.send(f"Suspended in DataStore but couldn't find the suspension guild.")
                        return

                    member = role_guild.get_member(discord_account.id)
                    if not member:
                        await interaction.followup.send(f"Suspended in DataStore but `{discord_account}` is not in the suspension server.")
                        return

                    role = role_guild.get_role(EA_SUSPENDED_ROLE_ID)
                    if role:
                        try:
                            await member.add_roles(role, reason=f"EA suspended by {interaction.user}")
                        except discord.Forbidden:
                            await interaction.followup.send(f"Suspended in DataStore but couldn't assign role (missing permissions).")
                            return

                    await interaction.followup.send(f"Successfully suspended `{target}` (ID: `{user_id}`) {duration_text} and assigned suspended role to {discord_account.mention}.")
                else:
                    err_body = await response.text()
                    await interaction.followup.send(f"Failed to update Roblox DataStore. Status: {response.status}\n`{err_body}`")

    @app_commands.command(name="unsuspend", description="Remove an EA suspension from a Roblox user")
    @app_commands.describe(target="Roblox Username or ID to unsuspend")
    async def unsuspend(self, interaction: discord.Interaction, discord_account: discord.User, target: str):
        if not IsEASuspensionMod(interaction.user):
            await interaction.response.send_message("No permission.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        user_id, error = await self.resolve_user_id(target)
        if error:
            await interaction.followup.send(f"{error}")
            return

        entry_key = str(user_id)
        url = f"https://apis.roblox.com/datastores/v1/universes/{UNIVERSE_ID}/standard-datastores/datastore/entries/entry"
        params = {
            "datastoreName": suspension_dataStore_ID,
            "entryKey": entry_key
        }
        headers = {"x-api-key": ROBLOX_API_KEY}

        async with aiohttp.ClientSession() as session:
            async with session.delete(url, headers=headers, params=params) as response:
                if response.status in (200, 204):
                    role_guild = client.get_guild(EA_SUSPENSION_GUILD_ID)
                    if role_guild:
                        member = role_guild.get_member(discord_account.id)
                        role = role_guild.get_role(EA_SUSPENDED_ROLE_ID)
                        if member and role and role in member.roles:
                            try:
                                await member.remove_roles(role, reason=f"EA unsuspended by {interaction.user}")
                            except discord.Forbidden:
                                await interaction.followup.send(f"Unsuspended in DataStore but couldn't remove role (missing permissions).")
                                return

                    await interaction.followup.send(f"Successfully unsuspended `{target}` (ID: `{user_id}`) and removed suspended role from {discord_account.mention}.")
                elif response.status == 404:
                    await interaction.followup.send(f"User `{target}` is not currently suspended.")
                else:
                    err_body = await response.text()
                    await interaction.followup.send(f"API Error. Status: {response.status}\n`{err_body}`")


    @app_commands.command(name="blacklist", description="Blacklist a user from specific entities")
    @app_commands.describe(
        target="Roblox Username or ID",
        entities="Entity names separated by commas (e.g. Titan, Dragon)",
        duration_days="Days until expiry (leave empty for permanent)"
    )
    async def blacklist(self, interaction: discord.Interaction, target: str, entities: str, duration_days: Optional[int] = None):
        if not IsEASuspensionMod(interaction.user):
            await interaction.response.send_message("No permission.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        user_id, error = await self.resolve_user_id(target)
        if error:
            await interaction.followup.send(f"{error}")
            return

        entry_key = str(user_id)
        url = f"https://apis.roblox.com/datastores/v1/universes/{UNIVERSE_ID}/standard-datastores/datastore/entries/entry"
        params = {"datastoreName": blacklist_dataStore_ID, "entryKey": entry_key}
        headers = {"x-api-key": ROBLOX_API_KEY, "content-type": "application/json"}

        async with aiohttp.ClientSession() as session:
            current_data = {}
            async with session.get(url, headers=headers, params=params) as get_resp:
                if get_resp.status == 200:
                    try:
                        current_data = await get_resp.json()
                    except:
                        current_data = {}
            
            if not current_data:
                current_data = {}

            entity_list = [e.strip() for e in entities.split(",")]
            expiry = int(time.time()) + (duration_days * 86400) if duration_days else None
            
            for entity in entity_list:
                current_data[entity] = expiry

            async with session.post(url, headers=headers, params=params, data=json.dumps(current_data)) as post_resp:
                if post_resp.status == 200:
                    dur_text = f"{duration_days} days" if duration_days else "Permanent"
                    await interaction.followup.send(f"Blacklisted `{target}` from: **{', '.join(entity_list)}** (Duration: {dur_text})")
                    
                    await log_action(
                        title="EA Blacklist Added",
                        description=f"**User:** {target} ({user_id})\n**Entities:** {', '.join(entity_list)}\n**Duration:** {dur_text}\n**Moderator:** {interaction.user.mention}",
                        color=discord.Color.orange()
                    )
                else:
                    await interaction.followup.send(f"Failed to update DataStore. Status: {post_resp.status}")

    @app_commands.command(name="unblacklist", description="Remove a blacklist for specific entities")
    @app_commands.describe(
        target="Roblox Username or ID",
        entities="Entity names to remove, separated by commas. Use 'ALL' to clear everything."
    )
    async def unblacklist(self, interaction: discord.Interaction, target: str, entities: str):
        if not IsEASuspensionMod(interaction.user):
            await interaction.response.send_message("No permission.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        user_id, error = await self.resolve_user_id(target)
        if error:
            await interaction.followup.send(f"{error}")
            return

        entry_key = str(user_id)
        url = f"https://apis.roblox.com/datastores/v1/universes/{UNIVERSE_ID}/standard-datastores/datastore/entries/entry"
        params = {"datastoreName": blacklist_dataStore_ID, "entryKey": entry_key}
        headers = {"x-api-key": ROBLOX_API_KEY, "content-type": "application/json"}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as get_resp:
                if get_resp.status != 200:
                    await interaction.followup.send("ℹThis user has no active blacklists.")
                    return
                current_data = await get_resp.json()

            if "entities" not in current_data:
                await interaction.followup.send("ℹNo entity data found for this user.")
                return

            if entities.upper() == "ALL":
                current_data["entities"] = {}
                removed = ["ALL"]
            else:
                to_remove = [e.strip() for e in entities.split(",")]
                removed = []
                for e in to_remove:
                    if e in current_data["entities"]:
                        del current_data["entities"][e]
                        removed.append(e)

            if not removed:
                await interaction.followup.send(f"User wasn't blacklisted from any of: {entities}")
                return

            if not current_data["entities"]:
                async with session.delete(url, headers=headers, params=params) as del_resp:
                    success = del_resp.status in (200, 204)
            else:
                async with session.post(url, headers=headers, params=params, data=json.dumps(current_data)) as post_resp:
                    success = post_resp.status == 200

            if success:
                await interaction.followup.send(f"Removed blacklist from **{', '.join(removed)}** for `{target}`.")
                await log_action(
                    title="🔓 EA Blacklist Removed",
                    description=f"**User:** {target} ({user_id})\n**Removed:** {', '.join(removed)}\n**Moderator:** {interaction.user.mention}",
                    color=discord.Color.blue()
                )
            else:
                await interaction.followup.send("Error updating Roblox DataStore.")

    @app_commands.command(name="list", description="debug cmd, does not do shit")
    async def list_suspended(self, interaction: discord.Interaction):
        if not IsAdmin(interaction.user):
            await interaction.response.send_message("No permission.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        entries = await self.get_entries()
        print(entries)
        await interaction.followup.send("Entries printed to console.")

EA_mod_group = EAmoderationGroup()
client.tree.add_command(EA_mod_group)


def add_command_to_queue(new_command):
    """Fetches the current queue, adds a new command, and pushes back to Gist."""
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    
    current_queue = get_gist_file("ExternalBridge.json")
    if not isinstance(current_queue, list):
        current_queue = []
    
    current_queue.append(new_command)
    
    payload = {
        "files": {
            "ExternalBridge.json": {"content": json.dumps(current_queue, indent=2)}
        }
    }
    requests.patch(url, headers=headers, json=payload)

# --- MOON COMMAND GROUP ---

class MoonControlGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="moon", description="Control the game atmosphere")

    @app_commands.command(name="set", description="Trigger a blackout or change the moon style with a delay")
    @app_commands.describe(delay="Set a delay in seconds before the moon triggers", debug="Makes the command only trigger in private servers and studio")
    async def set_moon(
        self, 
        interaction: discord.Interaction, 
        enabled: bool, 
        style: Literal['blood', 'fun', 'hallow', 'blackout'],
        delay: int,
        debug: bool,
    ):
        if not IsAdmin(interaction.user):
            await interaction.response.send_message("No permission.", ephemeral=True)
            return

        await interaction.response.defer()

        new_command = {
            "bool": enabled,
            "style": style,
            "delay": delay,
            "timestamp": discord.utils.utcnow().timestamp(),
            "debug": debug
        }

        try:
            add_command_to_queue(new_command)
            status_text = "ENABLED" if enabled else "DISABLED"
            await interaction.followup.send(f"**{style.upper()}** moon set to **{status_text}** in **{delay} seconds**. Pushed to Gist.")
        except Exception as e:
            await interaction.followup.send(f"Gist update failed: {e}")

moon_group = MoonControlGroup()
client.tree.add_command(moon_group)

class SettingsGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="settings", description="AI configuration settings")

    @app_commands.command(name="get_instructions", description="View current AI system instructions from the Gist")
    async def get_instructions(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not IsAdmin(interaction.user):
            await interaction.followup.send("No permission.")
            return

        async with aiohttp.ClientSession() as session:
            async with session.get(SYSTEM_INSTRUCTION_URL) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    if len(text) > 1900:
                        text = text[:1900] + "... (truncated)"
                    await interaction.followup.send(f"**Current System Instructions:**\n```\n{text}\n```")
                else:
                    await interaction.followup.send(f"Failed to fetch Gist. Status: {resp.status}")

    @app_commands.command(name="set_instructions", description="Update the AI system instructions in the Gist")
    @app_commands.describe(new_text="The new system instruction text")
    async def set_instructions(self, interaction: discord.Interaction, new_text: str):
        await interaction.response.defer(ephemeral=True)

        if not IsAdmin(interaction.user):
            await interaction.followup.send("No permission.")
            return

        FILENAME = "instructions.txt" 
        url = f"https://api.github.com/gists/{GIST_ID}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        payload = {
            "files": {
                FILENAME: {"content": new_text}
            }
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.patch(url, headers=headers, json=payload) as resp:
                    if resp.status == 200:
                        await interaction.followup.send("✅ System instructions updated successfully!")
                        await log_action(
                            title="⚙️ AI Instructions Updated",
                            description=f"**Moderator:** {interaction.user.mention}\n**New Text Preview:** {new_text[:500]}...",
                            color=discord.Color.purple()
                        )
                    else:
                        await interaction.followup.send(f"❌ GitHub API Error ({resp.status}). Check your Token/Gist ID.")
        except Exception as e:
            await interaction.followup.send(f"❌ A Python error occurred: {e}")

    @app_commands.command(name="ai_status", description="Check if the local Ollama instance is reachable")
    async def ai_status(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not IsAdmin(interaction.user):
            await interaction.followup.send("No permission.")
            return

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{OLLAMA_HOST}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        model_names = [m["name"] for m in data.get("models", [])]
                        models_str = ", ".join(model_names) if model_names else "none loaded"
                        await interaction.followup.send(
                            f"✅ Ollama is online at `{OLLAMA_HOST}`\n"
                            f"**Active model:** `{OLLAMA_MODEL}`\n"
                            f"**Available models:** {models_str}"
                        )
                    else:
                        await interaction.followup.send(f"⚠️ Ollama responded with status {resp.status}.")
        except Exception as e:
            await interaction.followup.send(f"❌ Could not reach Ollama at `{OLLAMA_HOST}`\nError: `{e}`")

settings_group = SettingsGroup()
client.tree.add_command(settings_group)

client.run(TOKEN)