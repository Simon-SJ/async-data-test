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
scans every guild listed in config.ADMIN_ROLES_BY_GUILD /
EA_ROLES_BY_GUILD — regardless of where the command was invoked from —
so it works the same whether someone runs it in a server, a DM, or a
group DM, and now also across more than one staff server. main.py's
global error handler turns a failed check into the same "No permission."
reply.
"""
import discord
from discord import app_commands

from config import ADMIN_IDS, ADMIN_ROLES_BY_GUILD, EA_ROLES_BY_GUILD


async def _has_role_in_any_guild(client: discord.Client, user: discord.abc.User, roles_by_guild: dict) -> bool:
    """Check every (guild_id -> role_ids) entry until one grants access."""
    for guild_id, role_ids in roles_by_guild.items():
        guild = client.get_guild(guild_id)
        if guild is None:
            continue

        member = guild.get_member(user.id)
        if member is None:
            try:
                member = await guild.fetch_member(user.id)
            except (discord.NotFound, discord.HTTPException):
                continue

        if any(role.id in role_ids for role in member.roles):
            return True

    return False


async def is_admin(client: discord.Client, user: discord.abc.User) -> bool:
    if user.id in ADMIN_IDS:
        return True
    return await _has_role_in_any_guild(client, user, ADMIN_ROLES_BY_GUILD)


async def is_ea_suspension_mod(client: discord.Client, user: discord.abc.User) -> bool:
    if user.id in ADMIN_IDS:
        return True
    return await _has_role_in_any_guild(client, user, EA_ROLES_BY_GUILD)


def require_admin():
    async def predicate(interaction: discord.Interaction) -> bool:
        return await is_admin(interaction.client, interaction.user)

    return app_commands.check(predicate)


def require_ea_mod():
    async def predicate(interaction: discord.Interaction) -> bool:
        return await is_ea_suspension_mod(interaction.client, interaction.user)

    return app_commands.check(predicate)