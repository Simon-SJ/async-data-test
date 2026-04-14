import discord
from discord import app_commands
import requests
import os
import json
import random
import aiohttp

# --- CONFIG ---
UNIVERSE_ID = 9256427353
ROBLOX_API_KEY = os.getenv("ROBLOX_API_KEY")
TOKEN = os.getenv("DISCORD_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GIST_ID = os.getenv("GIST_ID")
ADMIN_IDs = {595524051208765442, 554691397601591306, 781870312194703380}
MODERATOR_ROLE_ID = 1279483933943136368

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
            
            # Check for Moderators (Specific Role)
            if any(role.id == MODERATOR_ROLE_ID for role in member.roles):
                moderators.append([str(member.id), member.display_name])

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
        if interaction.user.id not in ADMIN_IDs:
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
        if interaction.user.id not in ADMIN_IDs:
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
        if interaction.user.id not in ADMIN_IDs:
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
    if interaction.user.id not in ADMIN_IDs:
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

class moderationGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="moderation", description="for mods")

    # Use @app_commands.command, and ensure parameter 'time_minutes' is lowercase
    @app_commands.command(name="ban", description="Ban a roblox user")
    async def ban(self, interaction: discord.Interaction, target: str, time_minutes: float, reason: str = "No reason provided"):
        if interaction.user.id not in ADMIN_IDs:
            await interaction.response.send_message("❌ No permission.", ephemeral=True)
            return

        await interaction.response.defer()

        user_id = target 
        # Ensure we use the correct variable name defined in the arguments above
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
                "privateReason": reason,
                "displayReason": reason,
                "excludeAltAccounts": False
            }
        }

        async with aiohttp.ClientSession() as session:
            async with session.patch(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    await interaction.followup.send(f"✅ Successfully banned ID `{user_id}` for {time_minutes} minutes.")
                else:
                    error_text = await response.text()
                    await interaction.followup.send(f"❌ Failed to ban. Status: {response.status}\n`{error_text}`")

# These lines at the end are correct
mod_group = moderationGroup()
client.tree.add_command(mod_group)


client.run(TOKEN)