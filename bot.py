import discord
import requests
import os
import json

# --- CONFIG ---
TOKEN = os.getenv("DISCORD_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GIST_ID = os.getenv("GIST_ID")
MY_ID = 595524051208765442

intents = discord.Intents.default()
intents.members = True 
intents.message_content = True
client = discord.Client(intents=intents)

def get_current_gist():
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    try:
        r = requests.get(url, headers=headers)
        # Returns the 2D array: [[id, name], [id, name]]
        return json.loads(r.json()['files']['data.json']['content'])
    except Exception as e:
        print(f"Error fetching Gist: {e}")
<<<<<<< HEAD
        return []
=======
        # Initialize with your requested two-array structure
        return {"discord-ids": [], "discord-names": []}
>>>>>>> d56e5d2d416fbaf80072827efbe9355b037ebe3f

def push_to_gist(content):
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    payload = {"files": {"data.json": {"content": json.dumps(content, indent=2)}}}
    requests.patch(url, headers=headers, json=payload)

def sync_all_boosters():
<<<<<<< HEAD
    """Returns a 2D list of [id, name] for all active boosters."""
    booster_list = []
    for guild in client.guilds:
        for member in guild.members:
            if member.premium_since is not None:
                booster_list.append([str(member.id), member.display_name])
    return booster_list

@client.event
async def on_ready():
    print(f'Logged in as {client.user}. Syncing 2D array...')
    data = sync_all_boosters()
    push_to_gist(data)
    print(f"Sync complete. {len(data)} boosters found.")

@client.event
async def on_member_update(before, after):
    # Update if boost status or nickname changes
    if (before.premium_since != after.premium_since) or (before.display_name != after.display_name):
        data = sync_all_boosters()
        push_to_gist(data)
=======
    """Rebuilds both arrays from scratch so indexes always match."""
    ids = []
    names = []
    for guild in client.guilds:
        for member in guild.members:
            if member.premium_since is not None:
                ids.append(str(member.id))
                names.append(member.display_name)
    return {"discord-ids": ids, "discord-names": names}

@client.event
async def on_ready():
    print(f'Logged in as {client.user}. Syncing arrays...')
    data = sync_all_boosters()
    push_to_gist(data)
    print(f"Sync complete. {len(data['discord-ids'])} boosters synced.")

@client.event
async def on_member_update(before, after):
    # If boosting status or nickname changes, refresh everything
    if (before.premium_since != after.premium_since) or (before.display_name != after.display_name):
        data = sync_all_boosters()
        push_to_gist(data)
        print(f"Updated list due to change in {after.name}")
>>>>>>> d56e5d2d416fbaf80072827efbe9355b037ebe3f

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith("!test") and message.author.id == MY_ID:
        try:
<<<<<<< HEAD
=======
            # Format: !test 123456789 RobloxName
>>>>>>> d56e5d2d416fbaf80072827efbe9355b037ebe3f
            parts = message.content.split(" ")
            if len(parts) != 3:
                await message.channel.send("Usage: `!test [id] [name]`")
                return

            new_id, new_name = parts[1], parts[2]
            data = get_current_gist()

<<<<<<< HEAD
            # Update existing entry or add new one
            found = False
            for entry in data:
                if entry[0] == new_id:
                    entry[1] = new_name
                    found = True
                    break
            
            if not found:
                data.append([new_id, new_name])
            
            push_to_gist(data)
            await message.channel.send(f"✅ Synced {new_name} in 2D array.")
=======
            # If the ID already exists, update its name at the same index
            if new_id in data["discord-ids"]:
                idx = data["discord-ids"].index(new_id)
                data["discord-names"][idx] = new_name
            else:
                # Otherwise, append to both
                data["discord-ids"].append(new_id)
                data["discord-names"].append(new_name)
            
            push_to_gist(data)
            await message.channel.send(f"✅ Synced {new_name} at index {len(data['discord-ids'])-1}")
>>>>>>> d56e5d2d416fbaf80072827efbe9355b037ebe3f
        except Exception as e:
            await message.channel.send(f"❌ Error: {str(e)}")

client.run(TOKEN)