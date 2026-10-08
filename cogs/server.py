import discord
from discord.ext import commands
import time

class Server(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="ping")
    async def ping(self, ctx):
        """Muestra la latencia del bot."""
        start_time = time.monotonic()
        msg = await ctx.send("🏓 Calculando latencia...")
        end_time = time.monotonic()
        
        api_latency = round(self.bot.latency * 1000)
        bot_latency = round((end_time - start_time) * 1000)

        embed = discord.Embed(
            description=f"⚡ **API Latency:** `{api_latency}ms`\n⏱️ **Response Time:** `{bot_latency}ms`",
            color=0x2b2d31
        )
        await msg.edit(content=None, embed=embed)

    @commands.command(name="serverinfo", aliases=["si"])
    async def server_info(self, ctx):
        """Información detallada del servidor."""
        guild = ctx.guild
        embed = discord.Embed(title=f"🏰 {guild.name}", color=0x2b2d31)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        embed.add_field(name="ID", value=f"`{guild.id}`", inline=True)
        embed.add_field(name="Dueño", value=f"{guild.owner.mention}", inline=True)
        embed.add_field(name="Miembros", value=f"`{guild.member_count}`", inline=True)
        embed.add_field(name="Canales", value=f"`{len(guild.channels)}`", inline=True)
        embed.add_field(name="Roles", value=f"`{len(guild.roles)}`", inline=True)
        embed.add_field(name="Boosts", value=f"`{guild.premium_subscription_count}` (Nivel {guild.premium_tier})", inline=True)
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Server(bot))