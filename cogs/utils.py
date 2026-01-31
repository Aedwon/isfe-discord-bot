import discord
from discord.ext import commands
import random


class Utils(commands.Cog):
    """Simple utility commands."""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name="flip")
    async def flip(self, ctx):
        """Flip a coin - Heads or Tails."""
        result = random.choice(["🪙 **Heads!**", "🪙 **Tails!**"])
        await ctx.send(result)


async def setup(bot):
    await bot.add_cog(Utils(bot))
