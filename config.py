import os
import aiosqlite
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN", "")
DEFAULT_PREFIX = ","
SUPPORT_GUILD_ID = 1557520938763948122 # Reemplaza con la ID de tu servidor de soporte
DB_NAME = "bleed_bot.db"

async def get_user_tier(bot, user, guild=None) -> int:
    """Calcula el nivel de Tier actual de un usuario (0 a 5)."""
    # 1. Administrador del servidor actual o Dueño del bot -> Tier 5
    if guild and (user.id == guild.owner_id or (hasattr(user, "guild_permissions") and user.guild_permissions.administrator)):
        return 5

    tier = 0

    # 2. Consultar asignación manual en la base de datos (Tiers 2, 3, 4, 5)
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT tier FROM user_tiers WHERE user_id = ?", (user.id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                tier = row[0]

    # 3. Verificar si es Booster del servidor oficial (Tier 1)
    if tier < 1:
        support_guild = bot.get_guild(SUPPORT_GUILD_ID)
        if support_guild:
            member = support_guild.get_member(user.id)
            if member and member.premium_since is not None:
                tier = max(tier, 1)

    return tier