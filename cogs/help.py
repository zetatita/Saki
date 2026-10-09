import discord
from discord.ext import commands

class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        # Reemplaza la URL de ejemplo con la de tu servidor oficial de Discord
        self.add_item(discord.ui.Button(label="Servidor oficial", url="https://discord.gg/tu-servidor", style=discord.ButtonStyle.link))

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help", aliases=["h"])
    async def help_command(self, ctx):
        embed = discord.Embed(
            title="Ayuda y soporte",
            description="Visita nuestro [servidor oficial](https://discord.gg/tu-servidor) para consultar los comandos y recibir ayuda.",
            color=0x1e1f22
        )
        view = HelpView()
        await ctx.reply(embed=embed, view=view, mention_author=False)

async def setup(bot):
    await bot.add_cog(Help(bot))
