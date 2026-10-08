import discord
from discord.ext import commands
import aiosqlite
from config import DB_NAME

class VIP(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # IDs de los roles de Tiers (Reemplaza con tus IDs reales)
    TIER_ROLES = {
        1: 1557603729669361775,  # Rol de Booster
        2: 1557599670455246848,  # Tier 2
        3: 1557600244823498753,  # Tier 3
        4: 1557600393561907320,  # Tier 4
        5: 1557600538390958181   # Tier 5
    }

    # ---------------------------------------------------------
    # LISTENER AUTOMÁTICO DE SERVER BOOSTS
    # ---------------------------------------------------------
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.premium_since is None and after.premium_since is not None:
            guild = after.guild
            
            # Asignar rol de Booster (Tier 1) automáticamente
            tier_1_role_id = self.TIER_ROLES.get(1)
            role = guild.get_role(tier_1_role_id)
            if role:
                try:
                    await after.add_roles(role, reason="Nuevo Server Boost detectado")
                except discord.HTTPException:
                    pass

            # Guardar en base de datos
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS user_tiers (
                        guild_id INTEGER, user_id INTEGER, tier INTEGER, PRIMARY KEY (guild_id, user_id)
                    )
                """)
                await db.execute(
                    "INSERT INTO user_tiers (guild_id, user_id, tier) VALUES (?, ?, 1) ON CONFLICT(guild_id, user_id) DO UPDATE SET tier = MAX(tier, 1)",
                    (guild.id, after.id)
                )
                await db.commit()

            # Enviar mensaje de agradecimiento en el canal del sistema o texto
            target_channel = guild.system_channel or next((c for c in guild.text_channels if c.permissions_for(guild.me).send_messages), None)
            if target_channel:
                embed = discord.Embed(
                    description=f"¡Gracias por mejorar {guild.name}, {after.mention}! 💜\n"
                                "Ya puedes usar estos comandos:\n\n"
                                "```text\n"
                                "!clearavatars, !clearnames, !tags\n"
                                "```",
                    color=0x9b59b6
                )
                embed.set_footer(
                    text=f"{guild.premium_subscription_count} boosts • Lvl {guild.premium_tier}",
                    icon_url=guild.icon.url if guild.icon else after.display_avatar.url
                )
                await target_channel.send(content=f"{after.mention} mejoró el servidor 💜", embed=embed)

    # ---------------------------------------------------------
    # COMANDO ,settier (Gestión de rangos VIP)
    # ---------------------------------------------------------
    @commands.command(name="settier", aliases=["setvip"])
    @commands.has_permissions(administrator=True)
    async def set_tier(self, ctx, member: discord.Member = None, tier_level: int = None):
        if member is None or tier_level is None or tier_level not in range(1, 6):
            embed = discord.Embed(
                description="### **Comando: settier**\n\n"
                            "Asigna un nivel VIP y su respectivo rol de servidor a un usuario.\n\n"
                            "```text\n"
                            "Sintaxis: ,settier <usuario> <nivel_1_al_5>\n"
                            "Ejemplo:  ,settier @usuario 3\n"
                            "```",
                color=0x1e1f22
            )
            embed.set_author(name=f"{self.bot.user.name} ayuda", icon_url=self.bot.user.display_avatar.url)
            return await ctx.reply(embed=embed, mention_author=False)

        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_tiers (
                    guild_id INTEGER, user_id INTEGER, tier INTEGER, PRIMARY KEY (guild_id, user_id)
                )
            """)
            await db.execute(
                "INSERT INTO user_tiers (guild_id, user_id, tier) VALUES (?, ?, ?) ON CONFLICT(guild_id, user_id) DO UPDATE SET tier = ?",
                (ctx.guild.id, member.id, tier_level, tier_level)
            )
            await db.commit()

        try:
            # Remover roles de otros tiers para evitar duplicados
            roles_to_remove = [ctx.guild.get_role(r_id) for t_lvl, r_id in self.TIER_ROLES.items() if t_lvl != tier_level]
            for r in roles_to_remove:
                if r and r in member.roles:
                    await member.remove_roles(r, reason=f"Actualización de Tier VIP a Nivel {tier_level} por {ctx.author}")

            target_role_id = self.TIER_ROLES.get(tier_level)
            target_role = ctx.guild.get_role(target_role_id)

            if target_role:
                await member.add_roles(target_role, reason=f"Asignación de Tier VIP Nivel {tier_level} por {ctx.author}")
            
            await ctx.message.add_reaction("👍")
        except Exception:
            await ctx.reply("Error al asignar los roles. Verifica la jerarquía de roles del bot.", mention_author=False)

async def setup(bot):
    await bot.add_cog(VIP(bot))