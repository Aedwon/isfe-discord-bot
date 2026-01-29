import discord
from discord.ext import commands
from discord import app_commands
from database.db import db
from typing import Literal

# Hardcoded game titles
GAMES = ["MLBB", "CODM"]


class RegistrationPanel(discord.ui.View):
    """Persistent registration panel with game buttons."""
    
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="MLBB", style=discord.ButtonStyle.primary, custom_id="reg_mlbb", emoji="📱")
    async def mlbb_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_registration_modal(interaction, "MLBB")
    
    @discord.ui.button(label="CODM", style=discord.ButtonStyle.primary, custom_id="reg_codm", emoji="🎮")
    async def codm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_registration_modal(interaction, "CODM")
    
    @discord.ui.button(label="Unregister", style=discord.ButtonStyle.danger, custom_id="reg_unregister", emoji="🚪")
    async def unregister_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_unregister_menu(interaction)
    
    @discord.ui.button(label="My Teams", style=discord.ButtonStyle.secondary, custom_id="reg_myteams", emoji="👤")
    async def myteams_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_my_teams(interaction)
    
    async def show_registration_modal(self, interaction: discord.Interaction, game: str):
        """Show team selection and IGN input."""
        teams = await db.fetchall(
            "SELECT id, team_name FROM teams WHERE game_name = %s ORDER BY team_name",
            (game,)
        )
        
        if not teams:
            await interaction.response.send_message(
                f"❌ No teams available for **{game}**. Please contact an admin.",
                ephemeral=True
            )
            return
        
        # Create view with team dropdown
        view = TeamSelectView(game, teams)
        await interaction.response.send_message(
            f"**{game} Registration**\nSelect your team and enter your IGN:",
            view=view,
            ephemeral=True
        )
    
    async def show_unregister_menu(self, interaction: discord.Interaction):
        """Show games user can unregister from."""
        registrations = await db.fetchall(
            """SELECT t.game_name, t.team_name FROM player_registrations pr
               JOIN teams t ON pr.team_id = t.id
               WHERE pr.discord_id = %s""",
            (interaction.user.id,)
        )
        
        if not registrations:
            await interaction.response.send_message(
                "❌ You're not registered for any team.",
                ephemeral=True
            )
            return
        
        view = UnregisterView(registrations)
        await interaction.response.send_message(
            "Select the game to unregister from:",
            view=view,
            ephemeral=True
        )
    
    async def show_my_teams(self, interaction: discord.Interaction):
        """Show user's current registrations."""
        registrations = await db.fetchall(
            """SELECT t.game_name, t.team_name, pr.ign FROM player_registrations pr
               JOIN teams t ON pr.team_id = t.id
               WHERE pr.discord_id = %s
               ORDER BY t.game_name""",
            (interaction.user.id,)
        )
        
        if not registrations:
            await interaction.response.send_message(
                "❌ You're not registered for any team.",
                ephemeral=True
            )
            return
        
        lines = []
        for r in registrations:
            ign_display = f" — IGN: `{r['ign']}`" if r['ign'] else ""
            lines.append(f"• **{r['game_name']}**: {r['team_name']}{ign_display}")
        
        embed = discord.Embed(
            title="Your Team Registrations",
            description="\n".join(lines),
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class TeamSelectView(discord.ui.View):
    """View with paginated team dropdown and IGN button."""
    
    TEAMS_PER_PAGE = 25  # Discord's max options per dropdown
    
    def __init__(self, game: str, teams: list, page: int = 0):
        super().__init__(timeout=120)
        self.game = game
        self.all_teams = teams
        self.page = page
        self.max_pages = (len(teams) - 1) // self.TEAMS_PER_PAGE + 1
        self.selected_team_id = None
        self.selected_team_name = None
        
        # Get teams for current page
        start = page * self.TEAMS_PER_PAGE
        end = start + self.TEAMS_PER_PAGE
        page_teams = teams[start:end]
        
        # Add team dropdown
        self.team_select = TeamSelect(game, page_teams)
        self.add_item(self.team_select)
        
        # Add pagination buttons if needed
        if self.max_pages > 1:
            self.add_item(PrevPageButton(disabled=(page == 0)))
            self.add_item(PageIndicator(page + 1, self.max_pages))
            self.add_item(NextPageButton(disabled=(page >= self.max_pages - 1)))
    
    @discord.ui.button(label="Enter IGN & Submit", style=discord.ButtonStyle.success, row=2)
    async def submit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.team_select.selected_team_id:
            await interaction.response.send_message(
                "❌ Please select a team first.",
                ephemeral=True
            )
            return
        
        # Show IGN modal
        modal = IGNModal(
            self.game, 
            self.team_select.selected_team_id, 
            self.team_select.selected_team_name
        )
        await interaction.response.send_modal(modal)


class PrevPageButton(discord.ui.Button):
    """Previous page button for team pagination."""
    
    def __init__(self, disabled: bool = False):
        super().__init__(label="◀ Prev", style=discord.ButtonStyle.secondary, row=1, disabled=disabled)
    
    async def callback(self, interaction: discord.Interaction):
        view: TeamSelectView = self.view
        new_view = TeamSelectView(view.game, view.all_teams, view.page - 1)
        await interaction.response.edit_message(
            content=f"**{view.game}** - Select your team (Page {view.page}/{view.max_pages}):",
            view=new_view
        )


class PageIndicator(discord.ui.Button):
    """Non-interactive page indicator."""
    
    def __init__(self, current: int, total: int):
        super().__init__(label=f"{current}/{total}", style=discord.ButtonStyle.secondary, row=1, disabled=True)
    
    async def callback(self, interaction: discord.Interaction):
        pass


class NextPageButton(discord.ui.Button):
    """Next page button for team pagination."""
    
    def __init__(self, disabled: bool = False):
        super().__init__(label="Next ▶", style=discord.ButtonStyle.secondary, row=1, disabled=disabled)
    
    async def callback(self, interaction: discord.Interaction):
        view: TeamSelectView = self.view
        new_view = TeamSelectView(view.game, view.all_teams, view.page + 1)
        await interaction.response.edit_message(
            content=f"**{view.game}** - Select your team (Page {view.page + 2}/{view.max_pages}):",
            view=new_view
        )


class TeamSelect(discord.ui.Select):
    """Dropdown to select a team from current page."""
    
    def __init__(self, game: str, teams: list):
        self.game = game
        self.selected_team_id = None
        self.selected_team_name = None
        
        options = [
            discord.SelectOption(label=team["team_name"], value=str(team["id"]))
            for team in teams[:25]
        ]
        super().__init__(placeholder="Select your team...", options=options, row=0)
    
    async def callback(self, interaction: discord.Interaction):
        self.selected_team_id = int(self.values[0])
        self.selected_team_name = next(opt.label for opt in self.options if opt.value == self.values[0])
        await interaction.response.send_message(
            f"✅ Selected: **{self.selected_team_name}**\nNow click **Enter IGN & Submit**.",
            ephemeral=True
        )


class IGNModal(discord.ui.Modal):
    """Modal for entering IGN."""
    
    def __init__(self, game: str, team_id: int, team_name: str):
        super().__init__(title=f"{game} Registration")
        self.game = game
        self.team_id = team_id
        self.team_name = team_name
        
        self.ign_input = discord.ui.TextInput(
            label="Enter your In-Game Name (IGN)",
            placeholder="e.g., ProPlayer123",
            min_length=1,
            max_length=50,
            required=True
        )
        self.add_item(self.ign_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        ign = self.ign_input.value.strip()
        
        # Remove any existing registration for this game
        await db.execute(
            """DELETE pr FROM player_registrations pr
               JOIN teams t ON pr.team_id = t.id
               WHERE pr.discord_id = %s AND t.game_name = %s""",
            (interaction.user.id, self.game)
        )
        
        # Add new registration with IGN
        await db.execute(
            "INSERT INTO player_registrations (discord_id, team_id, ign) VALUES (%s, %s, %s)",
            (interaction.user.id, self.team_id, ign)
        )
        
        # Change nickname
        new_nickname = f"{self.game} | {ign}"
        try:
            await interaction.user.edit(nick=new_nickname)
            nickname_msg = f"\n📝 Nickname changed to: **{new_nickname}**"
        except discord.Forbidden:
            nickname_msg = "\n⚠️ Could not change nickname (missing permissions or you're the server owner)."
        except Exception as e:
            nickname_msg = f"\n⚠️ Could not change nickname: {e}"
        
        await interaction.response.send_message(
            f"✅ Registered to **{self.team_name}** ({self.game})!{nickname_msg}",
            ephemeral=True
        )


class UnregisterSelect(discord.ui.Select):
    """Dropdown to select which game to unregister from."""
    
    def __init__(self, registrations: list):
        self.registrations = registrations
        options = [
            discord.SelectOption(
                label=f"{r['game_name']}: {r['team_name']}", 
                value=r['game_name']
            )
            for r in registrations
        ]
        super().__init__(placeholder="Select game to unregister from...", options=options)
    
    async def callback(self, interaction: discord.Interaction):
        game = self.values[0]
        
        # Find the team name for the message
        team_name = next(r['team_name'] for r in self.registrations if r['game_name'] == game)
        
        # Remove registration
        await db.execute(
            """DELETE pr FROM player_registrations pr
               JOIN teams t ON pr.team_id = t.id
               WHERE pr.discord_id = %s AND t.game_name = %s""",
            (interaction.user.id, game)
        )
        
        await interaction.response.edit_message(
            content=f"✅ Unregistered from **{team_name}** ({game}).",
            view=None
        )


class UnregisterView(discord.ui.View):
    """View containing unregister dropdown."""
    
    def __init__(self, registrations: list):
        super().__init__(timeout=60)
        self.add_item(UnregisterSelect(registrations))


class Registration(commands.Cog):
    """Player registration system for teams."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    async def cog_load(self):
        """Register persistent view on cog load."""
        self.bot.add_view(RegistrationPanel())
    
    # =========== ADMIN COMMANDS ===========
    
    @app_commands.command(name="regpanel", description="Send the registration panel")
    @app_commands.checks.has_permissions(administrator=True)
    async def regpanel(self, interaction: discord.Interaction):
        """Send the persistent registration panel."""
        embed = discord.Embed(
            title="🎮 Player Registration",
            description="Click a game button to register for your team.\n\n"
                        "• **MLBB** / **CODM** — Register or update your team\n"
                        "• **Unregister** — Leave your current team\n"
                        "• **My Teams** — View your registrations",
            color=discord.Color.gold()
        )
        await interaction.channel.send(embed=embed, view=RegistrationPanel())
        await interaction.response.send_message("✅ Registration panel sent!", ephemeral=True)
    
    @app_commands.command(name="myteams", description="View your current team registrations")
    async def myteams(self, interaction: discord.Interaction):
        """Shows all games the user is registered for."""
        registrations = await db.fetchall(
            """SELECT t.game_name, t.team_name, pr.ign FROM player_registrations pr
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
        
        lines = []
        for r in registrations:
            ign_display = f" — IGN: `{r['ign']}`" if r['ign'] else ""
            lines.append(f"• **{r['game_name']}**: {r['team_name']}{ign_display}")
        
        embed = discord.Embed(
            title="Your Team Registrations",
            description="\n".join(lines),
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # =========== TEAM MANAGEMENT ===========
    
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
    
    @teams_group.command(name="remove", description="Remove teams (comma-separated for bulk)")
    @app_commands.describe(game="The game title", team_names="Team name(s) to remove, comma-separated for bulk")
    @app_commands.checks.has_permissions(administrator=True)
    async def teams_remove(
        self, 
        interaction: discord.Interaction, 
        game: Literal["MLBB", "CODM"],
        team_names: str
    ):
        """Remove teams and all their registrations (supports bulk removal)."""
        names = [name.strip() for name in team_names.split(",") if name.strip()]
        
        if not names:
            await interaction.response.send_message("❌ No valid team names provided.", ephemeral=True)
            return
        
        removed = []
        not_found = []
        
        for name in names:
            result = await db.execute(
                "DELETE FROM teams WHERE game_name = %s AND team_name = %s",
                (game, name)
            )
            if result:
                removed.append(name)
            else:
                not_found.append(name)
        
        msg_parts = []
        if removed:
            msg_parts.append(f"✅ Removed: {', '.join(removed)}")
        if not_found:
            msg_parts.append(f"⚠️ Not found: {', '.join(not_found)}")
        
        await interaction.response.send_message(
            f"**{game}** Teams:\n" + "\n".join(msg_parts),
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
        """Show team roster with IGNs without mentioning."""
        players = await db.fetchall(
            """SELECT pr.discord_id, pr.ign FROM player_registrations pr
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
        
        lines = []
        for p in players:
            member = interaction.guild.get_member(p["discord_id"])
            ign_display = f" — `{p['ign']}`" if p["ign"] else ""
            if member:
                lines.append(f"• {member.display_name}{ign_display}")
            else:
                lines.append(f"• <@{p['discord_id']}> (not in server){ign_display}")
        
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
        return choices[:25]


async def setup(bot: commands.Bot):
    await bot.add_cog(Registration(bot))
