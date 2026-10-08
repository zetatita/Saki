import aiosqlite
import discord
from discord.ext import commands
from database.db import DB_NAME
from cogs.embeds import parse_embed_script

class AutoResponder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="ar", aliases=["autoresponder"])
    @commands.has_permissions(manage_guild=True)
    async def add_ar(self, ctx, trigger: str, *, response: str):
        """Agrega una respuesta automática. Uso: ,ar hola {description: Hola {user.mention}}"""
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "INSERT OR REPLACE INTO autoresponders VALUES (?, ?, ?)",
                (ctx.guild.id, trigger.lower(), response)
            )
            await db.commit()
        await ctx.send(f"Autoresponder activado para la palabra: `{trigger.lower()}`")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        content = message.content.lower()

        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute(
                "SELECT trigger, response FROM autoresponders WHERE guild_id = ?",
                (message.guild.id,)
            ) as cursor:
                rows = await cursor.fetchall()
                for trigger, response in rows:
                    if trigger in content:
                        embed = parse_embed_script(response, message.author)
                        await message.channel.send(embed=embed)
                        break

async def setup(bot):
    await bot.add_cog(AutoResponder(bot))