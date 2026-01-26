import discord
from discord.ext import commands
from discord import app_commands
from database.db import db
import logging
import datetime

class AdminLogs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="set_log_channel", description="Set the channel for bot command logs.")
    @app_commands.describe(channel="The channel to send command logs to")
    @commands.has_permissions(administrator=True)
    async def set_log_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Upsert into guild_settings
            query = """
                INSERT INTO guild_settings (guild_id, log_channel_id)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE log_channel_id = %s
            """
            await db.execute(query, (interaction.guild.id, channel.id, channel.id))
            
            await interaction.followup.send(f"✅ Command logs will now be sent to {channel.mention}.", ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to save setting: {e}", ephemeral=True)
            logging.error(f"Error setting log channel: {e}")

    @commands.Cog.listener()
    async def on_app_command_completion(self, interaction: discord.Interaction, command: app_commands.Command):
        """Logs every successful slash command execution."""
        try:
            # 1. Log to Database (Audit Trail)
            args_str = str(interaction.data.get('options', ''))
            
            log_query = """
                INSERT INTO command_logs (user_id, guild_id, channel_id, command_name, args)
                VALUES (%s, %s, %s, %s, %s)
            """
            await db.execute(log_query, (
                interaction.user.id,
                interaction.guild.id,
                interaction.channel_id,
                command.name,
                args_str
            ))

            # 2. Log to Discord Channel (if configured)
            settings_query = "SELECT log_channel_id FROM guild_settings WHERE guild_id = %s"
            row = await db.fetchrow(settings_query, (interaction.guild.id,))
            
            if row and row['log_channel_id']:
                log_channel = interaction.guild.get_channel(row['log_channel_id'])
                if log_channel:
                    embed = discord.Embed(
                        title="🤖 Command Executed",
                        description=f"**Command:** `/{command.name}`",
                        color=0x3498DB,
                        timestamp=datetime.datetime.now()
                    )
                    embed.set_author(name=f"{interaction.user} ({interaction.user.id})", icon_url=interaction.user.display_avatar.url)
                    embed.add_field(name="Channel", value=interaction.channel.mention, inline=True)
                    embed.add_field(name="Args", value=f"```{args_str}```", inline=False)
                    
                    try:
                        await log_channel.send(embed=embed)
                    except discord.Forbidden:
                        pass # Can't send to log channel
                    except Exception as e:
                        logging.error(f"Failed to send log embed: {e}")

        except Exception as e:
            logging.error(f"Error in on_app_command_completion: {e}")

async def setup(bot):
    await bot.add_cog(AdminLogs(bot))
