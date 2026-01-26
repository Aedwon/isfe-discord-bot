import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import pytz
import traceback
import base64
import json
from urllib.parse import urlparse, parse_qs, quote
from io import BytesIO
from utils.views import ConfirmView
import datetime

from utils.constants import MCC_PROD_ROLE_ID, MCC_PROD_CATEGORY_IDS

PREDEFINED_MESSAGE_LINK = "https://discord.com/channels/1170027365091508324/1170646801938923662/1382277195237560351"  # Replace with your actual message link

class Misc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="List all available commands and their descriptions.")
    async def help_command(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🤖 Bot Commands", description="Here are the available commands:", color=discord.Color.blue())
        for command in interaction.client.tree.get_commands():
            embed.add_field(name=f"/{command.name}", value=command.description or "No description", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="list", description="List members of a specified role in lexicographical order.")
    @app_commands.describe(role="Select a role to list its members")
    async def list(self, interaction: discord.Interaction, role: discord.Role):
        await interaction.response.defer(ephemeral=True)
        members = sorted(role.members, key=lambda x: x.display_name)
        if not members:
            await interaction.followup.send(f"❌ No members found for role **{role.name}**.", ephemeral=True)
            return
        member_list = '\n'.join([member.display_name for member in members])
        if len(member_list) > 4096:
            await interaction.followup.send(f"📜 **{role.name} Members (Lexicographical Order):**\n```{member_list}```", ephemeral=True)
        else:
            embed = discord.Embed(title=f"📜 {role.name} Members (Lexicographical Order)", color=discord.Color.gold())
            embed.description = f"```{member_list}```"
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="timestamp", description="Generate Discord timestamps from a given date and time (DD/MM/YYYY HH:MM).")
    @app_commands.describe(datetime_str="Enter the date and time in DD/MM/YYYY HH:MM (24-hr) format.")
    async def timestamp(self, interaction: discord.Interaction, datetime_str: str):
        try:
            dt = datetime.strptime(datetime_str, "%d/%m/%Y %H:%M")
            unix_timestamp = int(dt.replace(tzinfo=pytz.UTC).timestamp())
            timestamp_str = f"<t:{unix_timestamp}:F>"
            embed = discord.Embed(title="🕒 Discord Timestamp", color=discord.Color.purple())
            embed.add_field(name="Input", value=f"`{datetime_str}`", inline=False)
            embed.add_field(name="Timestamp", value=f"{timestamp_str}", inline=False)
            embed.add_field(name="Preview", value=timestamp_str, inline=False)
            await interaction.response.send_message(embed=embed)
        except ValueError:
            await interaction.response.send_message("❌ Incorrect date format. Please use **DD/MM/YYYY HH:MM**.", ephemeral=True)
        except Exception as e:
            traceback.print_exc()
            await interaction.response.send_message(
                f"❌ An unexpected error occurred: `{str(e)}`", ephemeral=True
            )

    @app_commands.command(name="createthreads", description="Create private threads with specific roles.")
    @app_commands.describe(
        names="Thread names separated by commas",
        roles="Mention roles or provide role IDs (comma-separated) who can access the threads"
    )
    async def create_threads(self, interaction: discord.Interaction, names: str, roles: str):
        await interaction.response.defer()
        if not interaction.channel or not isinstance(interaction.channel, discord.TextChannel):
            return await interaction.followup.send("❌ This command can only be used in text channels.", ephemeral=True)
        thread_names = [name.strip() for name in names.split(",") if name.strip()]
        if not thread_names:
            return await interaction.followup.send("❌ Please provide at least one thread name.", ephemeral=True)
        role_ids = set()
        for role_str in roles.split(","):
            role_str = role_str.strip()
            if role_str.startswith("<@&") and role_str.endswith(">"):
                role_id = int(role_str[3:-1])
                role_ids.add(role_id)
            elif role_str.isdigit():
                role_ids.add(int(role_str))
        if not role_ids:
            return await interaction.followup.send("❌ Please provide at least one valid role mention or ID.", ephemeral=True)
        created_threads = []
        trimmed_threads = []
        for name in thread_names:
            original_name = name
            if len(name) > 100:
                name = name[:100]
                trimmed_threads.append((original_name, name))
            try:
                thread = await interaction.channel.create_thread(
                    name=name,
                    type=discord.ChannelType.private_thread,
                    invitable=True
                )
                await thread.add_user(interaction.user)
                for role_id in role_ids:
                    role = interaction.guild.get_role(role_id)
                    if role:
                        await thread.send(f"{role.mention} has access to this thread.")
                created_threads.append(f"- {thread.mention}")
            except Exception as e:
                return await interaction.followup.send(f"❌ Failed to create a thread: {e}", ephemeral=True)
        response_msg = "✅ **Created Threads:**\n" + "\n".join(created_threads)
        if trimmed_threads:
            response_msg += "\n⚠️ **Some thread names were too long and were trimmed:**"
            for original, trimmed in trimmed_threads:
                response_msg += f"\n- `{original}` → `{trimmed}`"
        await interaction.followup.send(response_msg, ephemeral=True)

    @app_commands.command(name="remind", description="Send the content of a predefined message to this channel.")
    async def remind(self, interaction: discord.Interaction):
        """Fetches and resends the content of a predefined message."""
        try:
            parts = PREDEFINED_MESSAGE_LINK.strip().split("/")
            if len(parts) < 7:
                await interaction.response.send_message("❌ Invalid message link format.", ephemeral=True)
                return
            channel_id = int(parts[-2])
            message_id = int(parts[-1])
            channel = interaction.client.get_channel(channel_id) or await interaction.client.fetch_channel(channel_id)
            message = await channel.fetch_message(message_id)
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Could not fetch the predefined message: `{e}`",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            message.content,
            allowed_mentions=discord.AllowedMentions.none()
        )

    @commands.command(name="mccprod")
    async def mccprod(self, ctx):
        """Give MCC Production Team role and ping in all prod categories (auto-deletes pings)."""
        guild = ctx.guild
        member = ctx.author

        # Give the role
        role = guild.get_role(MCC_PROD_ROLE_ID)
        if role and role not in member.roles:
            try:
                await member.add_roles(role, reason="MCC Production Team self-assign")
            except discord.Forbidden:
                await ctx.send("❌ I don't have permission to assign the MCC Production Team role.", delete_after=5)
                return

        # Mention in all text channels in the specified categories
        for cat_id in MCC_PROD_CATEGORY_IDS:
            category = guild.get_channel(cat_id)
            if category and isinstance(category, discord.CategoryChannel):
                for channel in category.text_channels:
                    try:
                        msg = await channel.send(f"{member.mention}")
                        await asyncio.sleep(2)
                        await msg.delete()
                    except Exception:
                        continue  # Ignore errors (e.g., missing perms)

        await ctx.send("✅ MCC Production Team role given and pings sent (auto-deleted).", delete_after=5)

async def setup(bot):
    await bot.add_cog(Misc(bot))