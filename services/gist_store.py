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

Every "file" this bot manages (data.json, manual.json, names.json,
moderators.json, ExternalBridge.json) actually lives inside ONE gist, so
any two writes anywhere in the bot are really writes to the same shared
resource. GitHub's Gist API returns 409 "Gist cannot be updated" if two
PATCH requests to the same gist land close together. _write_lock below
serializes every write through this module so that can't happen
regardless of which two callers collide — but the real fix for sustained
409s/503s is calling this module less often in the first place; see
cogs/booster_sync.py for the on_member_update debounce/narrowing that
actually addresses the call volume.
"""
import asyncio
import json

import aiohttp

from config import GIST_ID, GITHUB_TOKEN

_GIST_URL = f"https://api.github.com/gists/{GIST_ID}"
_HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}

_write_lock = asyncio.Lock()

# One shared session, reused for the life of the process, instead of a new
# TCP connection + TLS handshake per call. Created lazily since a
# ClientSession has to be built inside a running event loop.
_session: aiohttp.ClientSession | None = None


def _get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession()
    return _session


async def close_session() -> None:
    """Call on bot shutdown to close the pooled connection cleanly."""
    global _session
    if _session is not None and not _session.closed:
        await _session.close()
    _session = None


async def _fetch_gist() -> dict | None:
    try:
        session = _get_session()
        async with session.get(_GIST_URL, headers=_HEADERS) as resp:
            if resp.status != 200:
                print(f"[gist_store] GET failed fetching gist: HTTP {resp.status}")
                return None
            return await resp.json()
    except aiohttp.ClientError as e:
        print(f"[gist_store] GET network error: {e}")
        return None


async def get_file(filename: str, default=None):
    """Fetch and JSON-decode one file from the gist. Returns `default` on
    any failure (missing file, network error, bad JSON) instead of raising,
    since every caller in this bot treats a missing file as "start empty".

    Fetching more than one file at once? Use get_files() instead — each
    call here is a full GET of the whole gist, so two get_file() calls
    back to back is two redundant round trips for data that comes back in
    one response either way.
    """
    result = await get_files([filename], defaults={filename: default})
    return result[filename]


async def get_files(filenames: list[str], defaults: dict | None = None) -> dict:
    """Fetch several files from the gist in a single GET. Returns a dict
    keyed by filename; any file that's missing or fails to parse falls
    back to defaults.get(filename) (or None)."""
    defaults = defaults or {}
    payload = await _fetch_gist()
    if payload is None:
        return {name: defaults.get(name) for name in filenames}

    files = payload.get("files", {})
    result = {}
    for name in filenames:
        if name not in files:
            result[name] = defaults.get(name)
            continue
        try:
            result[name] = json.loads(files[name]["content"])
        except (KeyError, json.JSONDecodeError) as e:
            print(f"[gist_store] GET {name} had unparseable content: {e}")
            result[name] = defaults.get(name)
    return result


async def put_files(files: dict, *, max_attempts: int = 3) -> bool:
    """Write one or more files to the gist in a single PATCH request.
    `files` maps filename -> the Python object to JSON-encode.

    Serialized by _write_lock (see module docstring) and retried a couple
    times specifically on 409 ("Gist cannot be updated"), which is GitHub
    rejecting a write that landed while another one was still settling.
    """
    payload = {
        "files": {name: {"content": json.dumps(content, indent=2)} for name, content in files.items()}
    }

    async with _write_lock:
        for attempt in range(1, max_attempts + 1):
            try:
                session = _get_session()
                async with session.patch(_GIST_URL, headers=_HEADERS, json=payload) as resp:
                    if resp.status == 200:
                        return True

                    body = await resp.text()
                    if resp.status == 409 and attempt < max_attempts:
                        print(f"[gist_store] PATCH got 409 (conflict), retrying ({attempt}/{max_attempts})...")
                        await asyncio.sleep(0.5 * attempt)
                        continue

                    print(f"[gist_store] PATCH failed: HTTP {resp.status} {body}")
                    return False
            except aiohttp.ClientError as e:
                print(f"[gist_store] PATCH network error: {e}")
                return False

    return False


async def clear_file(filename: str) -> bool:
    """Reset a single gist file to an empty list."""
    return await put_files({filename: []})