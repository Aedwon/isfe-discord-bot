import discord
from discord.ext import commands
from discord import app_commands
from database.db import db
import logging

class Roles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="reaction_panel", description="Setup a reaction role panel.")
    @app_commands.describe(
        message_link="Link to the existing message to use as a panel",
        emoji="The emoji to react with",
        role="The role to give"
    )
    @commands.has_permissions(administrator=True)
    async def reaction_panel(self, interaction: discord.Interaction, message_link: str, emoji: str, role: discord.Role):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Parse message link
            parts = message_link.split("/")
            message_id = int(parts[-1])
            channel_id = int(parts[-2])
            
            channel = interaction.guild.get_channel(channel_id)
            if not channel:
                await interaction.followup.send("❌ Channel not found.", ephemeral=True)
                return
                
            try:
                message = await channel.fetch_message(message_id)
            except discord.NotFound:
                await interaction.followup.send(f"❌ Message not found.", ephemeral=True)
                return

            # Add reaction to message
            try:
                await message.add_reaction(emoji)
            except Exception as e:
                await interaction.followup.send(f"❌ Failed to add reaction: {e}. Is the emoji valid?", ephemeral=True)
                return

            # Save to DB
            query = """
                INSERT INTO reaction_roles (message_id, channel_id, guild_id, emoji, role_id)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE role_id = %s
            """
            await db.execute(query, (message_id, channel_id, interaction.guild.id, str(emoji), role.id, role.id))
            
            await interaction.followup.send(f"✅ Reaction role setup! Reacting with {emoji} gives {role.mention}.", ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)
            logging.error(f"Error setting up reaction panel: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.member.bot: return

        try:
            query = "SELECT role_id FROM reaction_roles WHERE message_id = %s AND emoji = %s"
            row = await db.fetchrow(query, (payload.message_id, str(payload.emoji)))
            
            if row:
                role_id = row['role_id']
                guild = self.bot.get_guild(payload.guild_id)
                if guild:
                    role = guild.get_role(role_id)
                    if role:
                        try:
                            await payload.member.add_roles(role)
                        except discord.Forbidden:
                            logging.warning(f"Missing permissions to add role {role.name} in guild {guild.name}")
        except Exception as e:
            logging.error(f"Error in reaction add: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        try:
            query = "SELECT role_id FROM reaction_roles WHERE message_id = %s AND emoji = %s"
            row = await db.fetchrow(query, (payload.message_id, str(payload.emoji)))
            
            if row:
                role_id = row['role_id']
                guild = self.bot.get_guild(payload.guild_id)
                if guild:
                    member = guild.get_member(payload.user_id)
                    if member and not member.bot:
                        role = guild.get_role(role_id)
                        if role:
                            try:
                                await member.remove_roles(role)
                            except discord.Forbidden:
                                logging.warning(f"Missing permissions to remove role {role.name} in guild {guild.name}")
        except Exception as e:
            logging.error(f"Error in reaction remove: {e}")

    @app_commands.command(name="setup_game_roles", description="Set up the specific Game Roles panel (MLBB, CODM, T8).")
    @app_commands.default_permissions(administrator=True)
    async def setup_game_roles(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        target_channel = channel or interaction.channel
        
        embed = discord.Embed(
            title="🎮 Game Roles Selection",
            description="Select your games to unlock their channels!",
            color=0x5865F2 # Blurple
        )
        embed.set_footer(text="System developed by Aedwon")

        # Define Buttons
        view = discord.ui.View(timeout=None)
        
        # MLBB
        view.add_item(discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="MLBB",
            emoji=discord.PartialEmoji.from_str("<:MLBB:1464908191790923883>"),
            custom_id="role:1464901284128751782"
        ))
        
        # CODM
        view.add_item(discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="CODM",
            emoji=discord.PartialEmoji.from_str("<:CODM:1464907894871822347>"),
            custom_id="role:1464901350130188436"
        ))

        # Tekken 8
        view.add_item(discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="Tekken 8",
            emoji=discord.PartialEmoji.from_str("<:TK8:1464908146538709064>"),
            custom_id="role:1464901497539133564"
        ))
        
        try:
            await target_channel.send(embed=embed, view=view)
            await interaction.response.send_message(f"✅ Game Roles panel created in {target_channel.mention}.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.component:
            return
            
        custom_id = interaction.data.get('custom_id', '')
        if not custom_id.startswith('role:'):
            return
            
        try:
            role_id = int(custom_id.split(':')[1])
            target_role = interaction.guild.get_role(role_id)
            
            if not target_role:
                await interaction.response.send_message("❌ Role not found.", ephemeral=True)
                return

            # Simple toggle for all roles (including game roles - users can have multiple)
            if target_role in interaction.user.roles:
                await interaction.user.remove_roles(target_role)
                await interaction.response.send_message(f"❌ Removed {target_role.mention}", ephemeral=True)
            else:
                await interaction.user.add_roles(target_role)
                await interaction.response.send_message(f"✅ Added {target_role.mention}", ephemeral=True)
                
        except discord.Forbidden:
            await interaction.response.send_message("❌ Bot missing permissions to manage roles.", ephemeral=True)
        except Exception as e:
            logging.error(f"Button Role Error: {e}")
            try:
                await interaction.response.send_message("❌ An error occurred.", ephemeral=True)
            except: pass

async def setup(bot):
    await bot.add_cog(Roles(bot))
