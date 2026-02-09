import discord
import requests
import os
import json
import random

# --- CONFIG ---
TOKEN = os.getenv("DISCORD_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GIST_ID = os.getenv("GIST_ID")
ADMIN_IDs = {595524051208765442, 554691397601591306}
PREFIX = ":"

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
        return []

def push_to_gist(content):
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    payload = {"files": {"data.json": {"content": json.dumps(content, indent=2)}}}
    requests.patch(url, headers=headers, json=payload)

def sync_all_boosters():
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

@client.event
async def on_message(message):
    if message.author == client.user:
            return

    if message.guild == None:
        DmChannel = client.get_channel(1470330654448156672)
        await DmChannel.send(f"{message.content} from {message.author}")

    if message.content.__contains__("<@1468279695547044038>"):
        rng = random.randint(1, 3)
        match rng: 
            case 1: 
                await message.channel.send("hello")
            case 2:
                await message.channel.send("hi")
            case 3:
                await message.channel.send("What's up")

    author_id = message.author.id
    author_name = message.author.name

    if not message.content.startswith(":"):
        return

    if not ADMIN_IDs.__contains__(message.author.id):
        print("user is not an admin")
        return

    print(f"{author_name} has sent {message.content}")

    if message.content.startswith(f"{PREFIX}addUser"):
        try:
            parts = message.content.split(" ")
            if len(parts) != 3:
                await message.channel.send("Usage: `!test [id] [name]`")
                return

            new_id, new_name = parts[1], parts[2]
            data = get_current_gist()

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
            await message.channel.send(f"✅ Added {new_name} in Server Boosteres")
        except Exception as e:
            await message.channel.send(f"❌ Error: {str(e)}")




    if message.content.startswith(f"{PREFIX}dm"):
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