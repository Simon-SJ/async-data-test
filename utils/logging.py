"""Shared helper for posting moderation-action embeds to the staff log channel."""
import discord

from config import LOG_CHANNEL_ID


async def log_action(
    client: discord.Client,
    title: str,
    description: str,
    color: discord.Color = discord.Color.blue(),
) -> None:
    channel = client.get_channel(LOG_CHANNEL_ID)
    if channel is None:
        print(f"[log_action] Could not find log channel {LOG_CHANNEL_ID}")
        return

    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=discord.utils.utcnow(),
    )

    # A logging hiccup should never take down the command that triggered
    # it — the moderation action itself (ban/unban/blacklist/etc.) already
    # happened by the time this runs. Without this, a permissions problem
    # here surfaces as a scary generic error on a command that actually
    # succeeded, instead of just a console warning.
    try:
        await channel.send(embed=embed)
    except discord.Forbidden:
        print(f"[log_action] Missing access to log channel {LOG_CHANNEL_ID} — check the bot's permissions there.")
    except discord.HTTPException as e:
        print(f"[log_action] Failed to send log message: {e}")
    else:
        print(f"[log_action] Posted '{title}' to log channel {LOG_CHANNEL_ID}.")