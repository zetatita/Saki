import json
import aiosqlite
import discord
from discord.ext import commands
from database.db import DB_NAME

class Jail(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="jail")
    @commands.has_permissions(manage_roles=True)
    async def jail(self, ctx, member: discord.Member, *, reason: str = "Sin razón"):
        """Aísla a un usuario guardando sus roles previos. Uso: ,jail @usuario razón"""
        jail_role = discord.utils.get(ctx.guild.roles, name="Jailed")
        if not jail_role:
            return await ctx.send("Crea un rol llamado **Jailed** en el servidor para usar este comando.")

        user_roles = [r.id for r in member.roles if r != ctx.guild.default_role and not r.is_integration()]
        roles_json = json.dumps(user_roles)

        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "INSERT OR REPLACE INTO jail_data VALUES (?, ?, ?)",
                (ctx.guild.id, member.id, roles_json)
            )
            await db.commit()

        try:
            await member.edit(roles=[jail_role], reason=f"Jail por {ctx.author}: {reason}")
            embed = discord.Embed(
                description=f"**{member}** ha sido encarcelado. | Razón: {reason}",
                color=0xff4b4b
            )
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send("No tengo permisos suficientes para cambiar los roles de este usuario.")

    @commands.command(name="unjail")
    @commands.has_permissions(manage_roles=True)
    async def unjail(self, ctx, member: discord.Member):
        """Restaura los roles de un usuario encarcelado. Uso: ,unjail @usuario"""
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute(
                "SELECT saved_roles FROM jail_data WHERE guild_id = ? AND user_id = ?",
                (ctx.guild.id, member.id)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return await ctx.send("El usuario no tiene roles guardados en la base de datos.")

                role_ids = json.loads(row[0])
                await db.execute(
                    "DELETE FROM jail_data WHERE guild_id = ? AND user_id = ?",
                    (ctx.guild.id, member.id)
                )
                await db.commit()

        restored_roles = [ctx.guild.get_role(r_id) for r_id in role_ids if ctx.guild.get_role(r_id) is not None]
        await member.edit(roles=restored_roles, reason=f"Unjail por {ctx.author}")

        embed = discord.Embed(
            description=f"**{member}** ha sido liberado y sus roles fueron restaurados.",
            color=0x4caf50
        )
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Jail(bot))