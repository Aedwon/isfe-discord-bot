from discord.ext import commands
from discord import app_commands
import discord
import asyncio

# Import ConfirmView and any other helpers you use
from utils.views import ConfirmView
from utils.views import NicknameResetConfirmView

from utils.constants import DM_SENT_LOG_CHANNEL_ID  # Replace with your actual log channel ID

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def ping(self, ctx):
        """Simple ping command."""
        await ctx.send("Pong!")

    @app_commands.command(name="dm", description="Send a direct message to a user")
    @app_commands.describe(user="The user to message", message="The message content", attachment="Optional attachment to send")
    @commands.has_permissions(administrator=True)
    async def dm(self, interaction: discord.Interaction, user: discord.User, message: str, attachment: discord.Attachment = None):
        await interaction.response.defer(ephemeral=True)
        
        description = f"Are you sure you want to send the following message to {user.mention}?\n\n```{message}```"
        if attachment:
            description += f"\n\n**Attachment:** `{attachment.filename}`"

        embed = discord.Embed(
            title="📩 Confirmation",
            description=description,
            color=0x3498DB
        )
        
        if attachment and attachment.content_type and attachment.content_type.startswith('image/'):
            embed.set_thumbnail(url=attachment.url)

        view = ConfirmView(
            interaction=interaction,
            on_confirm=self.send_dm,
            confirm_args=(interaction, user, message, attachment)
        )
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    async def send_dm(self, interaction: discord.Interaction, user: discord.User, message: str, attachment: discord.Attachment = None):
        """Function to send a DM"""
        try:
            file = await attachment.to_file() if attachment else None
            await user.send(f"{message}\n\n- MCC Team", file=file)
            
            embed = discord.Embed(title="✅ DM Sent", color=0x3498DB)
            embed.add_field(name="Recipient", value=user.mention, inline=True)
            embed.add_field(name="Sent By", value=interaction.user.mention, inline=True)
            embed.add_field(name="Message Content", value=message, inline=False)
            if attachment:
                embed.add_field(name="Attachment", value=f"[{attachment.filename}]({attachment.url})", inline=False)
            
            await interaction.followup.send(embed=embed, ephemeral=True)  # Confirmation only

            # --- Channel log ---
            log_channel = interaction.guild.get_channel(DM_SENT_LOG_CHANNEL_ID)  # Replace with your log channel ID
            if log_channel:
                log_embed = discord.Embed(title="📨 DM Sent", color=0x3498DB)
                log_embed.add_field(name="Sender", value=interaction.user.mention, inline=True)
                log_embed.add_field(name="Recipient", value=user.mention, inline=True)
                log_embed.add_field(name="Message", value=message, inline=False)
                
                if attachment:
                    log_embed.add_field(name="Attachment", value=f"[{attachment.filename}]({attachment.url})", inline=False)
                    if attachment.content_type and attachment.content_type.startswith('image/'):
                        log_embed.set_image(url=attachment.url)

                await log_channel.send(embed=log_embed)
        except discord.Forbidden:
            await interaction.followup.send(f"❌ Could not send DM to {user.mention}.", ephemeral=True)

    @app_commands.command(
        name="purge_role",
        description="Remove a role from all members. Optionally reset their nicknames."
    )
    @app_commands.describe(
        role="The role to purge from all members",
        reset_nicknames="Also reset nicknames? (default: False)"
    )
    @commands.has_permissions(administrator=True)
    async def purge_role(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        reset_nicknames: bool = False  # Default is now False
    ):
        await interaction.response.defer(ephemeral=True)
        count = 0
        for member in interaction.guild.members:
            if role in member.roles:
                try:
                    await member.remove_roles(role)
                    if reset_nicknames:
                        await member.edit(nick=None)
                    count += 1
                except discord.Forbidden:
                    continue
        msg = f"✅ Removed {role.mention} from {count} members"
        if reset_nicknames:
            msg += " and reset their nicknames."
        else:
            msg += "."
        await interaction.followup.send(msg, ephemeral=True)

    @app_commands.command(name="purge_channel", description="Delete all messages in this channel.")
    @commands.has_permissions(administrator=True)
    async def purge_channel(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not isinstance(interaction.channel, discord.TextChannel):
            return await interaction.followup.send("❌ This command can only be used in text channels.", ephemeral=True)
        await interaction.channel.purge()
        await interaction.followup.send("✅ Channel purged.", ephemeral=True)

    @app_commands.command(name="reset_nicknames_specify", description="Reset nicknames of users whose nicknames contain a specified string.")
    @app_commands.describe(query="The string to search for in nicknames")
    @commands.has_permissions(administrator=True)
    async def reset_nicknames_specify(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer(ephemeral=True)
        affected_members = [member for member in interaction.guild.members if member.nick and query.lower() in member.nick.lower()]
        if not affected_members:
            return await interaction.followup.send(f"❌ No members found with `{query}` in their nickname.", ephemeral=True)
        # Generate the list of affected users
        member_list = "\n".join([f"- {member.mention} ({member.nick})" for member in affected_members[:20]])
        remaining = len(affected_members) - 20
        embed = discord.Embed(
            title="🔄 Nicknames to Reset",
            description=f"These users have `{query}` in their nickname:\n\n{member_list}" + (f"\n\n...and {remaining} more." if remaining > 0 else ""),
            color=discord.Color.gold()
        )
        embed.set_footer(text="Confirm to reset all nicknames.")
        view = NicknameResetConfirmView(interaction, affected_members, query, self.confirm_reset_nicknames)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    async def confirm_reset_nicknames(self, interaction: discord.Interaction, affected_members: list, query: str):
        reset_count = 0
        for member in affected_members:
            try:
                await member.edit(nick=None)
                reset_count += 1
            except discord.Forbidden:
                continue
        if reset_count == 0:
            return await interaction.followup.send(f"❌ The bot lacks permissions to reset any nicknames.", ephemeral=True)
        embed = discord.Embed(
            title="✅ Nicknames Reset",
            description=f"Successfully reset `{reset_count}` nicknames containing `{query}`.",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        log_embed = discord.Embed(
            title="🔄 Nicknames Reset Log",
            description=f"**Admin:** {interaction.user.mention}\nReset `{reset_count}` nicknames containing `{query}`.",
            color=discord.Color.blue()
        )
        log_channel = interaction.guild.get_channel(1176846607203962960)  # Update with your log channel ID
        if log_channel:
            await log_channel.send(embed=log_embed)
        else:
            await interaction.channel.send(embed=log_embed)

    @app_commands.command(name="reset_all_nicknames", description="Reset all members' nicknames (except admins).")
    @commands.has_permissions(manage_nicknames=True)
    async def reset_all_nicknames(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        count = 0
        for member in interaction.guild.members:
            if not member.guild_permissions.administrator:
                try:
                    await member.edit(nick=None)
                    count += 1
                except discord.Forbidden:
                    continue
        await interaction.followup.send(f"✅ Reset nicknames for {count} members.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Admin(bot))