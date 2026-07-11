"""
Loads every cog into a real Bot instance without connecting to Discord —
catches import errors, decorator mistakes, and registration problems
(e.g. two commands with the same name) in about a second, without needing
a real token. Handy after adding a new cog: `python smoke_test.py`.
"""
import asyncio
import os

os.environ.setdefault("DISCORD_TOKEN", "test-token")
os.environ.setdefault("ROBLOX_API_KEY", "test-key")
os.environ.setdefault("GITHUB_TOKEN", "test-token")
os.environ.setdefault("GIST_ID", "test-gist-id")

import discord
from discord.ext import commands

import config
from main import COGS


async def main():
    config.validate()
    print("config.validate() passed\n")

    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True
    bot = commands.Bot(command_prefix="!", intents=intents)

    for ext in COGS:
        await bot.load_extension(ext)
        print(f"loaded {ext}")

    print("\nRegistered application commands:")

    def describe(cmd, indent=0):
        prefix = "  " * indent
        if isinstance(cmd, discord.app_commands.Group):
            print(f"{prefix}/{cmd.name}  [group]  installs={cmd.allowed_installs}  contexts={cmd.allowed_contexts}")
            for sub in cmd.commands:
                describe(sub, indent + 1)
        else:
            checks = [c.__qualname__.split('.')[0] for c in cmd.checks]
            print(f"{prefix}/{cmd.qualified_name}  checks={checks}  binding={type(cmd.binding).__name__}")

    for cmd in bot.tree.get_commands():
        describe(cmd)

    print("\nListeners registered:")
    for name, funcs in bot.extra_events.items():
        print(f"  {name}: {len(funcs)} handler(s)")

    print("\nAll good.")


asyncio.run(main())
