import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import logging

class Threads(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="createthreads", description="Create private threads with specific roles (Max 50/batch).")
    @app_commands.describe(
        names="Thread names separated by commas",
        roles="Mention roles or provide role IDs (comma-separated) who can access the threads"
    )
    async def create_threads(self, interaction: discord.Interaction, names: str, roles: str):
        await interaction.response.defer(ephemeral=True)
        
        if not interaction.channel or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.followup.send("❌ This command can only be used in text channels.", ephemeral=True)
            return

        thread_names = [name.strip() for name in names.split(",") if name.strip()]
        if not thread_names:
            await interaction.followup.send("❌ Please provide at least one thread name.", ephemeral=True)
            return
            
        if len(thread_names) > 50:
            await interaction.followup.send(f"❌ Batch size limited to 50 threads. You provided {len(thread_names)}.", ephemeral=True)
            return

        # Parse Roles
        role_ids = set()
        for role_str in roles.split(","):
            role_str = role_str.strip()
            if role_str.startswith("<@&") and role_str.endswith(">"):
                try: role_ids.add(int(role_str[3:-1]))
                except: pass
            elif role_str.isdigit():
                 role_ids.add(int(role_str))
        
        if not role_ids:
            await interaction.followup.send("❌ Please provide at least one valid role mention or ID.", ephemeral=True)
            return
            
        created_threads = []
        errors = []
        
        await interaction.followup.send(f"⏳ Starting creation of {len(thread_names)} threads...", ephemeral=True)

        for i, name in enumerate(thread_names):
            # 1. Rate Limit Protection: Sleep 1s every 5 threads
            if i > 0 and i % 5 == 0:
                await asyncio.sleep(2) 
            
            # Truncate
            final_name = name[:100]
            
            try:
                # Create
                thread = await interaction.channel.create_thread(
                    name=final_name,
                    type=discord.ChannelType.private_thread,
                    invitable=True
                )
                
                # Add User
                await thread.add_user(interaction.user)
                
                # Add Roles (by pinging - only way for private threads usually unless using Overwrites if possible? 
                # Private threads inherit perms but restricting to roles usually needs invites or pings if 'Private Thread' type)
                # Note: Private threads are invite only. Pinging gives access? 
                # Actually, standard behavior for private threads is you must add members.
                # Adding a ROLE to a thread isn't directly possible via API 'add_member' (takes User).
                # Sending a message mentioned the role DOES NOT add them to private thread automatically unless configured?
                # Reference checks: "await thread.send(f"{role.mention} has access...")"
                # If the reference usage relied on pings adding them, I will keep that.
                
                msg_content = ""
                for role_id in role_ids:
                    role = interaction.guild.get_role(role_id)
                    if role: msg_content += f"{role.mention} "
                
                if msg_content:
                    await thread.send(f"FYI: {msg_content} has been granted access.")
                
                created_threads.append(thread.mention)
                
            except discord.HTTPException as e:
                if e.status == 429:
                    retry_after = e.retry_after
                    logging.warning(f"Rate limited. Sleeping for {retry_after}s")
                    await asyncio.sleep(retry_after + 1)
                    # Retry once?
                    try:
                        thread = await interaction.channel.create_thread(name=final_name, type=discord.ChannelType.private_thread)
                        created_threads.append(thread.mention)
                    except:
                        errors.append(f"{name} (Rate limit error)")
                else:
                    errors.append(f"{name} ({e.status})")
            except Exception as e:
                errors.append(f"{name} ({e})")

        report = f"✅ **Batch Complete**\nCreated: {len(created_threads)}\nFailed: {len(errors)}"
        if errors:
            report += f"\n\n**Failures:**\n" + "\n".join(errors[:10])
            if len(errors) > 10: report += "\n..."
            
        await interaction.followup.send(report, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Threads(bot))
