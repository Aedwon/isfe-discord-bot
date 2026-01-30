import discord
from discord.ext import commands
from discord import app_commands
from database.db import db
from typing import Literal

# Game role IDs
GAME_ROLES = {
    "MLBB": 1464901284128751782,
    "CODM": 1464901350130188436,
}

def truncate_nickname(nick: str, max_len: int = 32) -> str:
    """Truncate nickname to Discord's 32 char limit."""
    if len(nick) <= max_len:
        return nick
    return nick[:max_len - 3] + "..."


class VerificationPanel(discord.ui.View):
    """Persistent verification panel."""
    
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Verify", style=discord.ButtonStyle.success, custom_id="verify_main", emoji="✅")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_verify(interaction)
    
    @discord.ui.button(label="Unverify", style=discord.ButtonStyle.danger, custom_id="verify_unverify", emoji="🚪")
    async def unverify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_unverify(interaction)
    
    @discord.ui.button(label="My Status", style=discord.ButtonStyle.secondary, custom_id="verify_status", emoji="👤")
    async def status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_status(interaction)
    
    async def handle_verify(self, interaction: discord.Interaction):
        """Check roles and show appropriate verification flow."""
        user_role_ids = {r.id for r in interaction.user.roles}
        
        has_mlbb = GAME_ROLES["MLBB"] in user_role_ids
        has_codm = GAME_ROLES["CODM"] in user_role_ids
        
        if not has_mlbb and not has_codm:
            await interaction.response.send_message(
                "❌ Please select a game role from the **Game Roles Selection** panel first!",
                ephemeral=True
            )
            return
        
        if has_mlbb and has_codm:
            # User has both - ask which to verify
            view = GameChoiceView()
            await interaction.response.send_message(
                "You have both MLBB and CODM roles. Which game do you want to verify for?",
                view=view,
                ephemeral=True
            )
        elif has_mlbb:
            await self.start_verification(interaction, "MLBB")
        else:
            await self.start_verification(interaction, "CODM")
    
    async def start_verification(self, interaction: discord.Interaction, game: str):
        """Show team selection for the specified game."""
        teams = await db.fetchall(
            "SELECT id, team_name FROM teams WHERE game_name = %s ORDER BY LOWER(team_name)",
            (game,)
        )
        
        if not teams:
            await interaction.response.send_message(
                f"❌ No teams available for **{game}**. Please contact an admin.",
                ephemeral=True
            )
            return
        
        view = TeamSelectView(game, teams)
        await interaction.response.send_message(
            f"**{game} Verification**\nSelect your team:",
            view=view,
            ephemeral=True
        )
    
    async def handle_unverify(self, interaction: discord.Interaction):
        """Show games user can unverify from."""
        registrations = await db.fetchall(
            """SELECT t.game_name, t.team_name FROM player_registrations pr
               JOIN teams t ON pr.team_id = t.id
               WHERE pr.discord_id = %s""",
            (interaction.user.id,)
        )
        
        if not registrations:
            await interaction.response.send_message(
                "❌ You're not verified for any team.",
                ephemeral=True
            )
            return
        
        view = UnverifyView(registrations)
        await interaction.response.send_message(
            "Select the game to unverify from:",
            view=view,
            ephemeral=True
        )
    
    async def show_status(self, interaction: discord.Interaction):
        """Show user's verification status."""
        registrations = await db.fetchall(
            """SELECT t.game_name, t.team_name, pr.ign, pr.nickname_preference 
               FROM player_registrations pr
               JOIN teams t ON pr.team_id = t.id
               WHERE pr.discord_id = %s
               ORDER BY t.game_name""",
            (interaction.user.id,)
        )
        
        if not registrations:
            await interaction.response.send_message(
                "❌ You're not verified for any team.",
                ephemeral=True
            )
            return
        
        lines = []
        for r in registrations:
            ign_display = f" — IGN: `{r['ign']}`" if r['ign'] else ""
            lines.append(f"• **{r['game_name']}**: {r['team_name']}{ign_display}")
        
        embed = discord.Embed(
            title="Your Verification Status",
            description="\n".join(lines),
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class GameChoiceView(discord.ui.View):
    """View for choosing between MLBB and CODM when user has both."""
    
    def __init__(self):
        super().__init__(timeout=120)
    
    @discord.ui.button(label="MLBB", style=discord.ButtonStyle.primary, emoji="📱")
    async def mlbb_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await VerificationPanel().start_verification(interaction, "MLBB")
    
    @discord.ui.button(label="CODM", style=discord.ButtonStyle.primary, emoji="🎮")
    async def codm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await VerificationPanel().start_verification(interaction, "CODM")


class TeamSelectView(discord.ui.View):
    """Paginated team selection view."""
    
    TEAMS_PER_PAGE = 25
    
    def __init__(self, game: str, teams: list, page: int = 0):
        super().__init__(timeout=120)
        self.game = game
        self.all_teams = teams
        self.page = page
        self.max_pages = (len(teams) - 1) // self.TEAMS_PER_PAGE + 1
        
        start = page * self.TEAMS_PER_PAGE
        end = start + self.TEAMS_PER_PAGE
        page_teams = teams[start:end]
        
        self.team_select = TeamSelect(game, page_teams)
        self.add_item(self.team_select)
        
        if self.max_pages > 1:
            self.add_item(PrevPageButton(disabled=(page == 0)))
            self.add_item(PageIndicator(page + 1, self.max_pages))
            self.add_item(NextPageButton(disabled=(page >= self.max_pages - 1)))
    
    @discord.ui.button(label="Continue →", style=discord.ButtonStyle.success, row=2)
    async def continue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.team_select.selected_team_id:
            await interaction.response.send_message("❌ Please select a team first.", ephemeral=True)
            return
        
        modal = IGNModal(self.game, self.team_select.selected_team_id, self.team_select.selected_team_name)
        await interaction.response.send_modal(modal)


class TeamSelect(discord.ui.Select):
    """Team dropdown."""
    
    def __init__(self, game: str, teams: list):
        self.game = game
        self.selected_team_id = None
        self.selected_team_name = None
        
        options = [
            discord.SelectOption(label=team["team_name"][:100], value=str(team["id"]))
            for team in teams[:25]
        ]
        super().__init__(placeholder="Select your team...", options=options, row=0)
    
    async def callback(self, interaction: discord.Interaction):
        self.selected_team_id = int(self.values[0])
        self.selected_team_name = next(opt.label for opt in self.options if opt.value == self.values[0])
        await interaction.response.send_message(
            f"✅ Selected: **{self.selected_team_name}**\nClick **Continue →** to enter your IGN.",
            ephemeral=True
        )


class PrevPageButton(discord.ui.Button):
    def __init__(self, disabled: bool = False):
        super().__init__(label="◀ Prev", style=discord.ButtonStyle.secondary, row=1, disabled=disabled)
    
    async def callback(self, interaction: discord.Interaction):
        view: TeamSelectView = self.view
        new_view = TeamSelectView(view.game, view.all_teams, view.page - 1)
        await interaction.response.edit_message(view=new_view)


class PageIndicator(discord.ui.Button):
    def __init__(self, current: int, total: int):
        super().__init__(label=f"{current}/{total}", style=discord.ButtonStyle.secondary, row=1, disabled=True)
    
    async def callback(self, interaction: discord.Interaction):
        pass


class NextPageButton(discord.ui.Button):
    def __init__(self, disabled: bool = False):
        super().__init__(label="Next ▶", style=discord.ButtonStyle.secondary, row=1, disabled=disabled)
    
    async def callback(self, interaction: discord.Interaction):
        view: TeamSelectView = self.view
        new_view = TeamSelectView(view.game, view.all_teams, view.page + 1)
        await interaction.response.edit_message(view=new_view)


class IGNModal(discord.ui.Modal):
    """Modal for entering IGN."""
    
    def __init__(self, game: str, team_id: int, team_name: str):
        super().__init__(title=f"{game} Verification")
        self.game = game
        self.team_id = team_id
        self.team_name = team_name
        
        self.ign_input = discord.ui.TextInput(
            label="Enter your In-Game Name (IGN)",
            placeholder="e.g., ProPlayer123",
            min_length=1,
            max_length=30,
            required=True
        )
        self.add_item(self.ign_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        ign = self.ign_input.value.strip()
        
        # Check if user has other game registrations
        other_reg = await db.fetchrow(
            """SELECT t.game_name, pr.ign FROM player_registrations pr
               JOIN teams t ON pr.team_id = t.id
               WHERE pr.discord_id = %s AND t.game_name != %s""",
            (interaction.user.id, self.game)
        )
        
        # Remove existing registration for THIS game
        await db.execute(
            """DELETE pr FROM player_registrations pr
               JOIN teams t ON pr.team_id = t.id
               WHERE pr.discord_id = %s AND t.game_name = %s""",
            (interaction.user.id, self.game)
        )
        
        # Add new registration
        await db.execute(
            "INSERT INTO player_registrations (discord_id, team_id, ign, nickname_preference) VALUES (%s, %s, %s, 'this')",
            (interaction.user.id, self.team_id, ign)
        )
        
        # If verified for both games, show nickname choice
        if other_reg:
            view = NicknameChoiceView(
                current_game=self.game,
                current_ign=ign,
                other_game=other_reg['game_name'],
                other_ign=other_reg['ign'],
                team_name=self.team_name
            )
            await interaction.response.send_message(
                f"✅ Verified for **{self.team_name}** ({self.game})!\n\n"
                f"You're verified for both games. Choose your nickname format:",
                view=view,
                ephemeral=True
            )
        else:
            # Only one game - set nickname directly
            new_nickname = truncate_nickname(f"{self.game} | {ign}")
            nickname_msg = await self.change_nickname(interaction.user, new_nickname)
            
            await interaction.response.send_message(
                f"✅ Verified for **{self.team_name}** ({self.game})!{nickname_msg}",
                ephemeral=True
            )
    
    async def change_nickname(self, member: discord.Member, new_nickname: str) -> str:
        try:
            await member.edit(nick=new_nickname)
            return f"\n📝 Nickname: **{new_nickname}**"
        except discord.Forbidden:
            return "\n⚠️ Could not change nickname (missing permissions or server owner)."
        except Exception as e:
            return f"\n⚠️ Could not change nickname: {e}"


class NicknameChoiceView(discord.ui.View):
    """View for choosing nickname format when verified for both games."""
    
    def __init__(self, current_game: str, current_ign: str, other_game: str, other_ign: str, team_name: str):
        super().__init__(timeout=120)
        self.current_game = current_game
        self.current_ign = current_ign
        self.other_game = other_game
        self.other_ign = other_ign
        self.team_name = team_name
        
        # Build nickname options - store full nicknames as values
        self.nickname_options = {
            "this": f"{current_game} | {current_ign}",
            "other": f"{other_game} | {other_ign}",
            "combined": f"{current_game} | {current_ign} • {other_game} | {other_ign}",
            "plain": current_ign,
        }
        
        select = NicknameSelect(self.nickname_options)
        self.add_item(select)


class NicknameSelect(discord.ui.Select):
    """Dropdown for nickname format selection - applies immediately on select."""
    
    def __init__(self, nickname_options: dict):
        self.nickname_options = nickname_options
        
        select_options = [
            discord.SelectOption(
                label=truncate_nickname(nick, 100), 
                value=key, 
                description=f"Preview: {truncate_nickname(nick)}"
            )
            for key, nick in nickname_options.items()
        ]
        super().__init__(placeholder="Choose nickname format...", options=select_options, row=0)
    
    async def callback(self, interaction: discord.Interaction):
        selected_key = self.values[0]
        selected_nickname = self.nickname_options[selected_key]
        new_nickname = truncate_nickname(selected_nickname)
        
        try:
            await interaction.user.edit(nick=new_nickname)
            await interaction.response.edit_message(
                content=f"✅ Nickname set to: **{new_nickname}**",
                view=None
            )
        except discord.Forbidden:
            await interaction.response.edit_message(
                content="⚠️ Could not change nickname (missing permissions or server owner).",
                view=None
            )


class UnverifySelect(discord.ui.Select):
    """Dropdown for game unverification."""
    
    def __init__(self, registrations: list):
        self.registrations = registrations
        options = [
            discord.SelectOption(label=f"{r['game_name']}: {r['team_name']}", value=r['game_name'])
            for r in registrations
        ]
        super().__init__(placeholder="Select game to unverify from...", options=options)
    
    async def callback(self, interaction: discord.Interaction):
        game = self.values[0]
        team_name = next(r['team_name'] for r in self.registrations if r['game_name'] == game)
        
        await db.execute(
            """DELETE pr FROM player_registrations pr
               JOIN teams t ON pr.team_id = t.id
               WHERE pr.discord_id = %s AND t.game_name = %s""",
            (interaction.user.id, game)
        )
        
        await interaction.response.edit_message(
            content=f"✅ Unverified from **{team_name}** ({game}).",
            view=None
        )


class UnverifyView(discord.ui.View):
    def __init__(self, registrations: list):
        super().__init__(timeout=60)
        self.add_item(UnverifySelect(registrations))


# ============ ADMIN TEAM MANAGEMENT ============

class TeamRemoveView(discord.ui.View):
    """Multi-select team removal."""
    
    TEAMS_PER_PAGE = 25
    
    def __init__(self, game: str, teams: list, page: int = 0):
        super().__init__(timeout=120)
        self.game = game
        self.all_teams = teams
        self.page = page
        self.max_pages = (len(teams) - 1) // self.TEAMS_PER_PAGE + 1
        
        start = page * self.TEAMS_PER_PAGE
        end = start + self.TEAMS_PER_PAGE
        page_teams = teams[start:end]
        
        self.team_select = TeamRemoveSelect(game, page_teams)
        self.add_item(self.team_select)
        
        if self.max_pages > 1:
            self.add_item(RemovePrevButton(disabled=(page == 0)))
            self.add_item(RemovePageIndicator(page + 1, self.max_pages))
            self.add_item(RemoveNextButton(disabled=(page >= self.max_pages - 1)))
    
    @discord.ui.button(label="Remove Selected", style=discord.ButtonStyle.danger, row=2)
    async def remove_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.team_select.values:
            await interaction.response.send_message("❌ No teams selected.", ephemeral=True)
            return
        
        removed = []
        for team_id in self.team_select.values:
            result = await db.execute("DELETE FROM teams WHERE id = %s", (int(team_id),))
            if result:
                team = next((t for t in self.all_teams if str(t["id"]) == team_id), None)
                if team:
                    removed.append(team["team_name"])
        
        if removed:
            await interaction.response.edit_message(
                content=f"✅ Removed from **{self.game}**: {', '.join(removed)}",
                view=None
            )
        else:
            await interaction.response.edit_message(content="❌ No teams were removed.", view=None)


class TeamRemoveSelect(discord.ui.Select):
    def __init__(self, game: str, teams: list):
        self.game = game
        options = [
            discord.SelectOption(label=team["team_name"][:100], value=str(team["id"]))
            for team in teams[:25]
        ]
        super().__init__(placeholder="Select teams to remove...", options=options, min_values=1, max_values=len(options), row=0)
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"✅ Selected {len(self.values)} team(s). Click **Remove Selected**.", ephemeral=True)


class RemovePrevButton(discord.ui.Button):
    def __init__(self, disabled: bool = False):
        super().__init__(label="◀ Prev", style=discord.ButtonStyle.secondary, row=1, disabled=disabled)
    
    async def callback(self, interaction: discord.Interaction):
        view: TeamRemoveView = self.view
        new_view = TeamRemoveView(view.game, view.all_teams, view.page - 1)
        await interaction.response.edit_message(view=new_view)


class RemovePageIndicator(discord.ui.Button):
    def __init__(self, current: int, total: int):
        super().__init__(label=f"{current}/{total}", style=discord.ButtonStyle.secondary, row=1, disabled=True)
    
    async def callback(self, interaction: discord.Interaction):
        pass


class RemoveNextButton(discord.ui.Button):
    def __init__(self, disabled: bool = False):
        super().__init__(label="Next ▶", style=discord.ButtonStyle.secondary, row=1, disabled=disabled)
    
    async def callback(self, interaction: discord.Interaction):
        view: TeamRemoveView = self.view
        new_view = TeamRemoveView(view.game, view.all_teams, view.page + 1)
        await interaction.response.edit_message(view=new_view)


class Verification(commands.Cog):
    """Player verification system."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    async def cog_load(self):
        self.bot.add_view(VerificationPanel())
    
    @app_commands.command(name="verifypanel", description="Send the verification panel")
    @app_commands.checks.has_permissions(administrator=True)
    async def verifypanel(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="✅ Player Verification",
            description="Verify your team registration.\n\n"
                        "• **Verify** — Register for your team\n"
                        "• **Unverify** — Leave your current team\n"
                        "• **My Status** — View your verifications",
            color=discord.Color.green()
        )
        await interaction.channel.send(embed=embed, view=VerificationPanel())
        await interaction.response.send_message("✅ Verification panel sent!", ephemeral=True)
    
    @app_commands.command(name="mystatus", description="View your verification status")
    async def mystatus(self, interaction: discord.Interaction):
        registrations = await db.fetchall(
            """SELECT t.game_name, t.team_name, pr.ign FROM player_registrations pr
               JOIN teams t ON pr.team_id = t.id
               WHERE pr.discord_id = %s
               ORDER BY t.game_name""",
            (interaction.user.id,)
        )
        
        if not registrations:
            await interaction.response.send_message("❌ You're not verified for any team.", ephemeral=True)
            return
        
        lines = [f"• **{r['game_name']}**: {r['team_name']} — `{r['ign']}`" for r in registrations]
        embed = discord.Embed(title="Your Verification Status", description="\n".join(lines), color=discord.Color.green())
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # ============ TEAM MANAGEMENT ============
    
    teams_group = app_commands.Group(name="teams", description="Manage teams")
    
    @teams_group.command(name="add", description="Add teams (comma-separated)")
    @app_commands.describe(game="The game", team_names="Team names, comma-separated")
    @app_commands.checks.has_permissions(administrator=True)
    async def teams_add(self, interaction: discord.Interaction, game: Literal["MLBB", "CODM"], team_names: str):
        names = [n.strip() for n in team_names.split(",") if n.strip()]
        if not names:
            await interaction.response.send_message("❌ No team names provided.", ephemeral=True)
            return
        
        added, duplicates = [], []
        for name in names:
            try:
                await db.execute("INSERT INTO teams (game_name, team_name) VALUES (%s, %s)", (game, name))
                added.append(name)
            except:
                duplicates.append(name)
        
        msg = []
        if added: msg.append(f"✅ Added: {', '.join(added)}")
        if duplicates: msg.append(f"⚠️ Exists: {', '.join(duplicates)}")
        await interaction.response.send_message(f"**{game}**\n" + "\n".join(msg), ephemeral=True)
    
    @teams_group.command(name="remove", description="Remove teams via selection")
    @app_commands.describe(game="The game")
    @app_commands.checks.has_permissions(administrator=True)
    async def teams_remove(self, interaction: discord.Interaction, game: Literal["MLBB", "CODM"]):
        teams = await db.fetchall("SELECT id, team_name FROM teams WHERE game_name = %s ORDER BY LOWER(team_name)", (game,))
        if not teams:
            await interaction.response.send_message(f"❌ No teams for **{game}**.", ephemeral=True)
            return
        
        view = TeamRemoveView(game, teams)
        await interaction.response.send_message(f"**Remove {game} Teams**\nSelect teams:", view=view, ephemeral=True)
    
    @teams_group.command(name="list", description="List all teams")
    @app_commands.describe(game="The game")
    @app_commands.checks.has_permissions(administrator=True)
    async def teams_list(self, interaction: discord.Interaction, game: Literal["MLBB", "CODM"]):
        teams = await db.fetchall(
            """SELECT t.team_name, COUNT(pr.id) as cnt FROM teams t
               LEFT JOIN player_registrations pr ON t.id = pr.team_id
               WHERE t.game_name = %s GROUP BY t.id ORDER BY t.team_name""",
            (game,)
        )
        if not teams:
            await interaction.response.send_message(f"❌ No teams for **{game}**.", ephemeral=True)
            return
        
        lines = [f"• {t['team_name']} ({t['cnt']} players)" for t in teams]
        embed = discord.Embed(title=f"{game} Teams", description="\n".join(lines), color=discord.Color.blue())
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # ============ LEAGUE OPS ============
    
    @app_commands.command(name="mention", description="Mention all players in a team")
    @app_commands.describe(game="The game", team_name="The team")
    @app_commands.checks.has_permissions(administrator=True)
    async def mention(self, interaction: discord.Interaction, game: Literal["MLBB", "CODM"], team_name: str):
        players = await db.fetchall(
            """SELECT pr.discord_id FROM player_registrations pr
               JOIN teams t ON pr.team_id = t.id
               WHERE t.game_name = %s AND t.team_name = %s""",
            (game, team_name)
        )
        if not players:
            await interaction.response.send_message(f"❌ No players for **{team_name}** ({game}).", ephemeral=True)
            return
        
        mentions = " ".join([f"<@{p['discord_id']}>" for p in players])
        await interaction.response.send_message(f"**{team_name}** ({game}):\n{mentions}")
    
    @app_commands.command(name="roster", description="View team roster")
    @app_commands.describe(game="The game", team_name="The team")
    @app_commands.checks.has_permissions(administrator=True)
    async def roster(self, interaction: discord.Interaction, game: Literal["MLBB", "CODM"], team_name: str):
        players = await db.fetchall(
            """SELECT pr.discord_id, pr.ign FROM player_registrations pr
               JOIN teams t ON pr.team_id = t.id
               WHERE t.game_name = %s AND t.team_name = %s""",
            (game, team_name)
        )
        if not players:
            await interaction.response.send_message(f"❌ No players for **{team_name}** ({game}).", ephemeral=True)
            return
        
        lines = []
        for p in players:
            member = interaction.guild.get_member(p["discord_id"])
            ign = f" — `{p['ign']}`" if p["ign"] else ""
            discord_id = p["discord_id"]
            display = member.display_name if member else f"<@{discord_id}>"
            lines.append(f"• {display}{ign}")
        
        embed = discord.Embed(title=f"{team_name} ({game})", description="\n".join(lines[:25]), color=discord.Color.blue())
        embed.set_footer(text=f"{len(players)} player(s)")
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @mention.autocomplete("team_name")
    @roster.autocomplete("team_name")
    async def team_autocomplete(self, interaction: discord.Interaction, current: str):
        game = None
        for opt in interaction.data.get("options", []):
            if opt["name"] == "game":
                game = opt["value"]
                break
        if not game:
            return []
        
        teams = await db.fetchall("SELECT team_name FROM teams WHERE game_name = %s ORDER BY team_name", (game,))
        return [app_commands.Choice(name=t["team_name"], value=t["team_name"]) for t in teams if current.lower() in t["team_name"].lower()][:25]


async def setup(bot: commands.Bot):
    await bot.add_cog(Verification(bot))
