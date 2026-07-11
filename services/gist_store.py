"""
Thin async wrapper around the GitHub Gist used as the bot's persistence
layer (booster lists, name overrides, the moon-command queue).

The original bot's sync_and_publish() had already been fixed to avoid
blocking calls, but the helpers it called underneath — get_gist_file,
push_all_to_gist, clear_external_bridge, add_command_to_queue — still
used the synchronous `requests` library from inside async command
handlers, which blocks the whole bot's event loop for the duration of
every Gist read/write. Centralizing everything here on aiohttp fixes
that everywhere at once instead of one call site at a time.
"""
import json
import aiohttp
from config import GIST_ID, GITHUB_TOKEN

_GIST_URL = f"https://api.github.com/gists/{GIST_ID}"
_HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}


async def get_file(filename: str, default=None):
    """Fetch and JSON-decode one file from the gist. Returns `default` on
    any failure (missing file, network error, bad JSON) instead of raising,
    since every caller in this bot treats a missing file as "start empty"."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(_GIST_URL, headers=_HEADERS) as resp:
                if resp.status != 200:
                    print(f"[gist_store] GET failed fetching gist: HTTP {resp.status}")
                    return default
                payload = await resp.json()
    except aiohttp.ClientError as e:
        print(f"[gist_store] GET network error: {e}")
        return default

    files = payload.get("files", {})
    if filename not in files:
        return default

    try:
        return json.loads(files[filename]["content"])
    except (KeyError, json.JSONDecodeError) as e:
        print(f"[gist_store] GET {filename} had unparseable content: {e}")
        return default


async def put_files(files: dict) -> bool:
    """Write one or more files to the gist in a single PATCH request.
    Retries automatically on HTTP 409 Conflict errors.
    """
    payload = {
        "files": {name: {"content": json.dumps(content, indent=2)} for name, content in files.items()}
    }
    
    max_retries = 3
    base_delay = 1.0

    for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.patch(_GIST_URL, headers=_HEADERS, json=payload) as resp:
                        if resp.status == 200:
                            return True
                        
                        body = await resp.text()
                        
                        if resp.status == 409:
                            print(f"[gist_store] PATCH conflict (409) on attempt {attempt + 1}. Retrying...")
                            continue
                            
                        print(f"[gist_store] PATCH failed: HTTP {resp.status} {body}")
                        return False
                        
            except aiohttp.ClientError as e:
                print(f"[gist_store] PATCH network error: {e}")
                return False
                
    print("[gist_store] PATCH failed after maximum retries due to persistent 409 Conflict.")
    return False


async def clear_file(filename: str) -> bool:
    """Reset a single gist file to an empty list."""
    return await put_files({filename: []})
