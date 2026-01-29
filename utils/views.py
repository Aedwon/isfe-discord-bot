import discord
from discord import ui
import asyncio

class ConfirmView(ui.View):
    def __init__(self, interaction: discord.Interaction, on_confirm, confirm_args=(), timeout=60):
        super().__init__(timeout=timeout)
        self.interaction = interaction
        self.on_confirm = on_confirm
        self.confirm_args = confirm_args
        self.value = None

    async def on_timeout(self):
        # Disable buttons
        for child in self.children:
            child.disabled = True
        try:
            await self.interaction.edit_original_response(view=self)
        except:
            pass

    @ui.button(label="Confirm", style=discord.ButtonStyle.green, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.interaction.user.id:
            await interaction.response.send_message("❌ You cannot invoke this action.", ephemeral=True)
            return
        
        self.value = True
        for child in self.children:
            child.disabled = True
        
        await interaction.response.edit_message(view=self)
        
        # Execute callback
        if self.on_confirm:
            if asyncio.iscoroutinefunction(self.on_confirm):
                await self.on_confirm(*self.confirm_args)
            else:
                self.on_confirm(*self.confirm_args)

    @ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.interaction.user.id:
            await interaction.response.send_message("❌ You cannot invoke this action.", ephemeral=True)
            return
            
        self.value = False
        for child in self.children:
            child.disabled = True
            
        await interaction.response.edit_message(content="❌ Action cancelled.", view=self, embed=None)

class NicknameResetConfirmView(ConfirmView):
     def __init__(self, interaction, affected_members, query, callback):
        super().__init__(interaction, on_confirm=callback, confirm_args=(interaction, affected_members, query))

class CancelScheduledEmbedView(ui.View):
    def __init__(self, scheduled_list, cog, user):
        super().__init__(timeout=60)
        self.cog = cog
        self.user = user
        self.scheduled_list = scheduled_list
        self.add_item(ScheduledEmbedSelect(scheduled_list))
    
    @ui.button(label="Cancel Selected", style=discord.ButtonStyle.danger, row=1)
    async def cancel_button(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ Not your session.", ephemeral=True)
            return
        
        select = self.children[0]  # The select menu
        if not hasattr(select, 'values') or not select.values:
            await interaction.response.send_message("❌ No embeds selected.", ephemeral=True)
            return
        
        cancelled = []
        for identifier in select.values:
            await self.cog.cancel_scheduled_embed_action_silent(identifier)
            cancelled.append(identifier)
        
        await interaction.response.edit_message(
            content=f"✅ Cancelled {len(cancelled)} embed(s): {', '.join(cancelled)}",
            view=None
        )

class ScheduledEmbedSelect(ui.Select):
    def __init__(self, scheduled_list):
        options = []
        for entry in scheduled_list[:25]:
            lbl = f"{entry.get('identifier')} - {entry.get('schedule_for')}"
            options.append(discord.SelectOption(label=lbl[:100], value=entry.get('identifier')))
        
        super().__init__(
            placeholder="Select embed(s) to cancel...", 
            min_values=1, 
            max_values=len(options),
            options=options,
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.user.id:
            await interaction.response.send_message("❌ Not your session.", ephemeral=True)
            return
        
        count = len(self.values)
        await interaction.response.send_message(
            f"✅ Selected {count} embed(s). Click **Cancel Selected** to confirm.",
            ephemeral=True
        )

