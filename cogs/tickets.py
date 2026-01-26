import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import io
import datetime
import pytz
import html
import re
from database.db import db
import logging
from utils.constants import TZ_MANILA, COLOR_GOLD, COLOR_ERROR, COLOR_SUCCESS

# --- Configuration & Constants ---
# These should ideally be in env or DB config, but hardcoded per reference for now
TICKET_PANEL_CHANNEL_ID = 1217135394471022753
TICKET_LOG_CHANNEL_ID = 1217142468403793941

ROLE_LEAGUE_OPS = 1453237544287473877
ROLE_REWARDS = 1453238047515742310
ROLE_CONTENT = 1170484589253365872
ROLE_OTHERS = 1453237544287473877 
SUPPORT_ROLE_ID = 1170167517449302147

TICKET_CATEGORIES = {
    "A": {"label": "League Operations", "desc": "Registration, Rules, Roster, Schedules", "emoji": "⚔️", "tag": "a", "role_id": ROLE_LEAGUE_OPS},
    "B": {"label": "Rewards & Payouts", "desc": "Diamonds, Monetary Prizes, Incentives", "emoji": "💎", "tag": "b", "role_id": ROLE_REWARDS},
    "C": {"label": "Contents & Socials", "desc": "PubMats, Logos, Stream Assets", "emoji": "🎨", "tag": "c", "role_id": ROLE_CONTENT},
    "D": {"label": "General & Tech Support", "desc": "Server Assistance, Bug Reports, Inquiries", "emoji": "🛠️", "tag": "d", "role_id": ROLE_OTHERS}
}

# --- HTML Transcript Generator (Ported from reference) ---
def generate_html_transcript(messages: list[discord.Message], channel_name: str) -> str:
    """Generates a beautiful HTML transcript of the chat history."""
    style = """
    <style>
        body { font-family: 'gg sans', 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #313338; color: #dbdee1; margin: 0; padding: 20px; }
        .header { border-bottom: 1px solid #3f4147; padding-bottom: 10px; margin-bottom: 20px; }
        .header h1 { color: #f2f3f5; margin: 0; font-size: 20px; }
        .chat-container { display: block; width: 100%; }
        .message-group { display: flex; margin-bottom: 16px; align-items: flex-start; width: 100%; }
        .avatar { width: 40px; height: 40px; border-radius: 50%; margin-right: 16px; flex-shrink: 0; background-color: #2b2d31; }
        .content { flex: 1; }
        .meta { display: flex; align-items: baseline; margin-bottom: 4px; }
        .username { font-weight: 500; color: #f2f3f5; margin-right: 8px; font-size: 16px; }
        .bot-tag { background-color: #5865f2; color: #fff; font-size: 10px; padding: 1px 4px; border-radius: 3px; vertical-align: middle; margin-left: 4px; }
        .timestamp { font-size: 12px; color: #949ba4; }
        .text { font-size: 16px; line-height: 1.375rem; white-space: pre-wrap; word-wrap: break-word; color: #dbdee1; }
        .text strong { font-weight: 700; color: #f2f3f5; }
        .text .mention { background-color: #3c4270; color: #c9cdfb; padding: 0 2px; border-radius: 3px; cursor: pointer; font-weight: 500;}
        .attachment img { max-width: 400px; max-height: 300px; border-radius: 4px; }
        a { color: #00a8fc; text-decoration: none; }
    </style>
    """
    
    html_content = f"""
    <!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>Transcript - {channel_name}</title>{style}</head><body>
         <div class="header"><h1>#{channel_name}</h1><p>Transcript generated on {datetime.datetime.now(TZ_MANILA).strftime('%Y-%m-%d %H:%M:%S')} (PHT)</p></div>
         <div class="chat-container">
    """
    for msg in messages:
        try:
            avatar = msg.author.display_avatar.url if msg.author.display_avatar else "https://cdn.discordapp.com/embed/avatars/0.png"
            username = html.escape(msg.author.display_name)
            ts = msg.created_at.astimezone(TZ_MANILA).strftime('%m/%d/%Y %I:%M %p')
            content = html.escape(msg.content or "")
            # Basic Mention Parsing
            content = re.sub(r'&lt;@!?(\d+)&gt;', r'<span class="mention">@\1</span>', content)
            
            attachments = ""
            for att in msg.attachments:
                if att.content_type and att.content_type.startswith('image/'):
                    attachments += f'<div class="attachment"><a href="{att.url}" target="_blank"><img src="{att.url}"></a></div>'
                else:
                    attachments += f'<div class="attachment"><a href="{att.url}" target="_blank">📄 {html.escape(att.filename)}</a></div>'

            html_content += f"""
            <div class="message-group">
                <img class="avatar" src="{avatar}">
                <div class="content">
                    <div class="meta"><span class="username">{username}</span><span class="timestamp">{ts}</span></div>
                    <div class="text">{content}</div>
                    {attachments}
                </div>
            </div>"""
        except: continue
    
    html_content += "</div></body></html>"
    return html_content

# --- UI Components ---
class TicketTopicSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=d["label"], description=d["desc"], emoji=d["emoji"], value=k) for k, d in TICKET_CATEGORIES.items()]
        super().__init__(placeholder="Select the category of your concern...", min_values=1, max_values=1, custom_id="ticket_category_select", options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_key = self.values[0]
        category_data = TICKET_CATEGORIES.get(selected_key)
        await interaction.response.send_modal(TicketModal(selected_key, category_data))

class TicketTopicView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(TicketTopicSelect())

class TicketCreateView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="📩 Create Ticket", style=discord.ButtonStyle.primary, custom_id="create_ticket_base")
    async def create_start(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Please select the category below:", view=TicketTopicView(), ephemeral=True)

class TicketModal(discord.ui.Modal):
    def __init__(self, category_key, category_data):
        super().__init__(title=f"New {category_data['label']} Ticket")
        self.category_key = category_key
        self.category_data = category_data
        self.ticket_subject = discord.ui.TextInput(label="Subject", placeholder="Briefly state your concern...", max_length=100)
        self.ticket_desc = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph, placeholder="Details...", max_length=1000)
        self.add_item(self.ticket_subject)
        self.add_item(self.ticket_desc)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        user = interaction.user
        
        # Determine Category Channel
        category_channel = interaction.channel.category
        if not category_channel:
            category_channel = discord.utils.get(guild.categories, name="🎟⎮tickets")

        if not category_channel:
             await interaction.followup.send("❌ Error: Could not determine category.", ephemeral=True)
             return

        # Check existing
        row = await db.fetchrow("SELECT channel_id FROM tickets WHERE creator_id = %s AND status = 'open' AND category = %s", (user.id, self.category_key))
        if row:
             ch = guild.get_channel(row['channel_id'])
             if ch:
                 await interaction.followup.send(f"❌ You already have a ticket of this type open: {ch.mention}", ephemeral=True)
                 return

        tag = self.category_data["tag"]
        channel_name = f"[{tag}]-{user.name}"
        
        # Permissions
        role_to_ping_id = self.category_data["role_id"]
        role_to_ping = guild.get_role(role_to_ping_id)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, manage_channels=True)
        }
        if role_to_ping: overwrites[role_to_ping] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
        
        try:
            ticket_channel = await guild.create_text_channel(channel_name, category=category_channel, overwrites=overwrites)
            
            # DB Insert
            await db.execute(
                "INSERT INTO tickets (channel_id, guild_id, creator_id, category, status) VALUES (%s, %s, %s, %s, 'open')",
                (ticket_channel.id, guild.id, user.id, self.category_key)
            )

            embed = discord.Embed(title=f"{self.category_data['emoji']} {self.category_data['label']}", description=f"**Subject:** {self.ticket_subject.value}\n\n{self.ticket_desc.value}", color=COLOR_GOLD)
            embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
            embed.set_footer(text=f"Ticket ID: {ticket_channel.id}")
            
            view = TicketActionsView()
            mention_text = role_to_ping.mention if role_to_ping else ""
            await ticket_channel.send(content=f"{user.mention} {mention_text}", embed=embed, view=view)
            await interaction.followup.send(f"✅ Ticket created: {ticket_channel.mention}", ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to create ticket: {e}", ephemeral=True)
            logging.error(f"Ticket creation error: {e}")

class TicketActionsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🛠 Claim Ticket", style=discord.ButtonStyle.success, custom_id="claim_ticket")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        row = await db.fetchrow("SELECT claimed_by, category FROM tickets WHERE channel_id = %s", (interaction.channel_id,))
        if not row: return
        
        if row['claimed_by']:
            await interaction.followup.send("❌ Already claimed.", ephemeral=True)
            return
            
        # Permission Check ( Simplified )
        # Real logic should check if user has access based on category role or admin
        await db.execute("UPDATE tickets SET claimed_by = %s WHERE channel_id = %s", (interaction.user.id, interaction.channel_id))
        
        embed = discord.Embed(description=f"✅ {interaction.user.mention} has claimed this ticket.", color=COLOR_SUCCESS)
        await interaction.channel.send(embed=embed)
        button.disabled = True
        button.label = f"Claimed by {interaction.user.display_name}"
        await interaction.message.edit(view=self)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CloseReasonModal())

class CloseReasonModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Close Ticket")
        self.reason = discord.ui.TextInput(label="Reason", placeholder="e.g. Solved", max_length=200)
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        # Log and Close
        channel = interaction.channel
        
        # Transcript
        messages = [m async for m in channel.history(limit=500, oldest_first=True)]
        html = generate_html_transcript(messages, channel.name)
        file = discord.File(io.StringIO(html), filename=f"transcript-{channel.name}.html")
        
        # Mark Closed in DB
        await db.execute("UPDATE tickets SET status = 'closed' WHERE channel_id = %s", (channel.id,))
        
        # Send Log
        # Send Log
        log_channel_id = None
        settings_row = await db.fetchrow("SELECT ticket_transcript_channel_id FROM guild_settings WHERE guild_id = %s", (interaction.guild.id,))
        if settings_row:
             log_channel_id = settings_row.get('ticket_transcript_channel_id')

        # Fallback to TICKET_LOG_CHANNEL_ID if configured or if no DB setting (legacy support)
        # But prefer DB.
        
        target_log_channel = None
        if log_channel_id:
             target_log_channel = interaction.guild.get_channel(log_channel_id)
        
        if target_log_channel:
            embed = discord.Embed(title="Ticket Closed", color=COLOR_ERROR, timestamp=datetime.datetime.now(TZ_MANILA))
            embed.add_field(name="Ticket", value=channel.name)
            embed.add_field(name="Closed By", value=interaction.user.mention)
            embed.add_field(name="Reason", value=self.reason.value)
            await target_log_channel.send(embed=embed, file=file)
            
        await channel.delete()

class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_ticket_reminders.start()

    def cog_unload(self):
        self.check_ticket_reminders.cancel()

    async def cog_load(self):
        self.bot.add_view(TicketCreateView())
        self.bot.add_view(TicketActionsView())

    @app_commands.command(name="setup_tickets", description="Force recreate the ticket panel.")
    @app_commands.describe(channel="Channel to post the panel in (default: current channel)")
    @app_commands.default_permissions(administrator=True)
    async def setup_tickets(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        target_channel = channel or interaction.channel
        
        if not target_channel:
             await interaction.response.send_message("❌ Could not determine target channel.", ephemeral=True)
             return

        embed = discord.Embed(
            title="Support Tickets",
            description="**How can we help you?**\n\nPlease select the category that best matches your concern from the dropdown menu below.",
            color=COLOR_GOLD
        )
        embed.set_footer(text="System developed by Aedwon")
        
        try:
            await target_channel.send(embed=embed, view=TicketCreateView())
            await interaction.response.send_message(f"✅ Panel created in {target_channel.mention}.", ephemeral=True)
        except discord.Forbidden:
             await interaction.response.send_message(f"❌ Missing permissions to send messages in {target_channel.mention}.", ephemeral=True)

    @app_commands.command(name="set_ticket_log_channel", description="Set the channel where ticket transcripts are sent.")
    @app_commands.describe(channel="Channel for transcripts")
    @app_commands.default_permissions(administrator=True)
    async def set_ticket_log_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)
        try:
            await db.execute(
                "INSERT INTO guild_settings (guild_id, ticket_transcript_channel_id) VALUES (%s, %s) ON DUPLICATE KEY UPDATE ticket_transcript_channel_id = %s",
                (interaction.guild.id, channel.id, channel.id)
            )
            await interaction.followup.send(f"✅ Ticket transcripts will be sent to {channel.mention}.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error saving setting: {e}", ephemeral=True)

    @tasks.loop(minutes=10)
    async def check_ticket_reminders(self):
        # Scan open tickets > 24h
        query = "SELECT channel_id, created_at FROM tickets WHERE status = 'open' AND reminded_24h = FALSE"
        rows = await db.fetchall(query)
        now = datetime.datetime.now()
        
        for row in rows:
            created = row['created_at']
            if (now - created).total_seconds() > 86400: # 24h
                channel = self.bot.get_channel(row['channel_id'])
                if channel:
                    await channel.send("⏳ **Reminder:** Unclaimed for 24h.")
                    await db.execute("UPDATE tickets SET reminded_24h = TRUE WHERE channel_id = %s", (row['channel_id'],))

    @check_ticket_reminders.before_loop
    async def before_reminders(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Tickets(bot))
