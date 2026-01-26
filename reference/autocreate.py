import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import json
import os

AUTOCREATE_FILE = "data/autocreate_channels.json"

def load_autocreate_channels():
    # Ensure the data folder exists
    os.makedirs(os.path.dirname(AUTOCREATE_FILE), exist_ok=True)
    # If the file doesn't exist, create it with an empty list
    if not os.path.exists(AUTOCREATE_FILE):
        with open(AUTOCREATE_FILE, "w") as f:
            json.dump([], f)
        return set()
    with open(AUTOCREATE_FILE, "r") as f:
        return set(json.load(f))

def save_autocreate_channels(channel_ids):
    with open(AUTOCREATE_FILE, "w") as f:
        json.dump(list(channel_ids), f)

class AutoCreate(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.autocreate_channel_ids = load_autocreate_channels()

    @app_commands.command(name="autocreate", description="Create an autocreate voice channel that duplicates when joined.")
    @app_commands.describe(
        category="The category to create the base voice channel in",
        name="Name of the autocreate voice channel"
    )
    @commands.has_permissions(administrator=True)
    async def autocreate(self, interaction: discord.Interaction, category: discord.CategoryChannel, name: str):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        vc_channel = await guild.create_voice_channel(name, category=category)
        self.autocreate_channel_ids.add(vc_channel.id)
        save_autocreate_channels(self.autocreate_channel_ids)
        await interaction.followup.send(
            f"✅ Created autocreate voice channel: {vc_channel.mention}. Users who join will get their own temporary VC.",
            ephemeral=True
        )

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # Only act if user joined a channel
        if after.channel and after.channel.id in self.autocreate_channel_ids:
            guild = after.channel.guild
            category = after.channel.category
            # Create a new temp channel
            temp_channel = await guild.create_voice_channel(
                name=f"{member.display_name}'s Channel",
                category=category,
                overwrites=after.channel.overwrites
            )
            await member.move_to(temp_channel)

            # Optionally, delete the temp channel when empty
            async def delete_when_empty():
                await self.bot.wait_until_ready()
                while True:
                    await asyncio.sleep(10)
                    if len(temp_channel.members) == 0:
                        await temp_channel.delete()
                        break
            self.bot.loop.create_task(delete_when_empty())

async def setup(bot):
    await bot.add_cog(AutoCreate(bot))