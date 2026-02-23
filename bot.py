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

def sync_and_publish():
    # 1. Load our saved data
    manual_list = get_gist_file("manual.json") # [[id, name], ...]
    name_overrides = get_gist_file("names.json") # {id: roblox_name}

    # 2. Get live boosters from Discord
    live_boosters = []
    for guild in client.guilds:
        for member in guild.members:
            if member.premium_since:
                live_boosters.append([str(member.id), member.display_name])

    # 3. Combine lists (ID is key)
    combined = {}
    
    # Add manual users first
    for m_id, m_name in manual_list:
        combined[m_id] = m_name
        
    # Add live boosters (overwrites if they are in both)
    for b_id, b_name in live_boosters:
        combined[b_id] = b_name

    # 4. APPLY NAME OVERRIDES (The Roblox names)
    # This loop checks if we have a saved Roblox name for ANYONE in the list
    final_output = []
    for user_id, current_name in combined.items():
        # If we have a saved name for this ID, use it. Otherwise, use Discord name.
        name_to_use = name_overrides.get(user_id, current_name)
        final_output.append([user_id, name_to_use])

    # 5. Push to GitHub
    push_all_to_gist(final_output, manual_list, name_overrides)
    return len(final_output)

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

    if message.content.lower().startswith(f"{PREFIX}adduser"):
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
    
    if message.content.lower().startswith(f"{PREFIX}updateuser"):
        try:
            parts = message.content.split(" ")
            if len(parts) < 3:
                await message.channel.send("Usage: `:updateuser [id] [roblox_name]`")
                return

            target_id = parts[1]
            roblox_name = " ".join(parts[2:])
            
            # 1. Update the name mapping
            names = get_gist_file("names.json")
            names[target_id] = roblox_name
            
            # 2. Re-run the sync to update data.json
            # Note: We need to pull manual_data to pass it back to the push function
            manual_data = get_gist_file("manual.json")
            
            # Use the logic from step 2 to merge and push
            sync_and_publish()
            
            await message.channel.send(f"✅ Linked ID `{target_id}` to Roblox: **{roblox_name}**")
        except Exception as e:
            await message.channel.send(f"❌ Error: {str(e)}")

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