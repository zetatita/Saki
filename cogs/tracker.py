import discord
from discord.ext import commands
import aiosqlite
from config import DB_NAME
import io
from PIL import Image
import aiohttp
import asyncio

async def fetch_image_bytes(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(str(url)) as resp:
                if resp.status == 200:
                    return await resp.read()
    except Exception:
        pass
    return None

def generate_grid_sync(avatar_data_list):
    size = 120
    count = min(len(avatar_data_list), 25)
    if count == 0:
        return None
    
    cols = min(5, count)
    rows = (count + cols - 1) // cols
    
    grid_img = Image.new('RGB', (cols * size, rows * size), (30, 31, 34))
    
    for idx, img_data in enumerate(avatar_data_list[:25]):
        if img_data:
            try:
                avatar = Image.open(io.BytesIO(img_data)).convert("RGB")
                avatar = avatar.resize((size, size))
                x = (idx % cols) * size
                y = (idx // cols) * size
                grid_img.paste(avatar, (x, y))
            except Exception:
                pass
            
    output = io.BytesIO()
    grid_img.save(output, format="PNG")
    output.seek(0)
    return output

async def create_avatar_grid(avatar_urls):
    tasks = [fetch_image_bytes(url) for url in avatar_urls[:25]]
    avatar_data_list = await asyncio.gather(*tasks)
    
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, generate_grid_sync, avatar_data_list)


class ProfileSelect(discord.ui.Select):
    def __init__(self, target_user: discord.User, current_selected: str = "avatars"):
        self.target_user = target_user
        
        options = [
            discord.SelectOption(label="Nombres", description="Nombres de usuario anteriores", emoji="📝", value="names", default=(current_selected == "names")),
            discord.SelectOption(label="Avatares", description="Historial de fotos de perfil", emoji="📦", value="avatars", default=(current_selected == "avatars")),
            discord.SelectOption(label="Tags", description="Tags y apodos anteriores", emoji="🏷️", value="tags", default=(current_selected == "tags")),
            discord.SelectOption(label="Ficha", description="Información general del usuario", emoji="📊", value="ficha", default=(current_selected == "ficha"))
        ]
        super().__init__(placeholder="Selecciona una opción...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        selected = self.values[0]

        async with aiosqlite.connect(DB_NAME) as db:
            if selected == "avatars":
                async with db.execute("SELECT avatar_url FROM user_avatars WHERE user_id = ? ORDER BY timestamp DESC LIMIT 25", (self.target_user.id,)) as cursor:
                    rows = await cursor.fetchall()
                
                urls = [r[0] for r in rows] if rows else [str(self.target_user.display_avatar.url)]
                grid_file = await create_avatar_grid(urls)
                
                embed = discord.Embed(color=0x2b2d31)
                view = ProfileView(self.target_user, current_selected="avatars")
                
                if grid_file:
                    file = discord.File(grid_file, filename="avatars.png")
                    embed.set_image(url="attachment://avatars.png")
                    return await interaction.edit_original_response(content=f"🖼️ Historial de avatares de **{self.target_user.name}**", embed=embed, attachments=[file], view=view)
                else:
                    embed.set_image(url=str(self.target_user.display_avatar.url))
                    return await interaction.edit_original_response(content=f"🖼️ Avatar actual de **{self.target_user.name}**", embed=embed, attachments=[], view=view)

            elif selected == "names":
                async with db.execute("SELECT username, timestamp FROM user_names WHERE user_id = ? ORDER BY timestamp DESC LIMIT 10", (self.target_user.id,)) as cursor:
                    rows = await cursor.fetchall()
                
                names_str = "\n".join([f"`{i+1}.` {name} • *{date[:10]}*" for i, (name, date) in enumerate(rows)]) if rows else f"`1.` {self.target_user.name}"
                embed = discord.Embed(title=f"🌐 Historial de nombres — {self.target_user.name}", description=names_str, color=0x2b2d31)
                view = ProfileView(self.target_user, current_selected="names")
                return await interaction.edit_original_response(content=None, embed=embed, attachments=[], view=view)

            elif selected == "tags":
                async with db.execute("SELECT tag, timestamp FROM user_tags WHERE user_id = ? ORDER BY timestamp DESC LIMIT 10", (self.target_user.id,)) as cursor:
                    rows = await cursor.fetchall()
                
                tags_str = "\n".join([f"`{i+1}.` {t} • *{d[:10]}*" for i, (t, d) in enumerate(rows)]) if rows else f"`1.` {self.target_user.name}"
                embed = discord.Embed(title=f"🏷️ Historial de Tags — {self.target_user.name}", description=tags_str, color=0x2b2d31)
                view = ProfileView(self.target_user, current_selected="tags")
                return await interaction.edit_original_response(content=None, embed=embed, attachments=[], view=view)

            elif selected == "ficha":
                embed = discord.Embed(title=f"📊 Ficha de {self.target_user.name}", color=0x2b2d31)
                embed.set_thumbnail(url=str(self.target_user.display_avatar.url))
                embed.add_field(name="ID", value=f"`{self.target_user.id}`", inline=True)
                embed.add_field(name="Creado", value=f"<t:{int(self.target_user.created_at.timestamp())}:R>", inline=True)
                view = ProfileView(self.target_user, current_selected="ficha")
                return await interaction.edit_original_response(content=None, embed=embed, attachments=[], view=view)


class ProfileView(discord.ui.View):
    def __init__(self, target_user: discord.User, current_selected: str = "avatars"):
        super().__init__(timeout=60)
        self.add_item(ProfileSelect(target_user, current_selected))


class Tracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def init_db(self):
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_avatars (
                    user_id INTEGER,
                    avatar_url TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_names (
                    user_id INTEGER,
                    username TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_tags (
                    user_id INTEGER,
                    tag TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_banners (
                    user_id INTEGER,
                    banner_url TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()

    async def cog_load(self):
        await self.init_db()

    async def record_user(self, user: discord.User):
        """Verifica y registra de manera inteligente avatares, nombres, tags y banners nuevos."""
        avatar_url = str(user.display_avatar.url)
        username = user.name
        tag = getattr(user, "discriminator", "0")
        if tag == "0":
            tag = user.name

        try:
            fetched_user = await self.bot.fetch_user(user.id)
            banner_url = str(fetched_user.banner.url) if fetched_user.banner else None
        except Exception:
            banner_url = None

        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT avatar_url FROM user_avatars WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1", (user.id,)) as cursor:
                row_avatar = await cursor.fetchone()
            if not row_avatar or row_avatar[0] != avatar_url:
                await db.execute("INSERT INTO user_avatars (user_id, avatar_url) VALUES (?, ?)", (user.id, avatar_url))

            async with db.execute("SELECT username FROM user_names WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1", (user.id,)) as cursor:
                row_name = await cursor.fetchone()
            if not row_name or row_name[0] != username:
                await db.execute("INSERT INTO user_names (user_id, username) VALUES (?, ?)", (user.id, username))

            async with db.execute("SELECT tag FROM user_tags WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1", (user.id,)) as cursor:
                row_tag = await cursor.fetchone()
            if not row_tag or row_tag[0] != tag:
                await db.execute("INSERT INTO user_tags (user_id, tag) VALUES (?, ?)", (user.id, tag))

            if banner_url:
                async with db.execute("SELECT banner_url FROM user_banners WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1", (user.id,)) as cursor:
                    row_banner = await cursor.fetchone()
                if not row_banner or row_banner[0] != banner_url:
                    await db.execute("INSERT INTO user_banners (user_id, banner_url) VALUES (?, ?)", (user.id, banner_url))

            await db.commit()

    def check_clear_permission(self, ctx) -> bool:
        """Verifica si el usuario es Administrador o Booster del servidor."""
        if not isinstance(ctx.author, discord.Member):
            return False
        is_admin = ctx.author.guild_permissions.administrator
        is_booster = ctx.author.premium_since is not None
        return is_admin or is_booster

    async def send_boost_required_embed(self, ctx):
        """Responde con un embed estilo Bleed requiriendo mejora del servidor."""
        embed = discord.Embed(
            title="🚀 **Función Exclusiva de Mejoras / Boost**",
            description=(
                "Para poder usar los comandos de limpieza de historial debes haber "
                "**mejorado (boosteado) el servidor** o contar con permisos de Administrador.\n\n"
                "✨ *¡Boostea el servidor para desbloquear este y más beneficios exclusivos!*"
            ),
            color=0x2b2d31
        )
        embed.set_footer(text=f"Solicitado por {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        await self.record_user(after)

    @commands.command(name="avatar", aliases=["av"])
    async def avatar(self, ctx, user: discord.User = None):
        """Muestra el avatar actual del usuario de forma directa."""
        target = user or ctx.author
        
        embed = discord.Embed(
            title=f"Avatar de {target.name}",
            color=0x2b2d31
        )
        embed.set_image(url=str(target.display_avatar.url))
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="avatars", aliases=["historyavatars"])
    async def avatars(self, ctx, user: discord.User = None):
        """Muestra la cuadrícula con el historial de avatares del usuario."""
        target = user or ctx.author
        await self.record_user(target)
        
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT avatar_url FROM user_avatars WHERE user_id = ? ORDER BY timestamp DESC LIMIT 25", (target.id,)) as cursor:
                rows = await cursor.fetchall()

        urls = [r[0] for r in rows] if rows else [str(target.display_avatar.url)]
        grid_file = await create_avatar_grid(urls)

        embed = discord.Embed(color=0x2b2d31)
        file = None
        if grid_file:
            file = discord.File(grid_file, filename="avatars.png")
            embed.set_image(url="attachment://avatars.png")
        else:
            embed.set_image(url=str(target.display_avatar.url))

        view = ProfileView(target, current_selected="avatars")
        if file:
            await ctx.reply(content=f"🖼️ Historial de avatares de **{target.name}**", embed=embed, file=file, view=view, mention_author=False)
        else:
            await ctx.reply(content=f"🖼️ Historial de avatares de **{target.name}**", embed=embed, view=view, mention_author=False)

    @commands.command(name="usernames", aliases=["names", "historynames"])
    async def usernames(self, ctx, user: discord.User = None):
        target = user or ctx.author
        await self.record_user(target)

        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT username, timestamp FROM user_names WHERE user_id = ? ORDER BY timestamp DESC LIMIT 10", (target.id,)) as cursor:
                rows = await cursor.fetchall()

        names_str = "\n".join([f"`{i+1}.` {n} • *{d[:10]}*" for i, (n, d) in enumerate(rows)]) if rows else f"`1.` {target.name}"
        embed = discord.Embed(title=f"🌐 Historial de nombres — {target.name}", description=names_str, color=0x2b2d31)
        view = ProfileView(target, current_selected="names")
        await ctx.reply(embed=embed, view=view, mention_author=False)

    @commands.command(name="tags", aliases=["historytags"])
    async def tags(self, ctx, user: discord.User = None):
        target = user or ctx.author
        await self.record_user(target)

        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT tag, timestamp FROM user_tags WHERE user_id = ? ORDER BY timestamp DESC LIMIT 10", (target.id,)) as cursor:
                rows = await cursor.fetchall()

        tags_str = "\n".join([f"`{i+1}.` {t} • *{d[:10]}*" for i, (t, d) in enumerate(rows)]) if rows else f"`1.` {target.name}"
        embed = discord.Embed(title=f"🏷️ Historial de Tags — {target.name}", description=tags_str, color=0x2b2d31)
        view = ProfileView(target, current_selected="tags")
        await ctx.reply(embed=embed, view=view, mention_author=False)

    @commands.command(name="historybanners")
    async def historybanners(self, ctx, user: discord.User = None):
        target = user or ctx.author
        await self.record_user(target)

        try:
            fetched_user = await self.bot.fetch_user(target.id)
        except Exception:
            fetched_user = target

        embed = discord.Embed(title=f"🎨 Banner de {target.name}", color=0x2b2d31)
        if fetched_user.banner:
            embed.set_image(url=fetched_user.banner.url)
        else:
            embed.description = f"❌ **{target.name}** no tiene un banner configurado (mostrando avatar)."
            embed.set_image(url=str(target.display_avatar.url))

        view = ProfileView(target, current_selected="ficha")
        await ctx.reply(embed=embed, view=view, mention_author=False)

    # --- COMANDOS DE LIMPIEZA CON VERIFICACIÓN DE BOOST ---

    @commands.command(name="clearavatars")
    async def clearavatars(self, ctx, member: discord.Member = None):
        if not self.check_clear_permission(ctx):
            return await self.send_boost_required_embed(ctx)

        target = member if member and ctx.author.guild_permissions.administrator else ctx.author
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("DELETE FROM user_avatars WHERE user_id = ?", (target.id,))
            await db.commit()
        
        embed = discord.Embed(
            description=f"### **Limpieza de Avatares**\n\nSe ha borrado exitosamente el historial de avatares para **{target.name}**.",
            color=0x2b2d31
        )
        embed.set_author(name=f"{self.bot.user.name} perfiles", icon_url=self.bot.user.display_avatar.url)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="clearnames")
    async def clearnames(self, ctx, member: discord.Member = None):
        if not self.check_clear_permission(ctx):
            return await self.send_boost_required_embed(ctx)

        target = member if member and ctx.author.guild_permissions.administrator else ctx.author
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("DELETE FROM user_names WHERE user_id = ?", (target.id,))
            await db.commit()
        
        embed = discord.Embed(
            description=f"### **Limpieza de Nombres**\n\nSe ha borrado exitosamente el historial de nombres para **{target.name}**.",
            color=0x2b2d31
        )
        embed.set_author(name=f"{self.bot.user.name} perfiles", icon_url=self.bot.user.display_avatar.url)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="cleartags")
    async def cleartags(self, ctx, member: discord.Member = None):
        if not self.check_clear_permission(ctx):
            return await self.send_boost_required_embed(ctx)

        target = member if member and ctx.author.guild_permissions.administrator else ctx.author
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("DELETE FROM user_tags WHERE user_id = ?", (target.id,))
            await db.commit()
        
        embed = discord.Embed(
            description=f"### **Limpieza de Tags**\n\nSe ha borrado exitosamente el historial de tags para **{target.name}**.",
            color=0x2b2d31
        )
        embed.set_author(name=f"{self.bot.user.name} perfiles", icon_url=self.bot.user.display_avatar.url)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="clearbanners")
    async def clearbanners(self, ctx, member: discord.Member = None):
        if not self.check_clear_permission(ctx):
            return await self.send_boost_required_embed(ctx)

        target = member if member and ctx.author.guild_permissions.administrator else ctx.author
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("DELETE FROM user_banners WHERE user_id = ?", (target.id,))
            await db.commit()
        
        embed = discord.Embed(
            description=f"### **Limpieza de Banners**\n\nSe ha borrado exitosamente el historial de banners para **{target.name}**.",
            color=0x2b2d31
        )
        embed.set_author(name=f"{self.bot.user.name} perfiles", icon_url=self.bot.user.display_avatar.url)
        await ctx.reply(embed=embed, mention_author=False)

async def setup(bot):
    await bot.add_cog(Tracker(bot))
