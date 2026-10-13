import aiosqlite
import discord
from discord.ext import commands
import datetime
from config import DB_NAME

class AFK(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        """Crea la tabla de AFK en la base de datos al cargar el cog."""
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS afk_users (
                    guild_id INTEGER,
                    user_id INTEGER,
                    reason TEXT,
                    timestamp TIMESTAMP,
                    old_nickname TEXT,
                    PRIMARY KEY (guild_id, user_id)
                )
            """)
            await db.commit()

    # ==================== EVENTO: LISTENER DE MENSAJES ====================
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        async with aiosqlite.connect(DB_NAME) as db:
            # 1. Comprobar si el autor del mensaje está AFK para quitárselo
            async with db.execute(
                "SELECT reason, timestamp, old_nickname FROM afk_users WHERE guild_id = ? AND user_id = ?",
                (message.guild.id, message.author.id)
            ) as cursor:
                afk_data = await cursor.fetchone()

            if afk_data:
                # Quitar estado AFK de la base de datos
                await db.execute(
                    "DELETE FROM afk_users WHERE guild_id = ? AND user_id = ?",
                    (message.guild.id, message.author.id)
                )
                await db.commit()

                # Restaurar apodo anterior si es posible
                old_nick = afk_data[2]
                try:
                    await message.author.edit(nick=old_nick, reason="Removido estado AFK")
                except discord.HTTPException:
                    pass

                embed = discord.Embed(
                    description=f"👋 Bienvenido de vuelta {message.author.mention}, he retirado tu estado **AFK**.",
                    color=0x2b2d31
                )
                await message.channel.send(embed=embed, delete_after=6)

            # 2. Comprobar si el mensaje menciona a alguien que esté AFK
            if message.mentions:
                for mention in message.mentions:
                    if mention.bot or mention.id == message.author.id:
                        continue

                    async with db.execute(
                        "SELECT reason, timestamp FROM afk_users WHERE guild_id = ? AND user_id = ?",
                        (message.guild.id, mention.id)
                    ) as cursor:
                        mentioned_afk = await cursor.fetchone()

                    if mentioned_afk:
                        reason, afk_time_str = mentioned_afk
                        
                        # Formatear tiempo para Discord
                        afk_dt = datetime.datetime.fromisoformat(afk_time_str)
                        time_relative = f"<t:{int(afk_dt.timestamp())}:R>"

                        embed = discord.Embed(
                            description=f"💤 {mention.mention} está **AFK**: `{reason}` — {time_relative}",
                            color=0x2b2d31
                        )
                        await message.reply(embed=embed, mention_author=False)

    # ==================== COMANDO: ,afk ====================
    @commands.command(name="afk")
    async def afk_command(self, ctx, *, reason: str = "AFK"):
        """Establece el estado AFK para el usuario."""
        now = datetime.utils.utcnow() if hasattr(datetime, 'utils') else datetime.datetime.now(datetime.timezone.utc)
        old_nick = ctx.author.nick

        # Intentar agregar [AFK] al apodo
        new_nick = f"[AFK] {ctx.author.display_name}"
        if len(new_nick) > 32:
            new_nick = new_nick[:32]

        try:
            await ctx.author.edit(nick=new_nick, reason="Establecido estado AFK")
        except discord.HTTPException:
            pass

        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "INSERT OR REPLACE INTO afk_users (guild_id, user_id, reason, timestamp, old_nickname) VALUES (?, ?, ?, ?, ?)",
                (ctx.guild.id, ctx.author.id, reason, now.isoformat(), old_nick)
            )
            await db.commit()

        embed = discord.Embed(
            description=f"💤 {ctx.author.mention}: Tu estado ahora es **AFK** con el motivo: `{reason}`",
            color=0x2b2d31
        )
        await ctx.reply(embed=embed, mention_author=False)

async def setup(bot):
    await bot.add_cog(AFK(bot))
