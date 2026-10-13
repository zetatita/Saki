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
            await interaction.response.send_message("❌ No puedes usar este botón.", ephemeral=True)
            return
        self.value = True
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, custom_id="nuke_cancel")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ No puedes usar este botón.", ephemeral=True)
            return
        self.value = False
        self.stop()

class Antinuke(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_server_owner(self, ctx) -> bool:
        """Verifica si quien ejecuta el comando es el dueño del servidor."""
        return ctx.guild and ctx.author.id == ctx.guild.owner_id

    async def send_owner_only_embed(self, ctx):
        """Envía el mensaje de advertencia exclusivo para el Dueño del Servidor."""
        embed = discord.Embed(
            description=f"⚠️ {ctx.author.mention}: **Solo el Propietario del Servidor** (`{ctx.guild.owner}`) puede configurar o gestionar el sistema Antinuke.",
            color=0x2b2d31
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="antinuke", aliases=["an"])
    async def antinuke(self, ctx):
        """Muestra el panel de control del Antinuke (Exclusivo para el Owner)."""
        if not self.is_server_owner(ctx):
            return await self.send_owner_only_embed(ctx)

        embed = discord.Embed(
            title="🛡️ **Antinuke System**",
            description=(
                "El sistema de **Antinuke** está activo y protegiendo este servidor.\n\n"
                "> **Estado del Servidor:** `Protegido`\n"
                "> **Acciones Monitoreadas:** `Kicks`, `Bans`, `Canales`, `Roles`, `Webhooks`, `Bots`\n\n"
                "⚠️ *Recuerda que solo el dueño del servidor puede modificar los parámetros de protección.*"
            ),
            color=0x2b2d31
        )
        embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon.url if ctx.guild.icon else self.bot.user.display_avatar.url)
        embed.set_footer(text=f"Propietario: {ctx.guild.owner}", icon_url=ctx.guild.owner.display_avatar.url)
        
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="nuke")
    @commands.has_permissions(manage_channels=True)
    async def nuke(self, ctx):
        """Clona y reinicia el canal actual limpiando sus mensajes."""
        view = ConfirmView(ctx.author)
        
        embed = discord.Embed(
            description="⚠️ ¿Estás seguro de que deseas **reiniciar (nuke)** este canal?",
            color=0x2b2d31
        )
        message = await ctx.reply(embed=embed, view=view, mention_author=False)

        await view.wait()

        if view.value is None:
            timeout_embed = discord.Embed(
                description="⏳ El tiempo para confirmar el nuke ha expirado.",
                color=0x2b2d31
            )
            await message.edit(embed=timeout_embed, view=None)
            return

        if view.value:
            channel = ctx.channel
            position = channel.position

            new_channel = await channel.clone(reason=f"Nuke ejecutado por {ctx.author}")
            await new_channel.edit(position=position)
            await channel.delete()

            if isinstance(new_channel, discord.TextChannel):
                done_embed = discord.Embed(
                    description=f"💣 Canal reiniciado correctamente por {ctx.author.mention}.",
                    color=0x2b2d31
                )
                await new_channel.send(embed=done_embed)
        else:
            cancel_embed = discord.Embed(
                description="❌ Acción de nuke cancelada.",
                color=0x2b2d31
            )
            await message.edit(embed=cancel_embed, view=None)

async def setup(bot):
    await bot.add_cog(Antinuke(bot))
