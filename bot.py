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

def get_gist_file(filename):
    """Helper to get content of a specific file in the Gist."""
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    try:
        r = requests.get(url, headers=headers)
        files = r.json().get('files', {})
        if filename in files:
            return json.loads(files[filename]['content'])
        return []
    except Exception as e:
        print(f"Error fetching {filename}: {e}")
        return []

def push_to_gist(data_content, manual_content=None):
    """Updates the Gist. Can update data.json and manual.json simultaneously."""
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    
    files_payload = {
        "data.json": {"content": json.dumps(data_content, indent=2)}
    }
    
    # If we are specifically updating the manual list, include it
    if manual_content is not None:
        files_payload["manual.json"] = {"content": json.dumps(manual_content, indent=2)}

    payload = {"files": files_payload}
    requests.patch(url, headers=headers, json=payload)

def update_full_list():
    """Combines live boosters + manual list and pushes to data.json."""
    # 1. Get live boosters from Discord
    live_boosters = []
    for guild in client.guilds:
        for member in guild.members:
            if member.premium_since is not None:
                live_boosters.append([str(member.id), member.display_name])
    
    # 2. Get manual list from Gist
    manual_list = get_gist_file("manual.json")
    
    # 3. Merge (Live boosters take priority if ID overlaps)
    combined = {entry[0]: entry[1] for entry in manual_list} # Start with manual
    for b_id, b_name in live_boosters:
        combined[b_id] = b_name # Overwrite/Add with live boosters
    
    # Convert back to 2D array [[id, name], ...]
    final_data = [[uid, name] for uid, name in combined.items()]
    
    # 4. Push only the combined result to data.json
    push_to_gist(final_data)
    return len(final_data)

@client.event
async def on_ready():
    print(f'Logged in as {client.user}. Syncing...')
    count = update_full_list()
    print(f"Sync complete. {count} total users in list.")

@client.event
async def on_member_update(before, after):
    if (before.premium_since != after.premium_since) or (before.display_name != after.display_name):
        update_full_list()

@client.event
async def on_message(message):
    if message.author == client.user:
            return

    if message.guild == None:
        DmChannel = client.get_channel(1470330654448156672)
        await DmChannel.send(f"{message.content} from {message.author}")

    if message.content.__contains__("<@1468279695547044038>"): #gal56890
        rng = random.randint(1, 3)
        match rng: 
            case 1: 
                await message.channel.send("hello")
            case 2:
                await message.channel.send("hi")
            case 3:
                await message.channel.send("What's up")
    elif message.content.__contains__("<@554691397601591306>"): #guy56890
        rng = random.randint(1, 20)
        if rng == 1:
            rng = random.randint(1, 3)
            match rng: 
                case 1: 
                    await message.reply("hello")
                case 2:
                    await message.reply("hi")
                case 3:
                    await message.reply("What's up")

    #author_id = message.author.id
    author_name = message.author.name

    if not message.content.startswith(":"):
        return

    if not ADMIN_IDs.__contains__(message.author.id):
        print("user is not an admin")
        return

    print(f"{author_name} has sent {message.content}")

    if message.content.lower.startswith(f"{PREFIX}adduser"):
        try:
            parts = message.content.split(" ")
            if len(parts) < 3:
                await message.channel.send("Usage: `:addUser [id] [name]`")
                return

            new_id = parts[1]
            new_name = " ".join(parts[2:]) # Allows names with spaces
            
            # 1. Fetch current manual list
            manual_data = get_gist_file("manual.json")

            # 2. Update the manual list
            found = False
            for entry in manual_data:
                if entry[0] == new_id:
                    entry[1] = new_name
                    found = True
                    break
            if not found:
                manual_data.append([new_id, new_name])

            # 3. Save to manual.json AND refresh the main data.json
            # We fetch live boosters again to ensure data.json is perfectly synced
            live_boosters = []
            for guild in client.guilds:
                for member in guild.members:
                    if member.premium_since is not None:
                        live_boosters.append([str(member.id), member.display_name])

            combined = {entry[0]: entry[1] for entry in manual_data}
            for b_id, b_name in live_boosters:
                combined[b_id] = b_name
            
            final_data = [[uid, name] for uid, name in combined.items()]

            # Push both files at once
            push_to_gist(final_data, manual_content=manual_data)
            
            await message.channel.send(f"✅ Added {new_name} to manual list and synced Gist.")
        except Exception as e:
            await message.channel.send(f"❌ Error: {str(e)}")
    
    if message.content.lower.startswith(f"{PREFIX}updateuser"):
        try:
            parts = message.content.split(" ")
            if len(parts) < 3:
                await message.channel.send("Usage: `:updateUser [id] [new_roblox_name]`")
                return

            target_id = parts[1]
            new_name = " ".join(parts[2:])
            
            # 1. Fetch current manual list
            manual_data = get_gist_file("manual.json")

            # 2. Update the entry if ID matches
            found_in_manual = False
            for entry in manual_data:
                if entry[0] == target_id:
                    entry[1] = new_name
                    found_in_manual = True
                    break
            
            if not found_in_manual:
                await message.channel.send(f"⚠️ ID `{target_id}` isn't in the manual list. Use `:addUser` instead if they aren't a server booster.")
                return

            # 3. Re-sync everything to update data.json
            # Get live boosters
            live_boosters = []
            for guild in client.guilds:
                for member in guild.members:
                    if member.premium_since is not None:
                        live_boosters.append([str(member.id), member.display_name])

            # Merge manual list into live boosters
            combined = {entry[0]: entry[1] for entry in manual_data}
            for b_id, b_name in live_boosters:
                combined[b_id] = b_name
            
            final_data = [[uid, name] for uid, name in combined.items()]

            # 4. Push updates
            push_to_gist(final_data, manual_content=manual_data)
            
            await message.channel.send(f"✅ Updated ID `{target_id}` to Roblox name: **{new_name}**")

        except Exception as e:
            await message.channel.send(f"❌ Error updating user: {str(e)}")

    if message.content.lower.startswith(f"{PREFIX}dm"):
        try:
            parts = message.content.split(" ")
            if len(parts) != 3:
                await message.channel.send("Usage: `!dm [user id] [message]`")
                return
            
            user_id, message_new = parts[1], parts[2]

            message_new_new = ""

            for char in message_new:
                if char == '_':
                    message_new_new += ' '
                else:
                    message_new_new += char

            user = await client.fetch_user(user_id)
            await user.send(message_new_new)

        except Exception as e:
            await message.channel.send(f"❌ Error: {str(e)}")

client.run(TOKEN)