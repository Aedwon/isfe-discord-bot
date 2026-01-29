import discord
from discord.ext import commands
from discord import app_commands
from database.db import db
from typing import Optional, Literal

# Hardcoded game titles
GAMES = ["MLBB", "CODM"]

class GameSelect(discord.ui.Select):
    """Dropdown to select a game title."""
    
    def __init__(self, action: str):
        self.action = action  # 'register' or 'unregister'
        options = [discord.SelectOption(label=game, value=game) for game in GAMES]
        super().__init__(placeholder="Select a game...", options=options)
    
    async def callback(self, interaction: discord.Interaction):
        game = self.values[0]
        
        if self.action == "register":
            # Fetch teams for this game
            teams = await db.fetchall(
                "SELECT id, team_name FROM teams WHERE game_name = %s ORDER BY team_name",
                (game,)
            )
            
            if not teams:
                await interaction.response.edit_message(
                    content=f"❌ No teams available for **{game}**. Please contact an admin.",
                    view=None
                )
                return
            
            # Show team selection
            view = TeamSelectView(game, teams)
            await interaction.response.edit_message(
                content=f"**{game}** - Select your team:",
                view=view
            )
        
        elif self.action == "unregister":
            # Check if user is registered for this game
            registration = await db.fetchrow(
                """SELECT t.team_name FROM player_registrations pr
                   JOIN teams t ON pr.team_id = t.id
                   WHERE pr.discord_id = %s AND t.game_name = %s""",
                (interaction.user.id, game)
            )
            
            if not registration:
                await interaction.response.edit_message(
                    content=f"❌ You're not registered for any team in **{game}**.",
                    view=None
                )
                return
            
            # Remove registration
            await db.execute(
                """DELETE pr FROM player_registrations pr
                   JOIN teams t ON pr.team_id = t.id
                   WHERE pr.discord_id = %s AND t.game_name = %s""",
                (interaction.user.id, game)
            )
            
            await interaction.response.edit_message(
                content=f"✅ You've been unregistered from **{registration['team_name']}** ({game}).",
                view=None
            )


class GameSelectView(discord.ui.View):
    """View containing the game dropdown."""
    
    def __init__(self, action: str):
        super().__init__(timeout=60)
        self.add_item(GameSelect(action))
    
    async def on_timeout(self):
        pass


class TeamSelect(discord.ui.Select):
    """Dropdown to select a team."""
    
    def __init__(self, game: str, teams: list):
        self.game = game
        options = [
            discord.SelectOption(label=team["team_name"], value=str(team["id"]))
            for team in teams[:25]  # Discord limit
        ]
        super().__init__(placeholder="Select your team...", options=options)
    
    async def callback(self, interaction: discord.Interaction):
        team_id = int(self.values[0])
        team_name = next(opt.label for opt in self.options if opt.value == self.values[0])
        
        # Check if already registered for this team
        existing = await db.fetchrow(
            "SELECT id FROM player_registrations WHERE discord_id = %s AND team_id = %s",
            (interaction.user.id, team_id)
        )
        
        if existing:
            await interaction.response.edit_message(
                content=f"ℹ️ You're already registered for **{team_name}** ({self.game}).",
                view=None
            )
            return
        
        # Remove any existing registration for this game
        await db.execute(
            """DELETE pr FROM player_registrations pr
               JOIN teams t ON pr.team_id = t.id
               WHERE pr.discord_id = %s AND t.game_name = %s""",
            (interaction.user.id, self.game)
        )
        
        # Add new registration
        await db.execute(
            "INSERT INTO player_registrations (discord_id, team_id) VALUES (%s, %s)",
            (interaction.user.id, team_id)
        )
        
        await interaction.response.edit_message(
            content=f"✅ You've been registered to **{team_name}** ({self.game})!",
            view=None
        )


class TeamSelectView(discord.ui.View):
    """View containing the team dropdown."""
    
    def __init__(self, game: str, teams: list):
        super().__init__(timeout=60)
        self.add_item(TeamSelect(game, teams))
    
    async def on_timeout(self):
        pass


class Registration(commands.Cog):
    """Player registration system for teams."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    # =========== PLAYER COMMANDS ===========
    
    @app_commands.command(name="register", description="Register for a team")
    async def register(self, interaction: discord.Interaction):
        """Shows game selection dropdown, then team selection."""
        view = GameSelectView(action="register")
        await interaction.response.send_message("Select your game:", view=view, ephemeral=True)
    
    @app_commands.command(name="unregister", description="Leave your current team")
    async def unregister(self, interaction: discord.Interaction):
        """Shows game selection dropdown, then unregisters from that game."""
        view = GameSelectView(action="unregister")
        await interaction.response.send_message("Select the game to unregister from:", view=view, ephemeral=True)
    
    @app_commands.command(name="myteams", description="View your current team registrations")
    async def myteams(self, interaction: discord.Interaction):
        """Shows all games the user is registered for."""
        registrations = await db.fetchall(
            """SELECT t.game_name, t.team_name FROM player_registrations pr
               JOIN teams t ON pr.team_id = t.id
               WHERE pr.discord_id = %s
               ORDER BY t.game_name""",
            (interaction.user.id,)
        )
        
        if not registrations:
            await interaction.response.send_message(
                "❌ You're not registered for any team.", ephemeral=True
            )
            return
        
        lines = [f"• **{r['game_name']}**: {r['team_name']}" for r in registrations]
        embed = discord.Embed(
            title="Your Team Registrations",
            description="\n".join(lines),
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # =========== ADMIN COMMANDS ===========
    
    teams_group = app_commands.Group(name="teams", description="Manage teams")
    
    @teams_group.command(name="add", description="Add teams to a game (comma-separated)")
    @app_commands.describe(
        game="The game title",
        team_names="Team names separated by commas (e.g., Team A, Team B, Team C)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def teams_add(
        self, 
        interaction: discord.Interaction, 
        game: Literal["MLBB", "CODM"],
        team_names: str
    ):
        """Bulk add teams to a game."""
        names = [name.strip() for name in team_names.split(",") if name.strip()]
        
        if not names:
            await interaction.response.send_message("❌ No valid team names provided.", ephemeral=True)
            return
        
        added = []
        duplicates = []
        
        for name in names:
            try:
                await db.execute(
                    "INSERT INTO teams (game_name, team_name) VALUES (%s, %s)",
                    (game, name)
                )
                added.append(name)
            except Exception:
                duplicates.append(name)
        
        msg_parts = []
        if added:
            msg_parts.append(f"✅ Added: {', '.join(added)}")
        if duplicates:
            msg_parts.append(f"⚠️ Already exists: {', '.join(duplicates)}")
        
        await interaction.response.send_message(
            f"**{game}** Teams:\n" + "\n".join(msg_parts),
            ephemeral=True
        )
    
    @teams_group.command(name="remove", description="Remove a team")
    @app_commands.describe(game="The game title", team_name="The team to remove")
    @app_commands.checks.has_permissions(administrator=True)
    async def teams_remove(
        self, 
        interaction: discord.Interaction, 
        game: Literal["MLBB", "CODM"],
        team_name: str
    ):
        """Remove a team and all its registrations."""
        result = await db.execute(
            "DELETE FROM teams WHERE game_name = %s AND team_name = %s",
            (game, team_name)
        )
        
        if result:
            await interaction.response.send_message(
                f"✅ Removed **{team_name}** from {game} (all registrations cleared).",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ Team **{team_name}** not found in {game}.",
                ephemeral=True
            )
    
    @teams_group.command(name="list", description="List all teams for a game")
    @app_commands.describe(game="The game title")
    @app_commands.checks.has_permissions(administrator=True)
    async def teams_list(
        self, 
        interaction: discord.Interaction, 
        game: Literal["MLBB", "CODM"]
    ):
        """List all teams and player counts for a game."""
        teams = await db.fetchall(
            """SELECT t.team_name, COUNT(pr.id) as player_count
               FROM teams t
               LEFT JOIN player_registrations pr ON t.id = pr.team_id
               WHERE t.game_name = %s
               GROUP BY t.id, t.team_name
               ORDER BY t.team_name""",
            (game,)
        )
        
        if not teams:
            await interaction.response.send_message(
                f"❌ No teams found for **{game}**.", ephemeral=True
            )
            return
        
        lines = [f"• {t['team_name']} ({t['player_count']} players)" for t in teams]
        embed = discord.Embed(
            title=f"{game} Teams",
            description="\n".join(lines),
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # =========== LEAGUE OPS COMMANDS ===========
    
    @app_commands.command(name="mention", description="Mention all players in a team")
    @app_commands.describe(game="The game title", team_name="The team to mention")
    @app_commands.checks.has_permissions(administrator=True)
    async def mention(
        self, 
        interaction: discord.Interaction, 
        game: Literal["MLBB", "CODM"],
        team_name: str
    ):
        """Mention all registered players for a team."""
        players = await db.fetchall(
            """SELECT pr.discord_id FROM player_registrations pr
               JOIN teams t ON pr.team_id = t.id
               WHERE t.game_name = %s AND t.team_name = %s""",
            (game, team_name)
        )
        
        if not players:
            await interaction.response.send_message(
                f"❌ No players registered for **{team_name}** ({game}).",
                ephemeral=True
            )
            return
        
        mentions = " ".join([f"<@{p['discord_id']}>" for p in players])
        await interaction.response.send_message(
            f"**{team_name}** ({game}):\n{mentions}"
        )
    
    @app_commands.command(name="roster", description="View team roster without pinging")
    @app_commands.describe(game="The game title", team_name="The team to view")
    @app_commands.checks.has_permissions(administrator=True)
    async def roster(
        self, 
        interaction: discord.Interaction, 
        game: Literal["MLBB", "CODM"],
        team_name: str
    ):
        """Show team roster without mentioning."""
        players = await db.fetchall(
            """SELECT pr.discord_id FROM player_registrations pr
               JOIN teams t ON pr.team_id = t.id
               WHERE t.game_name = %s AND t.team_name = %s""",
            (game, team_name)
        )
        
        if not players:
            await interaction.response.send_message(
                f"❌ No players registered for **{team_name}** ({game}).",
                ephemeral=True
            )
            return
        
        # Use guild.get_member to get display names
        lines = []
        for p in players:
            member = interaction.guild.get_member(p["discord_id"])
            if member:
                lines.append(f"• {member.display_name}")
            else:
                lines.append(f"• <@{p['discord_id']}> (not in server)")
        
        embed = discord.Embed(
            title=f"{team_name} ({game})",
            description="\n".join(lines),
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"{len(players)} player(s)")
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # =========== AUTOCOMPLETE ===========
    
    @teams_remove.autocomplete("team_name")
    @mention.autocomplete("team_name")
    @roster.autocomplete("team_name")
    async def team_name_autocomplete(
        self, 
        interaction: discord.Interaction, 
        current: str
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for team names based on selected game."""
        # Get the game from the interaction
        game = None
        for opt in interaction.data.get("options", []):
            if opt["name"] == "game":
                game = opt["value"]
                break
        
        if not game:
            return []
        
        teams = await db.fetchall(
            "SELECT team_name FROM teams WHERE game_name = %s ORDER BY team_name",
            (game,)
        )
        
        choices = [
            app_commands.Choice(name=t["team_name"], value=t["team_name"])
            for t in teams
            if current.lower() in t["team_name"].lower()
        ]
        return choices[:25]  # Discord limit


async def setup(bot: commands.Bot):
    await bot.add_cog(Registration(bot))
