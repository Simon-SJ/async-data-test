import discord
import requests
import os
import json
import random

# --- CONFIG ---
TOKEN = os.getenv("DISCORD_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GIST_ID = os.getenv("GIST_ID")
            #simonsj             guy56790            scripto
ADMIN_IDs = {595524051208765442, 554691397601591306, 781870312194703380}
PREFIX = ":"

intents = discord.Intents.default()
intents.members = True 
intents.message_content = True
client = discord.Client(intents=intents)

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

def push_all_to_gist(final_data, manual_data, name_overrides):
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    payload = {
        "files": {
            "data.json": {"content": json.dumps(final_data, indent=2)},
            "manual.json": {"content": json.dumps(manual_data, indent=2)},
            "names.json": {"content": json.dumps(name_overrides, indent=2)}
        }
    }
    requests.patch(url, headers=headers, json=payload)

def sync_and_publish():
    """The master function that merges Discord, Manual, and Roblox Name Overrides."""
    # 1. Load saved data from Gist
    manual_list = get_gist_file("manual.json")
    name_overrides = get_gist_file("names.json")

    # 2. Get live boosters from Discord
    live_boosters = []
    for guild in client.guilds:
        for member in guild.members:
            if member.premium_since:
                live_boosters.append([str(member.id), member.display_name])

    # 3. Combine lists (Discord boosters + Manual additions)
    combined = {entry[0]: entry[1] for entry in manual_list}
    for b_id, b_name in live_boosters:
        combined[b_id] = b_name

    # 4. Apply Roblox Name Overrides (If ID exists in names.json, use that name instead)
    final_output = []
    for user_id, current_name in combined.items():
        name_to_use = name_overrides.get(user_id, current_name)
        final_output.append([user_id, name_to_use])

    # 5. Push all files back to Gist
    push_all_to_gist(final_output, manual_list, name_overrides)
    return len(final_output)

# --- EVENTS ---

@client.event
async def on_ready():
    print(f'Logged in as {client.user}. Initial Sync...')
    count = sync_and_publish()
    print(f"Sync complete. {count} total users in list.")

@client.event
async def on_member_update(before, after):
    # Trigger if someone starts/stops boosting or changes their Discord nickname
    if (before.premium_since != after.premium_since) or (before.display_name != after.display_name):
        sync_and_publish()

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    # DM Forwarder logic
    if message.guild is None:
        DmChannel = client.get_channel(1470330654448156672)
        if DmChannel:
            await DmChannel.send(f"{message.content} from {message.author}")

    # Mentions/Fun logic
    if "<@1468279695547044038>" in message.content:
        await message.channel.send(random.choice(["hello", "hi", "What's up"]))
    elif "<@554691397601591306>" in message.content:
        if random.randint(1, 20) == 1:
            await message.reply(random.choice(["hello", "hi", "What's up"]))

    if not message.content.startswith(PREFIX):
        return

    if message.author.id not in ADMIN_IDs:
        return

    # COMMAND: Add User
    if message.content.lower().startswith(f"{PREFIX}adduser"):
        try:
            parts = message.content.split(" ")
            if len(parts) < 3:
                await message.channel.send("Usage: `:addUser [id] [name]`")
                return

            new_id = parts[1]
            new_name = " ".join(parts[2:])
            
            manual_data = get_gist_file("manual.json")
            
            # Update or Append
            found = False
            for entry in manual_data:
                if entry[0] == new_id:
                    entry[1] = new_name
                    found = True
                    break
            if not found:
                manual_data.append([new_id, new_name])

            # Use our unified push function (requires fetching names too)
            name_overrides = get_gist_file("names.json")
            
            # This pushes the manual update and refreshes data.json
            sync_and_publish() 
            
            await message.channel.send(f"✅ Added {new_name} to manual list and synced.")
        except Exception as e:
            await message.channel.send(f"❌ Error: {str(e)}")
    
    # COMMAND: Update Roblox Name (Works for ANYONE)
    if message.content.lower().startswith(f"{PREFIX}updateuser"):
        try:
            parts = message.content.split(" ")
            if len(parts) < 3:
                await message.channel.send("Usage: `:updateuser [id] [roblox_name]`")
                return

            target_id = parts[1]
            roblox_name = " ".join(parts[2:])
            
            names = get_gist_file("names.json")
            names[target_id] = roblox_name
            
            # Logic inside sync_and_publish handles merging this into the final list
            sync_and_publish()
            
            await message.channel.send(f"✅ Linked ID `{target_id}` to Roblox: **{roblox_name}**")
        except Exception as e:
            await message.channel.send(f"❌ Error: {str(e)}")

    # COMMAND: DM
    if message.content.lower().startswith(f"{PREFIX}dm"):
        try:
            parts = message.content.split(" ")
            if len(parts) < 3:
                await message.channel.send("Usage: `:dm [user id] [message]`")
                return
            
            user_id = parts[1]
            text = " ".join(parts[2:]).replace('_', ' ')

            user = await client.fetch_user(user_id)
            await user.send(text)
            await message.channel.send(f"✉️ Sent DM to {user.name}")
        except Exception as e:
            await message.channel.send(f"❌ Error: {str(e)}")

client.run(TOKEN)