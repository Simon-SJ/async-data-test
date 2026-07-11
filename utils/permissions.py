"""
Permission checks, centralized.

The old bot repeated this at the top of ~15 commands:

    if not IsAdmin(interaction.user):
        await interaction.response.send_message("No permission.", ephemeral=True)
        return

`interaction.user.roles` also only exists on a discord.Member, so that
pattern would crash outright if a command was ever invoked somewhere
without guild context (a DM, a group DM). Every command here uses
@require_admin() / @require_ea_mod() instead, and the actual role check
always resolves membership in the home guild — regardless of where the
command was invoked from — so it works the same whether someone runs it
in the server, in a DM, or (once installed) a group DM. main.py's global
error handler turns a failed check into the same "No permission." reply.
"""
import discord
from discord import app_commands

from config import ADMIN_IDS, EA_SUSPENSION_ROLE_IDS, HOME_GUILD_ID, MODERATOR_ROLE_IDS


async def _resolve_home_member(client: discord.Client, user: discord.abc.User) -> discord.Member | None:
    """Look up `user` as a Member of the home guild, regardless of where
    the interaction actually happened."""
    home_guild = client.get_guild(HOME_GUILD_ID)
    if home_guild is None:
        return None

    member = home_guild.get_member(user.id)
    if member is not None:
        return member

    try:
        return await home_guild.fetch_member(user.id)
    except (discord.NotFound, discord.HTTPException):
        return None


async def is_admin(client: discord.Client, user: discord.abc.User) -> bool:
    if user.id in ADMIN_IDS:
        return True
    member = await _resolve_home_member(client, user)
    return member is not None and any(role.id in MODERATOR_ROLE_IDS for role in member.roles)


async def is_ea_suspension_mod(client: discord.Client, user: discord.abc.User) -> bool:
    if user.id in ADMIN_IDS:
        return True
    member = await _resolve_home_member(client, user)
    return member is not None and any(role.id in EA_SUSPENSION_ROLE_IDS for role in member.roles)


def require_admin():
    async def predicate(interaction: discord.Interaction) -> bool:
        return await is_admin(interaction.client, interaction.user)

    return app_commands.check(predicate)


def require_ea_mod():
    async def predicate(interaction: discord.Interaction) -> bool:
        return await is_ea_suspension_mod(interaction.client, interaction.user)

    return app_commands.check(predicate)
