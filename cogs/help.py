import discord
from discord.ext import commands
from discord import app_commands


class Help(commands.Cog):
    """Help command to display all available commands."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(name="help", description="View all available bot commands")
    async def help_command(self, interaction: discord.Interaction):
        """Display all available commands based on user permissions."""
        
        is_admin = interaction.user.guild_permissions.administrator
        
        # Build embed
        embed = discord.Embed(
            title="📖 Bot Commands",
            description="Here are all the available commands.",
            color=discord.Color.blue()
        )
        
        # === GENERAL COMMANDS ===
        general_commands = """
`/myteams` - View your team registrations
`/help` - Show this help message
        """.strip()
        embed.add_field(name="👤 General", value=general_commands, inline=False)
        
        # === REGISTRATION (via Panel) ===
        registration_info = """
Use the **Registration Panel** (sent via `/regpanel`):
• Click **MLBB** / **CODM** to register
• Click **Unregister** to leave a team
• Click **My Teams** to view registrations
        """.strip()
        embed.add_field(name="🎮 Registration", value=registration_info, inline=False)
        
        # === ADMIN COMMANDS ===
        if is_admin:
            # Registration Admin
            reg_admin = """
`/regpanel` - Send the registration panel
`/teams add <game> <names>` - Add teams (comma-separated)
`/teams remove <game> <team>` - Remove a team
`/teams list <game>` - List all teams
`/mention <game> <team>` - Ping all players in a team
`/roster <game> <team>` - View roster (no ping)
            """.strip()
            embed.add_field(name="🎮 Registration (Admin)", value=reg_admin, inline=False)
            
            # Tickets Admin
            tickets_admin = """
`/setup_tickets [channel]` - Setup ticket panel
`/set_ticket_log_channel <channel>` - Set transcript log channel
            """.strip()
            embed.add_field(name="🎫 Tickets (Admin)", value=tickets_admin, inline=False)
            
            # Roles Admin
            roles_admin = """
`/reaction_panel <message_link> <emoji> <role>` - Add reaction role
`/setup_game_roles [channel]` - Setup game roles panel
            """.strip()
            embed.add_field(name="🏷️ Roles (Admin)", value=roles_admin, inline=False)
            
            # Embeds Admin
            embeds_admin = """
`/send_embed <channel> <link> [schedule]` - Send Discohook embed
`/cancel_embed` - Cancel a scheduled embed
`/set_embed_log_channel <channel>` - Set embed log channel
            """.strip()
            embed.add_field(name="📝 Embeds (Admin)", value=embeds_admin, inline=False)
            
            # Threads Admin
            threads_admin = """
`/createthreads <names> <roles>` - Bulk create private threads
            """.strip()
            embed.add_field(name="🧵 Threads (Admin)", value=threads_admin, inline=False)
            
            # Voice Admin
            voice_admin = """
`/autocreate_setup <channel>` - Setup auto-duplicate voice channel
            """.strip()
            embed.add_field(name="🔊 Voice (Admin)", value=voice_admin, inline=False)
        
        embed.set_footer(text="Admin commands are only visible to administrators.")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))
