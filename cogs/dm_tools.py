"""/dm send, plus forwarding incoming DMs/group DMs to a staff log channel."""
import discord
from discord import app_commands
from discord.ext import commands

from config import DM_FORWARD_CHANNEL_ID
from utils.install_contexts import EVERYWHERE_CONTEXTS, EVERYWHERE_INSTALLS
from utils.permissions import require_admin


class DmTools(commands.Cog):
    dm_group = app_commands.Group(
        name="dm",
        description="DM tools",
        allowed_installs=EVERYWHERE_INSTALLS,
        allowed_contexts=EVERYWHERE_CONTEXTS,
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user:
            return
        if message.guild is not None:
            return  # only forward DMs / group DMs

        channel = self.bot.get_channel(DM_FORWARD_CHANNEL_ID)
        if channel is None:
            return

        embed = discord.Embed(
            title="New Direct Message",
            description=message.content or "*[no text content]*",
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
        embed.add_field(name="User ID", value=message.author.id, inline=True)
        embed.add_field(name="Reply", value=f"`/dm send {message.author.id}`", inline=True)

        if message.attachments:
            embed.add_field(name="Attachments", value="\n".join(a.url for a in message.attachments), inline=False)

        await channel.send(embed=embed)

    @dm_group.command(name="send", description="Send a DM to a user by username or ID")
    @app_commands.describe(target="Discord username or user ID", message="The message to send")
    @require_admin()
    async def send_dm(self, interaction: discord.Interaction, target: str, message: str):
        await interaction.response.defer()

        if target.isdigit():
            try:
                user = await self.bot.fetch_user(int(target))
            except discord.NotFound:
                await interaction.followup.send(f"❌ No user found with ID `{target}`.", ephemeral=True)
                return
        else:
            user = self._find_member_by_name(target)
            if user is None:
                await interaction.followup.send(
                    f"❌ No member found with username `{target}`. "
                    "Note: username search only works for members in shared servers.",
                    ephemeral=True,
                )
                return

        try:
            await user.send(message)
            await interaction.followup.send(f"✅ DM sent to `{user}` (`{user.id}`).")
        except discord.Forbidden:
            await interaction.followup.send(f"❌ Couldn't DM `{user}` — they may have DMs disabled.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ Error: `{e}`", ephemeral=True)

    def _find_member_by_name(self, target: str) -> discord.Member | None:
        target_lower = target.lower().lstrip("@")
        for guild in self.bot.guilds:
            for member in guild.members:
                if member.name.lower() == target_lower or member.display_name.lower() == target_lower:
                    return member
        return None


async def setup(bot: commands.Bot):
    await bot.add_cog(DmTools(bot))
