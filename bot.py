import discord
import requests
import os
import json
import asyncio

# --- CONFIG ---
TOKEN = os.getenv("DISCORD_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GIST_ID = os.getenv("GIST_ID")

intents = discord.Intents.default()
intents.members = True 
client = discord.Client(intents=intents)

def get_current_gist():
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    try:
        r = requests.get(url, headers=headers)
        return json.loads(r.json()['files']['data.json']['content'])
    except Exception as e:
        print(f"Error fetching Gist: {e}")
        return {"discord-ids": [], "discord-names": []}

def push_to_gist(content):
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    payload = {"files": {"data.json": {"content": json.dumps(content, indent=2)}}}
    requests.patch(url, headers=headers, json=payload)

def sync_member(member, data):
    """Adds member to data if they are boosting and not already there."""
    changed = False
    if member.premium_since is not None:
        d_id = str(member.id)
        # Use display_name (Nickname) as the Roblox name per your setup
        r_name = member.display_name 

        if d_id not in data["discord-ids"]:
            data["discord-ids"].append(d_id)
            changed = True
        
        if r_name not in data["discord-names"]:
            data["discord-names"].append(r_name)
            changed = True
    return changed

@client.event
async def on_ready():
    print(f'Logged in as {client.user}. Syncing existing boosters...')
    data = get_current_gist()
    has_updates = False

    for guild in client.guilds:
        for member in guild.members:
            if sync_member(member, data):
                has_updates = True

    if has_updates:
        push_to_gist(data)
        print("Gist updated with existing boosters.")
    else:
        print("No new boosters found on startup.")

@client.event
async def on_message(message):
    # Ignore messages from the bot itself
    print("message read: ".append(message.content))
    if message.author == client.user:
        return

    # Security check: Only YOU can run this
    if message.content.startswith("!test") and message.author.id == 595524051208765442:
        try:
            # Command format: !test [discord_id] [roblox_name]
            parts = message.content.split(" ")
            if len(parts) != 3:
                await message.channel.send("Usage: `!test [discord_id] [discord_name]`")
                return

            fake_id = parts[1]
            fake_name = parts[2]

            # Update the Gist
            data = get_current_gist()
            
            if fake_id not in data["discord-ids"]:
                data["discord-ids"].append(fake_id)
            if fake_name not in data["roblox-names"]:
                data["discord-names"].append(fake_name)
            
            push_to_gist(data)
            await message.channel.send(f"✅ Success! Added {fake_name} ({fake_id}) to the data file.")
            
        except Exception as e:
            await message.channel.send(f"❌ Error: {str(e)}")

@client.event
async def on_member_update(before, after):
    # Detect if they just started boosting
    if before.premium_since is None and after.premium_since is not None:
        print(f"New boost from {after.display_name}!")
        data = get_current_gist()
        if sync_member(after, data):
            push_to_gist(data)

client.run(TOKEN)