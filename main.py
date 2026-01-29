import discord
from discord.ext import commands
import os
import logging
from dotenv import load_dotenv
from database.db import db
from datetime import datetime
import traceback

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bot")

load_dotenv()

class ISFEBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.reactions = True
        intents.voice_states = True
        
        super().__init__(
            command_prefix="^",
            intents=intents,
            help_command=None,
            application_id=os.getenv("APP_ID")
        )

    async def setup_hook(self):
        # Connect Database
        await db.connect()
        await db.initialize_schema() # Ensure tables exist

        # Load Cogs
        initial_extensions = [
            "cogs.tickets",
            "cogs.roles",     # To be implemented
            "cogs.threads",   # To be implemented
            "cogs.embeds",    # To be implemented
            "cogs.voice",     # To be implemented
            "cogs.admin_logs", # New Feature 0
            "cogs.verification", # Player verification system
            "cogs.help"  # Help command
        ]
        
        for ext in initial_extensions:
            try:
                await self.load_extension(ext)
                logger.info(f"Loaded extension: {ext}")
            except Exception as e:
                logger.error(f"Failed to load extension {ext}: {e}")
                traceback.print_exc()

        # Sync Command Tree
        # Note: In production, sync specific guild or global on command, not every startup
        await self.tree.sync() 

    async def close(self):
        await db.close()
        await super().close()

bot = ISFEBot()

@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    
if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.error("DISCORD_TOKEN not found in .env")
    else:
        bot.run(token)
