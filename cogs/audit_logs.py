import discord
from discord.ext import commands
import aiosqlite
from config import DB_NAME

class AuditLogs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def init_db(self):
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS log_channels (
                    guild_id INTEGER,
                    log_type TEXT,
                    channel_id INTEGER,
                    PRIMARY KEY (guild_id, log_type)
                )
            """)
            await db.commit()

    async def cog_load(self):
        await self.init_db()

    async def get_log_channel(self, guild_id: int, log_type: str):
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute(
                "SELECT channel_id FROM log_channels WHERE guild_id = ? AND log_type = ?",
                (guild_id, log_type)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None

    # --- COMANDO UNIFICADO DE SETUP (ESTILO SAKI) ---
    @commands.command(name="setuplogs", aliases=["logssetup"])
    @commands.has_permissions(administrator=True)
    async def setuplogs(self, ctx):
        """Crea la categoría, los canales de logs de Saki y los registra automáticamente."""
        guild = ctx.guild
        
        # Permisos para mantener los canales privados
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, manage_channels=True)
        }
        if isinstance(ctx.author, discord.Member):
            overwrites[ctx.author] = discord.PermissionOverwrite(read_messages=True)

        try:
            # 1. Crear categoría y canales con la identidad de Saki
            category = await guild.create_category("saki logs", overwrites=overwrites)
            
            ch_moderadores = await guild.create_text_channel("solo-moderadores", category=category, overwrites=overwrites)
            ch_confi = await guild.create_text_channel("saki-confi", category=category, overwrites=overwrites)
            ch_members = await guild.create_text_channel("saki-members-logs", category=category, overwrites=overwrites)
            ch_channel = await guild.create_text_channel("saki-channel-logs", category=category, overwrites=overwrites)
            ch_vc = await guild.create_text_channel("saki-vc-logs", category=category, overwrites=overwrites)
            ch_txt = await guild.create_text_channel("saki-txt-logs", category=category, overwrites=overwrites)

            # 2. Registrar automáticamente en la base de datos
            async with aiosqlite.connect(DB_NAME) as db:
                channels_data = [
                    ("members", ch_members.id),
                    ("channels", ch_channel.id),
                    ("voice", ch_vc.id),
                    ("text", ch_txt.id)
                ]
                for log_type, ch_id in channels_data:
                    await db.execute(
                        """
                        INSERT INTO log_channels (guild_id, log_type, channel_id) 
                        VALUES (?, ?, ?)
                        ON CONFLICT(guild_id, log_type) DO UPDATE SET channel_id = excluded.channel_id
                        """,
                        (guild.id, log_type, ch_id)
                    )
                await db.commit()

            embed = discord.Embed(
                title="📂 **Saki Logs Setup Completado**",
                description=(
                    f"Se ha configurado todo automáticamente en la categoría **{category.name}**:\n"
                    f"• {ch_members.mention} (Miembros)\n"
                    f"• {ch_channel.mention} (Canales)\n"
                    f"• {ch_vc.mention} (Voz)\n"
                    f"• {ch_txt.mention} (Texto)\n"
                    f"• {ch_moderadores.mention} / {ch_confi.mention}"
                ),
                color=0x2b2d31
            )
            await ctx.reply(embed=embed, mention_author=False)

        except Exception as e:
            embed = discord.Embed(
                description=f"❌ Ocurrió un error al configurar los logs: `{e}`",
                color=0x2b2d31
            )
            await ctx.reply(embed=embed, mention_author=False)

    # --- LISTENERS DE LOGS (EMBEDS OSCUROS) ---
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        ch_id = await self.get_log_channel(member.guild.id, "members")
        if not ch_id: return
        channel = member.guild.get_channel(ch_id)
        if not channel: return

        embed = discord.Embed(title="📥 **Miembro Unido**", description=f"**{member}** se ha unido al servidor.", color=0x2b2d31)
        embed.add_field(name="ID", value=f"`{member.id}`", inline=True)
        embed.add_field(name="Creado", value=f"<t:{int(member.created_at.timestamp())}:R>", inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Total de miembros: {member.guild.member_count}")
        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        ch_id = await self.get_log_channel(member.guild.id, "members")
        if not ch_id: return
        channel = member.guild.get_channel(ch_id)
        if not channel: return

        embed = discord.Embed(title="📤 **Miembro Salió**", description=f"**{member}** ha dejado el servidor.", color=0x2b2d31)
        embed.add_field(name="ID", value=f"`{member.id}`", inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)
        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        ch_id = await self.get_log_channel(channel.guild.id, "channels")
        if not ch_id: return
        log_channel = channel.guild.get_channel(ch_id)
        if not log_channel: return

        embed = discord.Embed(title="📁 **Canal Creado**", description=f"Se ha creado el canal **{channel.name}** (`{channel.type}`).", color=0x2b2d31)
        embed.add_field(name="ID", value=f"`{channel.id}`", inline=True)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        ch_id = await self.get_log_channel(channel.guild.id, "channels")
        if not ch_id: return
        log_channel = channel.guild.get_channel(ch_id)
        if not log_channel: return

        embed = discord.Embed(title="🗑️ **Canal Eliminado**", description=f"Se ha eliminado el canal **{channel.name}**.", color=0x2b2d31)
        embed.add_field(name="ID", value=f"`{channel.id}`", inline=True)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        ch_id = await self.get_log_channel(member.guild.id, "voice")
        if not ch_id: return
        log_channel = member.guild.get_channel(ch_id)
        if not log_channel: return

        if before.channel is None and after.channel is not None:
            embed = discord.Embed(title="🔊 **Conexión a Voz**", description=f"**{member}** entró al canal de voz **{after.channel.name}**.", color=0x2b2d31)
            embed.set_thumbnail(url=member.display_avatar.url)
            await log_channel.send(embed=embed)
        elif before.channel is not None and after.channel is None:
            embed = discord.Embed(title="🔇 **Desconexión de Voz**", description=f"**{member}** salió del canal de voz **{before.channel.name}**.", color=0x2b2d31)
            embed.set_thumbnail(url=member.display_avatar.url)
            await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not message.guild or message.author.bot: return
        ch_id = await self.get_log_channel(message.guild.id, "text")
        if not ch_id: return
        log_channel = message.guild.get_channel(ch_id)
        if not log_channel: return

        embed = discord.Embed(title="💬 **Mensaje Eliminado**", description=f"Mensaje de **{message.author}** eliminado en {message.channel.mention}.", color=0x2b2d31)
        if message.content:
            embed.add_field(name="Contenido", value=f"```text\n{message.content[:1000]}\n```", inline=False)
        embed.set_thumbnail(url=message.author.display_avatar.url)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if not before.guild or before.author.bot or before.content == after.content: return
        ch_id = await self.get_log_channel(before.guild.id, "text")
        if not ch_id: return
        log_channel = before.guild.get_channel(ch_id)
        if not log_channel: return

        embed = discord.Embed(title="✏️ **Mensaje Editado**", description=f"Mensaje de **{before.author}** editado en {before.channel.mention}.", color=0x2b2d31)
        embed.add_field(name="Antes", value=f"```text\n{before.content[:500]}\n```", inline=False)
        embed.add_field(name="Después", value=f"```text\n{after.content[:500]}\n```", inline=False)
        embed.set_thumbnail(url=before.author.display_avatar.url)
        await log_channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(AuditLogs(bot))
