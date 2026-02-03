import requests
import os

TOKEN = os.getenv("DISCORD_TOKEN")
GIST_ID = os.getenv("GIST_ID")

def update_roblox_data(new_content):
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    data = {
        "files": {
            "data.json": {"content": new_content}
        }
    }
    response = requests.patch(url, headers=headers, json=data)
    return response.status_code == 200