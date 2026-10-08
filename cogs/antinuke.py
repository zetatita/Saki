import discord
from discord.ext import commands

class ConfirmView(discord.ui.View):
    def __init__(self, author: discord.Member):
        super().__init__(timeout=60)
        self.author = author
        self.value = None

    @discord.ui.button(label="Nuke", style=discord.ButtonStyle.danger, custom_id="nuke_confirm")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("No puedes usar este botón.", ephemeral=True)
            return
        self.value = True
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, custom_id="nuke_cancel")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("No puedes usar este botón.", ephemeral=True)
            return
        self.value = False
        self.stop()

class Antinuke(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="nuke")
    @commands.has_permissions(manage_channels=True)
    async def nuke(self, ctx):
        view = ConfirmView(ctx.author)
        message = await ctx.send(
            content="Are you sure that you want to **nuke** this **channel**?", 
            view=view
        )

        await view.wait()

        if view.value is None:
            await message.edit(content="El tiempo para confirmar el nuke ha expirado.", view=None)
            return

        if view.value:
            channel = ctx.channel
            position = channel.position

            new_channel = await channel.clone(reason=f"Nuke ejecutado por {ctx.author}")
            await new_channel.edit(position=position)
            
            await channel.delete()

            if isinstance(new_channel, discord.TextChannel):
                await new_channel.send(f"✅ Canal reiniciado correctamente por {ctx.author.mention}.")
        else:
            await message.edit(content="Acción de nuke cancelada.", view=None)

async def setup(bot):
    await bot.add_cog(Antinuke(bot))
