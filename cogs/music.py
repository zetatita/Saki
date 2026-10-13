import discord
from discord.ext import commands
import yt_dlp
import asyncio

# Configuración de yt-dlp para evitar bloqueos y obtener audio directo
ytdl_format_options = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('webpage_url')
        self.duration = data.get('duration')
        self.uploader = data.get('uploader')

    @classmethod
    async def create_source(cls, ctx, search: str, *, loop=None):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(search, download=False))

        if 'entries' in data:
            # Tomar el primer resultado si es una búsqueda
            data = data['entries'][0]

        filename = data['url']
        audio = discord.FFmpegPCMAudio(filename, **ffmpeg_options)
        return cls(audio, data=data)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = {}

    def get_queue(self, guild_id):
        if guild_id not in self.queue:
            self.queue[guild_id] = []
        return self.queue[guild_id]

    # ==================== COMANDO: ,play / ,p ====================
    @commands.command(name="play", aliases=["p"])
    async def play(self, ctx, *, search: str = None):
        """Reproduce una canción o la añade a la cola estilo Bleed."""
        if search is None:
            embed = discord.Embed(
                description="### **Command: play**\n\nPlays a song from YouTube\n\n```text\nSyntax: ,play <url o nombre>\nExample: ,play central cee dot ninedee\n```",
                color=0x1e1f22
            )
            embed.set_author(name=f"{self.bot.user.name} help", icon_url=self.bot.user.display_avatar.url)
            return await ctx.reply(embed=embed, mention_author=False)

        if not ctx.author.voice or not ctx.author.voice.channel:
            embed_err = discord.Embed(description="❌ Debes estar conectado a un canal de voz para reproducir música.", color=0x1e1f22)
            return await ctx.reply(embed=embed_err, mention_author=False)

        channel = ctx.author.voice.channel
        voice_client = ctx.voice_client

        if voice_client is None:
            try:
                voice_client = await channel.connect()
            except Exception as e:
                embed_err = discord.Embed(description=f"❌ No pude conectarme al canal de voz: `{e}`", color=0x1e1f22)
                return await ctx.reply(embed=embed_err, mention_author=False)
        elif voice_client.channel != channel:
            await voice_client.move_to(channel)

        async with ctx.typing():
            try:
                player = await YTDLSource.create_source(ctx, search, loop=self.bot.loop)
            except Exception as e:
                embed_err = discord.Embed(description=f"❌ Ocurrió un error al buscar la canción: `{e}`", color=0x1e1f22)
                return await ctx.reply(embed=embed_err, mention_author=False)

        server_queue = self.get_queue(ctx.guild.id)

        if voice_client.is_playing() or voice_client.is_paused():
            server_queue.append(player)
            embed = discord.Embed(
                description=f"🎵 Añadido a la cola: **[{player.title}]({player.url})** (`{player.uploader}`)",
                color=0x2b2d31
            )
            await ctx.reply(embed=embed, mention_author=False)
        else:
            server_queue.append(player)
            self.play_next(ctx)

    def play_next(self, ctx):
        server_queue = self.get_queue(ctx.guild.id)
        if len(server_queue) == 0:
            return

        player = server_queue.pop(0)

        def after_playing(error):
            if error:
                print(f"❌ Error en el reproductor de audio: {error}")
            self.play_next(ctx)

        ctx.voice_client.play(player, after=after_playing)

        embed = discord.Embed(
            description=f"🎶 Reproduciendo ahora: **[{player.title}]({player.url})**\n> Canal: `{player.uploader}`",
            color=0x2b2d31
        )
        asyncio.run_coroutine_threadsafe(ctx.send(embed=embed), self.bot.loop)

    # ==================== COMANDO: ,skip / ,s ====================
    @commands.command(name="skip", aliases=["s"])
    async def skip(self, ctx):
        """Salta la canción actual."""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            embed = discord.Embed(description="⏭️ Canción saltada.", color=0x2b2d31)
            await ctx.reply(embed=embed, mention_author=False)
        else:
            embed_err = discord.Embed(description="❌ No hay ninguna canción reproduciéndose actualmente.", color=0x1e1f22)
            await ctx.reply(embed=embed_err, mention_author=False)

    # ==================== COMANDO: ,queue / ,q ====================
    @commands.command(name="queue", aliases=["q"])
    async def queue(self, ctx):
        """Muestra la cola de reproducción actual."""
        server_queue = self.get_queue(ctx.guild.id)
        if not server_queue:
            embed = discord.Embed(description="Music queue is currently empty.", color=0x1e1f22)
            embed.set_author(name=f"{self.bot.user.name} queue", icon_url=self.bot.user.display_avatar.url)
            return await ctx.reply(embed=embed, mention_author=False)

        description = "\n".join([f"`{idx + 1}.` [{song.title}]({song.url})" for idx, song in enumerate(server_queue[:10])])
        embed = discord.Embed(title="Server Music Queue", description=description, color=0x2b2d31)
        await ctx.reply(embed=embed, mention_author=False)

    # ==================== COMANDO: ,stop / ,disconnect ====================
    @commands.command(name="stop", aliases=["dc", "disconnect"])
    async def stop(self, ctx):
        """Detiene la música y desconecta al bot del canal de voz."""
        server_queue = self.get_queue(ctx.guild.id)
        server_queue.clear()

        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            embed = discord.Embed(description="👋 Música detenida y bot desconectado.", color=0x2b2d31)
            await ctx.reply(embed=embed, mention_author=False)
        else:
            embed_err = discord.Embed(description="❌ El bot no está en ningún canal de voz.", color=0x1e1f22)
            await ctx.reply(embed=embed_err, mention_author=False)

async def setup(bot):
    await bot.add_cog(Music(bot))
