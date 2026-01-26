import discord
from discord.ext import commands
from discord import app_commands
from database.db import db
import asyncio
import logging

class Voice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_cache = {} # {voice_channel_id: category_id}
        self.temp_channels = set() # {channel_id}

    async def cog_load(self):
        # Load configs into cache
        try:
            rows = await db.fetchall("SELECT voice_channel_id, category_id FROM autocreate_configs")
            for row in rows:
                self.config_cache[row['voice_channel_id']] = row['category_id']
            logging.info(f"Loaded {len(self.config_cache)} autocreate configs.")
        except Exception as e:
            logging.error(f"Failed to load autocreate configs: {e}")

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
            
            # Update Cache
            self.config_cache[channel.id] = channel.category_id if channel.category else None
            
            await interaction.followup.send(f"✅ Setup complete: {channel.mention} is now an Autocreate channel.", ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # 1. Check if Joined a Master Channel
        if after.channel and after.channel.id in self.config_cache:
            try:
                # Use Cache
                category_id = self.config_cache[after.channel.id]
                guild = member.guild
                
                category = None
                if category_id:
                    category = guild.get_channel(category_id)
                if not category:
                    category = after.channel.category
                
                overwrites = after.channel.overwrites
                # Ensure user has perms
                overwrites[member] = discord.PermissionOverwrite(manage_channels=True, move_members=True)
                
                temp_channel = await guild.create_voice_channel(
                    name=f"{member.display_name}'s VC",
                    category=category,
                    overwrites=overwrites
                )
                
                self.temp_channels.add(temp_channel.id)
                
                # Move member
                await member.move_to(temp_channel)

            except Exception as e:
                logging.error(f"Error in autocreate voice: {e}")

        # 2. Cleanup: Event-based Immediate Deletion
        if before.channel and before.channel.id in self.temp_channels:
             if len(before.channel.members) == 0:
                 try:
                     await before.channel.delete()
                     self.temp_channels.remove(before.channel.id)
                 except discord.NotFound:
                     self.temp_channels.discard(before.channel.id)
                 except discord.HTTPException as e:
                     if e.status == 429: # Rate Limited
                         logging.warning(f"Rate limited on channel delete. Retrying in {e.retry_after}s")
                         await asyncio.sleep(e.retry_after)
                         try:
                             await before.channel.delete()
                             self.temp_channels.remove(before.channel.id)
                         except: pass
                     else:
                        logging.error(f"Failed to delete channel: {e}")

async def setup(bot):
    await bot.add_cog(Voice(bot))
