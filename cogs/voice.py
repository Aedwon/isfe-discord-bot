import discord
from discord.ext import commands
from discord import app_commands
from database.db import db
import asyncio
import logging

class Voice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="autocreate_setup", description="Setup a voice channel that duplicates when joined.")
    @app_commands.describe(channel="The master voice channel to use")
    @commands.has_permissions(administrator=True)
    async def autocreate_setup(self, interaction: discord.Interaction, channel: discord.VoiceChannel):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Upsert
            query = """
                INSERT INTO autocreate_configs (voice_channel_id, category_id)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE category_id = %s
            """
            await db.execute(query, (channel.id, channel.category_id if channel.category else None, channel.category_id if channel.category else None))
            
            await interaction.followup.send(f"✅ Setup complete: {channel.mention} is now an Autocreate channel.", ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # 1. Check if Joined a Master Channel
        if after.channel:
            try:
                row = await db.fetchrow("SELECT category_id FROM autocreate_configs WHERE voice_channel_id = %s", (after.channel.id,))
                if row:
                    # Create Temp Channel
                    guild = member.guild
                    category = guild.get_channel(row['category_id']) if row['category_id'] else after.channel.category
                    
                    overwrites = after.channel.overwrites
                    # Ensure user has perms
                    overwrites[member] = discord.PermissionOverwrite(manage_channels=True, move_members=True)
                    
                    temp_channel = await guild.create_voice_channel(
                        name=f"{member.display_name}'s VC",
                        category=category,
                        overwrites=overwrites
                    )
                    
                    # Move member
                    await member.move_to(temp_channel)
                    
                    # Start cleanup monitoring for this channel
                    self.bot.loop.create_task(self.check_empty_channel(temp_channel))
            except Exception as e:
                logging.error(f"Error in autocreate voice: {e}")

        # 2. Cleanup (Optional: if we rely on loop below, this is redundant but good for immediate cleanup)
        # Actually logic handled by the specific task spawned, or we can check 'before.channel' here.
        # Spawning a task per channel is fine for moderate usage.
        
    async def check_empty_channel(self, channel):
        """Monitors a temp channel and deletes it when empty."""
        try:
            while True:
                await asyncio.sleep(10) # check every 10s
                
                # Refresh channel state
                try:
                    # fetch not needed if we rely on cache updates, but safe
                    if len(channel.members) == 0:
                        await channel.delete()
                        break
                except discord.NotFound:
                    break # Already deleted
                except Exception:
                    pass
        except Exception as e:
            logging.error(f"Error monitoring temp channel {channel.id}: {e}")

async def setup(bot):
    await bot.add_cog(Voice(bot))
