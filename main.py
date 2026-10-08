import asyncio
import discord
from discord.ext import commands
from config import TOKEN, DEFAULT_PREFIX
from database.db import init_db

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

bot = commands.Bot(command_prefix=DEFAULT_PREFIX, intents=intents)

initial_extensions = [
    'cogs.server',
    'cogs.tracker',
    'cogs.vip',
    'cogs.moderation',
    'cogs.antinuke',
    'cogs.autoresponder',
    'cogs.embeds',
    'cogs.jail',
    'cogs.utility',
]

@bot.event
async def on_ready():
    await init_db()
    print(f"🤖 Bot conectado como {bot.user} (ID: {bot.user.id})")
    print("----------------------------------------------------")

async def main():
    async with bot:
        for extension in initial_extensions:
            await bot.load_extension(extension)
            print(f"📦 Cog cargado: {extension}")
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
