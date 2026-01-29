import discord
from discord.ext import commands
from discord import app_commands
import logging


class Roles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setup_game_roles", description="Set up the Game Roles panel (MLBB, CODM, T8)")
    @app_commands.default_permissions(administrator=True)
    async def setup_game_roles(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        target_channel = channel or interaction.channel
        
        embed = discord.Embed(
            title="🎮 Game Roles Selection",
            description="Select your games to unlock their channels!",
            color=0x5865F2
        )
        embed.set_footer(text="System developed by Aedwon")

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

            # Simple toggle (users can have multiple game roles)
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
