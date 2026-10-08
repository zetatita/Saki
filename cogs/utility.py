import discord
from discord.ext import commands

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.snipes = {}

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        self.snipes[message.channel.id] = (
            message.content,
            message.author,
            message.created_at
        )

  

    @commands.command(name="userinfo", aliases=["ui", "whois"])
    async def userinfo(self, ctx, member: discord.Member = None):
        """Muestra información del usuario. Uso: ,userinfo @usuario"""
        member = member or ctx.author
        roles = [role.mention for role in member.roles[1:]] or ["Ninguno"]
        
        embed = discord.Embed(color=0x2b2d31)
        embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="ID", value=member.id, inline=True)
        embed.add_field(name="Registro", value=member.created_at.strftime("%d/%m/%Y"), inline=True)
        embed.add_field(name="Ingreso", value=member.joined_at.strftime("%d/%m/%Y"), inline=True)
        embed.add_field(name=f"Roles [{len(roles)}]", value=", ".join(roles), inline=False)
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Utility(bot))
