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
        return json.loads(r.json()['files']['data.json']['content'])
    except Exception as e:
        print(f"Error fetching Gist: {e}")
        # Initialize with your requested two-array structure
        return {"discord-ids": [], "discord-names": []}

def push_to_gist(content):
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    payload = {"files": {"data.json": {"content": json.dumps(content, indent=2)}}}
    requests.patch(url, headers=headers, json=payload)

def sync_all_boosters():
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

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith("!test") and message.author.id == MY_ID:
        try:
            # Format: !test 123456789 RobloxName
            parts = message.content.split(" ")
            if len(parts) != 3:
                await message.channel.send("Usage: `!test [id] [name]`")
                return

            new_id, new_name = parts[1], parts[2]
            data = get_current_gist()

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
        except Exception as e:
            await message.channel.send(f"❌ Error: {str(e)}")

client.run(TOKEN)