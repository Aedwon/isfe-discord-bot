import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import base64
import random
import string
import datetime
import asyncio
from urllib.parse import urlparse, parse_qs, quote
from io import BytesIO
import logging
from database.db import db
from utils.constants import TZ_MANILA
from utils.views import CancelScheduledEmbedView

def generate_identifier(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def discohook_to_view(components_data):
    if not components_data: return None
    view = discord.ui.View(timeout=None)
    for row in components_data:
        for comp in row.get("components", []):
            t = comp.get("type")
            if t == 2: # Button
                style = comp.get("style", 1)
                label = comp.get("label")
                url = comp.get("url")
                disabled = comp.get("disabled", False)
                emoji = comp.get("emoji", {}).get("name") if comp.get("emoji") else None
                
                if style == 5 and url:
                    view.add_item(discord.ui.Button(style=discord.ButtonStyle.link, label=label, url=url, emoji=emoji, disabled=disabled))
                else:
                    view.add_item(discord.ui.Button(style=discord.ButtonStyle(style), label=label, custom_id=comp.get("custom_id"), emoji=emoji, disabled=disabled))
            elif t == 3: # Select
                options = [discord.SelectOption(label=o["label"], value=o["value"], description=o.get("description"), emoji=o.get("emoji", {}).get("name"), default=o.get("default", False)) for o in comp.get("options", [])]
                view.add_item(discord.ui.Select(custom_id=comp.get("custom_id"), placeholder=comp.get("placeholder"), min_values=1, max_values=1, options=options, disabled=comp.get("disabled", False)))
    return view if len(view.children) > 0 else None

class Embeds(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.schedule_loop.start()

    def cog_unload(self):
        self.schedule_loop.cancel()

    @tasks.loop(minutes=1)
    async def schedule_loop(self):
        # Fetch pending tasks due now (or in past)
        query = "SELECT identifier, channel_id, user_id, content, embed_json FROM scheduled_embeds WHERE status = 'pending' AND schedule_for <= NOW()"
        rows = await db.fetchall(query)
        
        for row in rows:
            try:
                channel = self.bot.get_channel(row['channel_id'])
                if not channel:
                    channel = await self.bot.fetch_channel(row['channel_id'])
                
                data = json.loads(row['embed_json'])
                embeds = [discord.Embed.from_dict(e) for e in data.get("embeds", [])]
                view = discohook_to_view(data.get("components", []))
                content = row['content']
                
                await channel.send(content=content, embeds=embeds, view=view)
                
                # Mark sent
                await db.execute("UPDATE scheduled_embeds SET status = 'sent' WHERE identifier = %s", (row['identifier'],))
                
            except Exception as e:
                logging.error(f"Failed to send scheduled embed {row['identifier']}: {e}")
                await db.execute("UPDATE scheduled_embeds SET status = 'failed' WHERE identifier = %s", (row['identifier'],))

    @schedule_loop.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()

    async def _process_link(self, link):
        try:
            parsed = urlparse(link)
            qs = parse_qs(parsed.query)
            encoded = qs.get("data", [None])[0]
            if not encoded: return None
            
            # Padding
            missing = len(encoded) % 4
            if missing: encoded += "=" * (4 - missing)
            
            decoded = base64.urlsafe_b64decode(encoded).decode("utf-8")
            data = json.loads(decoded)
            
            # Discohook format structure
            msg_data = data["messages"][0]["data"]
            return msg_data
        except Exception as e:
            logging.error(f"Link parse error: {e}")
            return None

    @app_commands.command(name="send_embed", description="Send embed from Discohook link.")
    async def send_embed(self, interaction: discord.Interaction, channel: discord.TextChannel, link: str, schedule_for_minutes: int = 0):
        # Using minutes offset for simplicity in port, can enhance to absolute time if needed
        data = await self._process_link(link)
        if not data:
            await interaction.response.send_message("❌ Invalid link.", ephemeral=True)
            return

        content = data.get("content", "")
        embeds_list = data.get("embeds", [])
        components_list = data.get("components", [])

        if schedule_for_minutes > 0:
            schedule_time = datetime.datetime.now() + datetime.timedelta(minutes=schedule_for_minutes)
            identifier = generate_identifier()
            full_json = json.dumps({"embeds": embeds_list, "components": components_list})
            
            await db.execute(
                "INSERT INTO scheduled_embeds (identifier, channel_id, user_id, content, embed_json, schedule_for, status) VALUES (%s, %s, %s, %s, %s, %s, 'pending')",
                (identifier, channel.id, interaction.user.id, content, full_json, schedule_time)
            )
            await interaction.response.send_message(f"✅ Scheduled for {schedule_time} (ID: {identifier})", ephemeral=True)
        else:
            embeds = [discord.Embed.from_dict(e) for e in embeds_list]
            view = discohook_to_view(components_list)
            await channel.send(content=content, embeds=embeds, view=view)
            await interaction.response.send_message("✅ Sent.", ephemeral=True)

    @app_commands.command(name="cancel_embed", description="Cancel a scheduled embed.")
    async def cancel_embed(self, interaction: discord.Interaction):
        # Get user's pending
        rows = await db.fetchall("SELECT identifier, schedule_for FROM scheduled_embeds WHERE user_id = %s AND status = 'pending'", (interaction.user.id,))
        if not rows:
            await interaction.response.send_message("❌ No pending embeds found.", ephemeral=True)
            return
            
        view = CancelScheduledEmbedView(rows, self, interaction.user)
        await interaction.response.send_message("Select embed to cancel:", view=view, ephemeral=True)

    async def cancel_scheduled_embed_action(self, interaction, identifier):
        await db.execute("DELETE FROM scheduled_embeds WHERE identifier = %s", (identifier,))
        await interaction.response.send_message(f"✅ Cancelled embed {identifier}.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Embeds(bot))
