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
        self.add_item(ScheduledEmbedSelect(scheduled_list))

class ScheduledEmbedSelect(ui.Select):
    def __init__(self, scheduled_list):
        options = []
        # scheduled_list is list of dict from DB/JSON
        for entry in scheduled_list[:25]:
            lbl = f"{entry.get('identifier')} - {entry.get('schedule_for')}"
            options.append(discord.SelectOption(label=lbl, value=entry.get('identifier')))
            
        super().__init__(placeholder="Select an embed to cancel...", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.user.id:
            await interaction.response.send_message("❌ Not your session.", ephemeral=True)
            return

        identifier = self.values[0]
        # Call cog method to remove
        await self.view.cog.cancel_scheduled_embed_action(interaction, identifier)
