import discord
from discord.ext import commands
from discord import app_commands


class Help(commands.Cog):
    """Help command to display all available commands dynamically."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    def _is_admin_command(self, command: app_commands.Command) -> bool:
        """Check if a command requires administrator permissions."""
        for check in command.checks:
            # Check for has_permissions decorator
            if hasattr(check, '__closure__') and check.__closure__:
                for cell in check.__closure__:
                    try:
                        perms = cell.cell_contents
                        if isinstance(perms, dict) and perms.get('administrator'):
                            return True
                    except (ValueError, TypeError):
                        pass
        return False
    
    def _format_command(self, cmd: app_commands.Command) -> str:
        """Format a command for display."""
        params = []
        for param in cmd.parameters:
            if param.required:
                params.append(f"<{param.name}>")
            else:
                params.append(f"[{param.name}]")
        
        param_str = " " + " ".join(params) if params else ""
        return f"`/{cmd.qualified_name}{param_str}` - {cmd.description}"
    
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
        
        # Group commands by cog
        cog_commands: dict[str, list[tuple[str, bool]]] = {}  # {cog_name: [(formatted_cmd, is_admin), ...]}
        
        for cmd in self.bot.tree.walk_commands():
            if isinstance(cmd, app_commands.Command):
                cog_name = cmd.binding.__class__.__name__ if cmd.binding else "General"
                is_admin_cmd = self._is_admin_command(cmd)
                
                if cog_name not in cog_commands:
                    cog_commands[cog_name] = []
                
                cog_commands[cog_name].append((self._format_command(cmd), is_admin_cmd))
        
        # Cog display names and emojis
        cog_display = {
            "Registration": ("🎮 Registration", "🎮 Registration (Admin)"),
            "Tickets": ("🎫 Tickets", "🎫 Tickets (Admin)"),
            "Roles": ("🏷️ Roles", "🏷️ Roles (Admin)"),
            "Embeds": ("📝 Embeds", "📝 Embeds (Admin)"),
            "Threads": ("🧵 Threads", "🧵 Threads (Admin)"),
            "Voice": ("🔊 Voice", "🔊 Voice (Admin)"),
            "Help": ("❓ Help", "❓ Help"),
            "AdminLogs": ("📋 Admin Logs", "📋 Admin Logs (Admin)"),
        }
        
        # Add panel info for Registration
        panel_info = """
Use the **Registration Panel** (sent via `/regpanel`):
• Click **MLBB** / **CODM** to register
• Click **Unregister** to leave a team
• Click **My Teams** to view registrations
        """.strip()
        embed.add_field(name="🎮 How to Register", value=panel_info, inline=False)
        
        # Process each cog
        for cog_name, commands_list in sorted(cog_commands.items()):
            user_cmds = [cmd for cmd, is_admin_cmd in commands_list if not is_admin_cmd]
            admin_cmds = [cmd for cmd, is_admin_cmd in commands_list if is_admin_cmd]
            
            display_names = cog_display.get(cog_name, (f"📁 {cog_name}", f"📁 {cog_name} (Admin)"))
            
            # Add user-accessible commands
            if user_cmds:
                embed.add_field(
                    name=display_names[0],
                    value="\n".join(user_cmds[:10]),  # Limit to avoid embed limits
                    inline=False
                )
            
            # Add admin commands (only visible to admins)
            if is_admin and admin_cmds:
                embed.add_field(
                    name=display_names[1],
                    value="\n".join(admin_cmds[:10]),
                    inline=False
                )
        
        embed.set_footer(text="Admin commands are only visible to administrators.")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))
