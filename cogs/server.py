import discord
from discord.ext import commands
import time
import aiosqlite
from config import DB_NAME

class Server(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ---------------------------------------------------------
    # COMANDOS GENERALES (Ping & Serverinfo)
    # ---------------------------------------------------------
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

    # ---------------------------------------------------------
    # SISTEMA DE BIENVENIDA
    # ---------------------------------------------------------
    @commands.group(name="welcome", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def welcome(self, ctx):
        embed = discord.Embed(
            description="### **Sistema de Bienvenidas**\n\n```text\nSintaxis: ,welcome set <canal> <mensaje>\n         ,welcome remove\n```",
            color=0x1e1f22
        )
        await ctx.reply(embed=embed, mention_author=False)

    @welcome.command(name="set")
    @commands.has_permissions(administrator=True)
    async def welcome_set(self, ctx, channel: discord.TextChannel, *, message: str):
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("CREATE TABLE IF NOT EXISTS welcomes (guild_id INTEGER PRIMARY KEY, channel_id INTEGER, message TEXT)")
            await db.execute(
                "INSERT INTO welcomes (guild_id, channel_id, message) VALUES (?, ?, ?) ON CONFLICT(guild_id) DO UPDATE SET channel_id = ?, message = ?",
                (ctx.guild.id, channel.id, message, channel.id, message)
            )
            await db.commit()
        await ctx.message.add_reaction("👍")

    @welcome.command(name="remove", aliases=["delete"])
    @commands.has_permissions(administrator=True)
    async def welcome_remove(self, ctx):
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("DELETE FROM welcomes WHERE guild_id = ?", (ctx.guild.id,))
            await db.commit()
        await ctx.message.add_reaction("👍")

    # ---------------------------------------------------------
    # SISTEMA DE DESPEDIDAS (GOODBYE)
    # ---------------------------------------------------------
    @commands.group(name="goodbye", aliases=["despedida"], invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def goodbye(self, ctx):
        embed = discord.Embed(
            description="### **Sistema de Despedidas**\n\n```text\nSintaxis: ,goodbye set <canal> <mensaje>\n         ,goodbye remove\n```",
            color=0x1e1f22
        )
        await ctx.reply(embed=embed, mention_author=False)

    @goodbye.command(name="set")
    @commands.has_permissions(administrator=True)
    async def goodbye_set(self, ctx, channel: discord.TextChannel, *, message: str):
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("CREATE TABLE IF NOT EXISTS goodbyes (guild_id INTEGER PRIMARY KEY, channel_id INTEGER, message TEXT)")
            await db.execute(
                "INSERT INTO goodbyes (guild_id, channel_id, message) VALUES (?, ?, ?) ON CONFLICT(guild_id) DO UPDATE SET channel_id = ?, message = ?",
                (ctx.guild.id, channel.id, message, channel.id, message)
            )
            await db.commit()
        await ctx.message.add_reaction("👍")

    @goodbye.command(name="remove", aliases=["delete"])
    @commands.has_permissions(administrator=True)
    async def goodbye_remove(self, ctx):
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("DELETE FROM goodbyes WHERE guild_id = ?", (ctx.guild.id,))
            await db.commit()
        await ctx.message.add_reaction("👍")

    # ---------------------------------------------------------
    # SISTEMA DE BOOSTS (BOOSTMSG)
    # ---------------------------------------------------------
    @commands.group(name="boostmsg", aliases=["boost"], invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def boostmsg(self, ctx):
        embed = discord.Embed(
            description="### **Sistema de Mensajes de Boost**\n\n```text\nSintaxis: ,boostmsg set <canal> <mensaje>\n         ,boostmsg remove\n```",
            color=0x1e1f22
        )
        await ctx.reply(embed=embed, mention_author=False)

    @boostmsg.command(name="set")
    @commands.has_permissions(administrator=True)
    async def boostmsg_set(self, ctx, channel: discord.TextChannel, *, message: str):
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("CREATE TABLE IF NOT EXISTS boosts (guild_id INTEGER PRIMARY KEY, channel_id INTEGER, message TEXT)")
            await db.execute(
                "INSERT INTO boosts (guild_id, channel_id, message) VALUES (?, ?, ?) ON CONFLICT(guild_id) DO UPDATE SET channel_id = ?, message = ?",
                (ctx.guild.id, channel.id, message, channel.id, message)
            )
            await db.commit()
        await ctx.message.add_reaction("👍")

    @boostmsg.command(name="remove", aliases=["delete"])
    @commands.has_permissions(administrator=True)
    async def boostmsg_remove(self, ctx):
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("DELETE FROM boosts WHERE guild_id = ?", (ctx.guild.id,))
            await db.commit()
        await ctx.message.add_reaction("👍")

async def setup(bot):
    await bot.add_cog(Server(bot))
