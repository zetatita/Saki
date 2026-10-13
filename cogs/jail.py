import json
import aiosqlite
import discord
from discord.ext import commands
from database.db import DB_NAME

class Jail(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def send_jail_log(self, guild, action: str, member: discord.Member, moderator: discord.Member, reason: str = "Sin razón"):
        """Envía el registro/log al canal configurado en la base de datos."""
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT channel_id FROM mod_logs WHERE guild_id = ?", (guild.id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return  # No hay canal de logs configurado

                log_channel = guild.get_channel(row[0])
                if not log_channel:
                    return

                # Diseño Embed Estilo Bleed para Logs
                is_jail = action.lower() == "jail"
                embed = discord.Embed(
                    title=f"Case: {action.upper()}",
                    color=0xff4b4b if is_jail else 0x4caf50,
                    timestamp=discord.utils.utcnow()
                )
                embed.set_author(name=f"{member.name} ({member.id})", icon_url=member.display_avatar.url)
                embed.add_field(name="User", value=f"{member.mention}", inline=True)
                embed.add_field(name="Moderator", value=f"{moderator.mention}", inline=True)
                embed.add_field(name="Reason", value=f"`{reason}`", inline=False)
                embed.set_footer(text=f"Guild ID: {guild.id}")

                try:
                    await log_channel.send(embed=embed)
                except Exception:
                    pass

    @commands.command(name="jail")
    @commands.has_permissions(manage_roles=True)
    async def jail(self, ctx, member: discord.Member = None, *, reason: str = "Sin razón especificada"):
        """Aísla a un usuario guardando sus roles previos al estilo Bleed."""
        if member is None:
            embed = discord.Embed(
                title="Comando: jail",
                description="encarcelamiento: aplica esta acción a un miembro. Pon entre comillas los nombres o apodos con espacios.",
                color=0x2b2d31
            )
            embed.set_author(name=f"{ctx.bot.user.name} ayuda", icon_url=ctx.bot.user.display_avatar.url)
            embed.add_field(name="\u200b", value="```text\nSintaxis: ,jail <usuario> [motivo]\nEjemplo: ,jail @Juan Incumplir las reglas del servidor\n```", inline=False)
            return await ctx.reply(embed=embed, mention_author=False)

        if member == ctx.author:
            return await ctx.reply("❌ No puedes encarcelarte a ti mismo.", mention_author=False)
        if member.guild_permissions.administrator:
            return await ctx.reply("❌ No puedes encarcelar a un administrador del servidor.", mention_author=False)

        jail_role = discord.utils.get(ctx.guild.roles, name="Jailed")
        if not jail_role:
            return await ctx.reply("❌ No se encontró el rol **Jailed** en este servidor.", mention_author=False)

        user_roles = [r.id for r in member.roles if r != ctx.guild.default_role and not r.is_integration()]
        roles_json = json.dumps(user_roles)

        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS jail_data (
                    guild_id INTEGER,
                    user_id INTEGER,
                    saved_roles TEXT,
                    PRIMARY KEY (guild_id, user_id)
                )
            """)
            await db.execute(
                "INSERT OR REPLACE INTO jail_data (guild_id, user_id, saved_roles) VALUES (?, ?, ?)",
                (ctx.guild.id, member.id, roles_json)
            )
            await db.commit()

        try:
            await member.edit(roles=[jail_role], reason=f"Jail por {ctx.author}: {reason}")
            await ctx.message.add_reaction("👍")
            
            # Enviar Log
            await self.send_jail_log(ctx.guild, "Jail", member, ctx.author, reason)

        except discord.Forbidden:
            await ctx.reply("❌ No tengo permisos suficientes. Sube el rol del bot por encima de los usuarios.", mention_author=False)

    @commands.command(name="unjail")
    @commands.has_permissions(manage_roles=True)
    async def unjail(self, ctx, member: discord.Member = None, *, reason: str = "Sin razón especificada"):
        """Restaura los roles originales de un usuario liberado al estilo Bleed."""
        if member is None:
            embed = discord.Embed(
                title="Comando: unjail",
                description="liberación: aplica esta acción a un miembro. Pon entre comillas los nombres o apodos con espacios.",
                color=0x2b2d31
            )
            embed.set_author(name=f"{ctx.bot.user.name} ayuda", icon_url=ctx.bot.user.display_avatar.url)
            embed.add_field(name="\u200b", value="```text\nSintaxis: ,unjail <usuario>\nEjemplo: ,unjail @Juan\n```", inline=False)
            return await ctx.reply(embed=embed, mention_author=False)

        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute(
                "SELECT saved_roles FROM jail_data WHERE guild_id = ? AND user_id = ?",
                (ctx.guild.id, member.id)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return await ctx.reply("❌ El usuario no tiene registros de jail en la base de datos.", mention_author=False)

                role_ids = json.loads(row[0])
                await db.execute(
                    "DELETE FROM jail_data WHERE guild_id = ? AND user_id = ?",
                    (ctx.guild.id, member.id)
                )
                await db.commit()

        restored_roles = [ctx.guild.get_role(r_id) for r_id in role_ids if ctx.guild.get_role(r_id) is not None]
        
        try:
            await member.edit(roles=restored_roles, reason=f"Unjail por {ctx.author}")
            await ctx.message.add_reaction("👍")
            
            # Enviar Log
            await self.send_jail_log(ctx.guild, "Unjail", member, ctx.author, reason)

        except discord.Forbidden:
            await ctx.reply("❌ No tengo permisos suficientes para restaurar los roles.", mention_author=False)

async def setup(bot):
    await bot.add_cog(Jail(bot))
