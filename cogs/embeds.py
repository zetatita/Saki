import re
import discord
from discord.ext import commands

def parse_embed_script(script: str, author: discord.Member) -> discord.Embed:
    """Convierte un script estilo Bleed en un objeto discord.Embed."""
    guild = author.guild
    
    # Sustitución de variables de entorno
    script = (script
        .replace("{user}", str(author))
        .replace("{user.mention}", author.mention)
        .replace("{user.name}", author.name)
        .replace("{user.avatar}", author.display_avatar.url)
        .replace("{server.name}", guild.name)
        .replace("{server.count}", str(guild.member_count))
    )

    embed = discord.Embed()

    # Extracción de campos mediante expresiones regulares
    title = re.search(r"\{title:\s*(.*?)\}", script, re.DOTALL)
    description = re.search(r"\{description:\s*(.*?)\}", script, re.DOTALL)
    color = re.search(r"\{color:\s*#?([A-Fa-f0-9]{6})\}", script)
    image = re.search(r"\{image:\s*(.*?)\}", script)
    thumbnail = re.search(r"\{thumbnail:\s*(.*?)\}", script)
    footer = re.search(r"\{footer:\s*(.*?)\}", script)

    if title: 
        embed.title = title.group(1).strip()
    if description: 
        embed.description = description.group(1).strip()
    if color: 
        embed.color = int(color.group(1), 16)
    else:
        embed.color = 0x2b2d31
    if image: 
        embed.set_image(url=image.group(1).strip())
    if thumbnail: 
        embed.set_thumbnail(url=thumbnail.group(1).strip())
    if footer: 
        embed.set_footer(text=footer.group(1).strip())

    return embed

class Embeds(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="embed", aliases=["ce"])
    @commands.has_permissions(manage_messages=True)
    async def create_embed(self, ctx, *, script: str):
        """Crea un embed personalizado. Uso: ,embed {title: Hola} {description: Bienvenido {user.mention}}"""
        try:
            embed = parse_embed_script(script, ctx.author)
            await ctx.send(embed=embed)
            await ctx.message.delete()
        except Exception as e:
            await ctx.send(f"Error al procesar el embed: `{e}`", delete_after=5)

async def setup(bot):
    await bot.add_cog(Embeds(bot))