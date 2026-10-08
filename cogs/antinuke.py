import discord
from discord.ext import commands

def is_antinuke_or_admin():
    async def predicate(ctx):
        if ctx.author.guild_permissions.administrator:
            return True
        if any(role.name.lower() == "antinuke" for role in ctx.author.roles):
            return True
        return False
    return commands.check(predicate)

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

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            embed = discord.Embed(
                description="### **Acceso Denegado**\n\nNo tienes el rol de **Antinuke** ni permisos de Administrador para usar este comando.",
                color=0x1e1f22
            )
            embed.set_author(name=f"{self.bot.user.name} seguridad", icon_url=self.bot.user.display_avatar.url)
            await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="lock")
    @commands.has_permissions(manage_channels=True)
    async def lock(self, ctx):
        try:
            await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
            embed = discord.Embed(
                description=f"✅ {ctx.author.mention}: Se aplicó **bloqueo** a {ctx.channel.mention}. Se siguen aplicando los permisos específicos de roles y miembros.",
                color=0x2ecc71
            )
            await ctx.reply(embed=embed, mention_author=False)
        except Exception as e:
            await ctx.reply(f"❌ Error al bloquear el canal: `{e}`", mention_author=False)

    @commands.command(name="unlock")
    @commands.has_permissions(manage_channels=True)
    async def unlock(self, ctx):
        try:
            await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
            embed = discord.Embed(
                description=f"✅ {ctx.author.mention}: Se aplicó **desbloqueo** a {ctx.channel.mention}. Se siguen aplicando los permisos específicos de roles y miembros.",
                color=0x2ecc71
            )
            await ctx.reply(embed=embed, mention_author=False)
        except Exception as e:
            await ctx.reply(f"❌ Error al desbloquear el canal: `{e}`", mention_author=False)

    @commands.command(name="hide")
    @commands.has_permissions(manage_channels=True)
    async def hide(self, ctx):
        try:
            await ctx.channel.set_permissions(ctx.guild.default_role, view_channel=False)
            embed = discord.Embed(
                description=f"✅ {ctx.author.mention}: Se aplicó **ocultación** a {ctx.channel.mention}. Se siguen aplicando los permisos específicos de roles y miembros.",
                color=0x2ecc71
            )
            await ctx.reply(embed=embed, mention_author=False)
        except Exception as e:
            await ctx.reply(f"❌ Error al ocultar el canal: `{e}`", mention_author=False)

    @commands.command(name="unhide")
    @commands.has_permissions(manage_channels=True)
    async def unhide(self, ctx):
        try:
            await ctx.channel.set_permissions(ctx.guild.default_role, view_channel=True)
            embed = discord.Embed(
                description=f"✅ {ctx.author.mention}: Se aplicó **visibilidad** a {ctx.channel.mention}. Se siguen aplicando los permisos específicos de roles y miembros.",
                color=0x2ecc71
            )
            await ctx.reply(embed=embed, mention_author=False)
        except Exception as e:
            await ctx.reply(f"❌ Error al mostrar el canal: `{e}`", mention_author=False)

    @commands.command(name="nuke")
    @is_antinuke_or_admin()
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

            # Funciona tanto para canales de texto como de voz
            new_channel = await channel.clone(reason=f"Nuke ejecutado por {ctx.author}")
            await new_channel.edit(position=position)
            
            await channel.delete()

            if isinstance(new_channel, discord.TextChannel):
                await new_channel.send(f"✅ Canal reiniciado correctamente por {ctx.author.mention}.")
        else:
            await message.edit(content="Acción de nuke cancelada.", view=None)

    @commands.command(name="hb")
    @is_antinuke_or_admin()
    async def hb(self, ctx, *, args=None):
        embed = discord.Embed(
            description="### **Sistema Antinuke**\n\nComando `hb` ejecutado correctamente.",
            color=0x1e1f22
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="hblist", aliases=["hb lis"])
    @is_antinuke_or_admin()
    async def hblist(self, ctx):
        embed = discord.Embed(
            description="### **Lista de HB (Antinuke)**\n\nNo hay registros activos actualmente.",
            color=0x1e1f22
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="unban")
    @is_antinuke_or_admin()
    async def unban(self, ctx, user_id: int):
        try:
            user = await self.bot.fetch_user(user_id)
            await ctx.guild.unban(user, reason=f"Desbaneado por {ctx.author} (Antinuke)")
            embed = discord.Embed(
                description=f"### **Desbaneo Exitoso**\n\nSe ha retirado el baneo de **{user}** correctamente.",
                color=0x1e1f22
            )
            await ctx.reply(embed=embed, mention_author=False)
        except Exception:
            await ctx.reply("No se pudo encontrar al usuario o ocurrió un error al intentar desbanearlo.", mention_author=False)

async def setup(bot):
    await bot.add_cog(Antinuke(bot))
