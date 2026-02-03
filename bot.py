import discord
import requests
import os
import json

# --- CONFIGURATION ---
TOKEN = os.getenv("DISCORD_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GIST_ID = os.getenv("GIST_ID")

intents = discord.Intents.default()
intents.members = True  # Required to see member updates
client = discord.Client(intents=intents)

def update_gist(discord_id):
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    
    # 1. Fetch current data
    current_gist = requests.get(url).json()
    content = json.loads(current_gist['files']['data.json']['content'])
    
    # 2. Add new ID if not already there
    if discord_id not in content["discord-ids"]:
        content["discord-ids"].append(discord_id)
        
        # 3. Push update back to GitHub
        payload = {"files": {"data.json": {"content": json.dumps(content, indent=2)}}}
        requests.patch(url, headers=headers, json=payload)
        print(f"Added {discord_id} to Gist!")

@client.event
async def on_ready():
    print(f'Bot logged in as {client.user}')

@client.event
async def on_member_update(before, after):
    # Check if they started boosting
    # premium_since is None if they aren't boosting
    if before.premium_since is None and after.premium_since is not None:
        print(f"{after.name} just boosted!")
        update_gist(str(after.id))

client.run(TOKEN)