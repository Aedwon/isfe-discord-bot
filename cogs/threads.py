import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import logging


class Threads(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="createthreads", description="Create numbered private threads with specific roles (Max 50)")
    @app_commands.describe(
        prefix="Thread name prefix (e.g., 'Match' creates Match 1, Match 2...)",
        count="Number of threads to create (1-50)",
        roles="Mention roles or provide role IDs (comma-separated) who can access the threads"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def create_threads(self, interaction: discord.Interaction, prefix: str, count: int, roles: str):
        await interaction.response.defer(ephemeral=True)
        
        if not interaction.channel or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.followup.send("❌ This command can only be used in text channels.", ephemeral=True)
            return

        if count < 1 or count > 50:
            await interaction.followup.send("❌ Count must be between 1 and 50.", ephemeral=True)
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
        
        # Generate thread names
        thread_names = [f"{prefix} {i}" for i in range(1, count + 1)]
        
        created_threads = []
        errors = []
        
        await interaction.followup.send(f"⏳ Creating {count} threads: `{prefix} 1` to `{prefix} {count}`...", ephemeral=True)

        for i, name in enumerate(thread_names):
            # Rate Limit Protection: Sleep 2s every 5 threads
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
                
                # Add Roles via ping
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
                    # Retry once
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
