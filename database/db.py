import aiosqlite
import os
from config import DB_NAME

async def init_db():
    os.makedirs(os.path.dirname(DB_NAME), exist_ok=True)
    async with aiosqlite.connect(DB_NAME) as db:
        # Tabla de niveles VIP
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_tiers (
                user_id INTEGER PRIMARY KEY,
                tier INTEGER NOT NULL DEFAULT 0
            )
        """)
        # Tabla de historial de perfil
        await db.execute("""
            CREATE TABLE IF NOT EXISTS profile_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                value TEXT NOT NULL,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Tabla de vistas de perfil (mstats)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS history_views (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_id INTEGER NOT NULL,
                viewer_id INTEGER NOT NULL,
                viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Tabla de modo fantasma
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ghost_mode (
                user_id INTEGER PRIMARY KEY
            )
        """)
        # Tabla de auditoría de comandos
        await db.execute("""
            CREATE TABLE IF NOT EXISTS command_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                command_name TEXT NOT NULL,
                args TEXT,
                executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Índices para acelerar búsquedas
        await db.execute("CREATE INDEX IF NOT EXISTS idx_profile_user ON profile_history(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_views_target ON history_views(target_id)")
        await db.commit()