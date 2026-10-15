import discord
from discord.ext import commands
import aiosqlite
from config import DB_NAME
import io
from PIL import Image
import aiohttp
import asyncio
import time

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
    def __init__(self, target_user, current_selected: str = "names"):
        self.target_user = target_user
        
        options = [
            discord.SelectOption(label="Nombres", description="Historial de apodos y nombres visibles", emoji="🌐", value="names", default=(current_selected == "names")),
            discord.SelectOption(label="Avatares", description="Historial de fotos de perfil", emoji="📦", value="avatars", default=(current_selected == "avatars")),
            discord.SelectOption(label="Tags", description="Historial de nombres de usuario (@handles)", emoji="🏷️", value="tags", default=(current_selected == "tags")),
            discord.SelectOption(label="Ficha", description="Información general del usuario", emoji="📊", value="ficha", default=(current_selected == "ficha"))
        ]
        super().__init__(placeholder="Selecciona una opción...", options=options, min_values=1, max_values=1, row=0)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        selected = self.values[0]
        view = ProfileView(self.target_user, current_selected=selected, current_page=0)
        await view.update_message(interaction)


class ProfileView(discord.ui.View):
    def __init__(self, target_user, current_selected: str = "names", current_page: int = 0):
        super().__init__(timeout=120)
        self.target_user = target_user
        self.current_selected = current_selected
        self.current_page = current_page
        self.per_page = 10
        self.total_pages = 1

        self.add_item(ProfileSelect(target_user, current_selected))

    @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.primary, row=1)
    async def first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = 0
        await self.update_message(interaction)

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.primary, row=1)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
        await self.update_message(interaction)

    @discord.ui.button(emoji="✖️", style=discord.ButtonStyle.secondary, row=1)
    async def close_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.primary, row=1)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
        await self.update_message(interaction)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.primary, row=1)
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = max(0, self.total_pages - 1)
        await self.update_message(interaction)

    @discord.ui.button(label="Mis estadísticas", emoji="📊", style=discord.ButtonStyle.secondary, row=2)
    async def stats_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            description=f"📊 **Estadísticas de {self.target_user.name}**\n\nEl historial se registra automáticamente al cambiar de apodo o avatar.",
            color=0x2b2d31
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def update_message(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_NAME) as db:
            if self.current_selected == "names":
                async with db.execute(
                    "SELECT display_name, timestamp FROM user_names WHERE user_id = ? ORDER BY timestamp DESC", 
                    (self.target_user.id,)
                ) as cursor:
                    rows = await cursor.fetchall()

                display_fallback = getattr(self.target_user, "display_name", self.target_user.name)
                if not rows:
                    rows = [(display_fallback, int(time.time()))]

                self.total_pages = max(1, (len(rows) - 1) // self.per_page + 1)
                start = self.current_page * self.per_page
                page_items = rows[start:start + self.per_page]

                lines = []
                for idx, (name_val, ts_val) in enumerate(page_items):
                    try:
                        ts_num = int(ts_val)
                    except Exception:
                        ts_num = int(time.time())
                    lines.append(f"`{start + idx + 1}.` **{name_val}** • <t:{ts_num}:R>")

                embed = discord.Embed(
                    title="🌐 **Historial de nombres**",
                    description=f"### {self.target_user.name}\n\n" + "\n".join(lines),
                    color=0x2b2d31
                )
                embed.set_footer(text=f"Página {self.current_page + 1}/{self.total_pages} ({len(rows)} registros)")
                
                if interaction.response.is_done():
                    await interaction.edit_original_response(embed=embed, attachments=[], view=self)
                else:
                    await interaction.response.edit_message(embed=embed, attachments=[], view=self)

            elif self.current_selected == "tags":
                async with db.execute(
                    "SELECT tag, timestamp FROM user_tags WHERE user_id = ? ORDER BY timestamp DESC", 
                    (self.target_user.id,)
                ) as cursor:
                    rows = await cursor.fetchall()

                if not rows:
                    rows = [(self.target_user.name, int(time.time()))]

                self.total_pages = max(1, (len(rows) - 1) // self.per_page + 1)
                start = self.current_page * self.per_page
                page_items = rows[start:start + self.per_page]

                lines = []
                for idx, (tag_val, ts_val) in enumerate(page_items):
                    try:
                        ts_num = int(ts_val)
                    except Exception:
                        ts_num = int(time.time())
                    lines.append(f"`{start + idx + 1}.` **{tag_val}** • <t:{ts_num}:R>")

                embed = discord.Embed(
                    title="🏷️ **Historial de Tags**",
                    description=f"### {self.target_user.name}\n\n" + "\n".join(lines),
                    color=0x2b2d31
                )
                embed.set_footer(text=f"Página {self.current_page + 1}/{self.total_pages} ({len(rows)} registros)")
                
                if interaction.response.is_done():
                    await interaction.edit_original_response(embed=embed, attachments=[], view=self)
                else:
                    await interaction.response.edit_message(embed=embed, attachments=[], view=self)

            elif self.current_selected == "avatars":
                async with db.execute("SELECT avatar_url FROM user_avatars WHERE user_id = ? ORDER BY timestamp DESC LIMIT 25", (self.target_user.id,)) as cursor:
                    rows = await cursor.fetchall()

                urls = [r[0] for r in rows] if rows else [str(self.target_user.display_avatar.url)]
                grid_file = await create_avatar_grid(urls)

                embed = discord.Embed(
                    description=f"🖼️ **Aquí está el historial de avatares de {self.target_user.name}**",
                    color=0x2b2d31
                )
                embed.set_author(name=self.target_user.name, icon_url=self.target_user.display_avatar.url)

                if grid_file:
                    file = discord.File(grid_file, filename="avatars.png")
                    embed.set_image(url="attachment://avatars.png")
                    if interaction.response.is_done():
                        await interaction.edit_original_response(embed=embed, attachments=[file], view=self)
                    else:
                        await interaction.response.edit_message(embed=embed, attachments=[file], view=self)
                else:
                    embed.set_image(url=str(self.target_user.display_avatar.url))
                    if interaction.response.is_done():
                        await interaction.edit_original_response(embed=embed, attachments=[], view=self)
                    else:
                        await interaction.response.edit_message(embed=embed, attachments=[], view=self)

            elif self.current_selected == "ficha":
                member = interaction.guild.get_member(self.target_user.id) if interaction.guild else None
                created_ts = int(self.target_user.created_at.timestamp())
                joined_ts = int(member.joined_at.timestamp()) if member and member.joined_at else created_ts

                embed = discord.Embed(
                    title=f"{self.target_user.name} ({self.target_user.id})",
                    color=0x2b2d31
                )
                embed.set_thumbnail(url=self.target_user.display_avatar.url)
                embed.add_field(name="Creado", value=f"<t:{created_ts}:R>", inline=True)
                embed.add_field(name="Unido", value=f"<t:{joined_ts}:R>", inline=True)
                
                if member and member.roles:
                    top_role = member.top_role.mention if len(member.roles) > 1 else "Ninguno"
                    embed.add_field(name="Top rol", value=top_role, inline=True)

                embed.add_field(
                    name="Enlaces",
                    value=f"[Avatar]({self.target_user.display_avatar.url})",
                    inline=False
                )
                embed.set_footer(text="SAKI", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
                
                if interaction.response.is_done():
                    await interaction.edit_original_response(embed=embed, attachments=[], view=self)
                else:
                    await interaction.response.edit_message(embed=embed, attachments=[], view=self)


class Tracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def init_db(self):
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("CREATE TABLE IF NOT EXISTS user_avatars (user_id INTEGER, avatar_url TEXT, timestamp INTEGER)")
            await db.execute("CREATE TABLE IF NOT EXISTS user_names (user_id INTEGER, display_name TEXT, timestamp INTEGER)")
            await db.execute("CREATE TABLE IF NOT EXISTS user_tags (user_id INTEGER, tag TEXT, timestamp INTEGER)")
            await db.execute("CREATE TABLE IF NOT EXISTS user_banners (user_id INTEGER, banner_url TEXT, timestamp INTEGER)")
            await db.commit()

    async def cog_load(self):
        await self.init_db()

    async def record_user(self, user):
        if not user:
            return
        try:
            avatar_url = str(user.display_avatar.url)
            display_name = getattr(user, "display_name", user.name)
            username_handle = user.name
            banner_url = None

            try:
                fetched_user = await self.bot.fetch_user(user.id)
                if fetched_user and fetched_user.banner:
                    banner_url = str(fetched_user.banner.url)
            except Exception:
                pass

            current_time = int(time.time())

            async with aiosqlite.connect(DB_NAME) as db:
                async with db.execute("SELECT avatar_url FROM user_avatars WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1", (user.id,)) as cursor:
                    row_avatar = await cursor.fetchone()
                if not row_avatar or row_avatar[0] != avatar_url:
                    await db.execute("INSERT INTO user_avatars (user_id, avatar_url, timestamp) VALUES (?, ?, ?)", (user.id, avatar_url, current_time))

                async with db.execute("SELECT display_name FROM user_names WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1", (user.id,)) as cursor:
                    row_name = await cursor.fetchone()
                if not row_name or row_name[0] != display_name:
                    await db.execute("INSERT INTO user_names (user_id, display_name, timestamp) VALUES (?, ?, ?)", (user.id, display_name, current_time))

                async with db.execute("SELECT tag FROM user_tags WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1", (user.id,)) as cursor:
                    row_tag = await cursor.fetchone()
                if not row_tag or row_tag[0] != username_handle:
                    await db.execute("INSERT INTO user_tags (user_id, tag, timestamp) VALUES (?, ?, ?)", (user.id, username_handle, current_time))

                if banner_url:
                    async with db.execute("SELECT banner_url FROM user_banners WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1", (user.id,)) as cursor:
                        row_banner = await cursor.fetchone()
                    if not row_banner or row_banner[0] != banner_url:
                        await db.execute("INSERT INTO user_banners (user_id, banner_url, timestamp) VALUES (?, ?, ?)", (user.id, banner_url, current_time))

                await db.commit()
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        await self.record_user(after)

    @commands.Cog.listener()
    async def on_user_update(self, before: discord.User, after: discord.User):
        await self.record_user(after)

    @commands.command(name="avatar", aliases=["av"])
    async def avatar(self, ctx, user: discord.User = None):
        target = user or ctx.author
        embed = discord.Embed(title=f"Avatar de {target.name}", color=0x2b2d31)
        embed.set_image(url=str(target.display_avatar.url))
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="avatars", aliases=["historyavatars"])
    async def avatars(self, ctx, user: discord.User = None):
        target = user or ctx.author
        try:
            await self.record_user(target)
        except Exception:
            pass

        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT avatar_url FROM user_avatars WHERE user_id = ? ORDER BY timestamp DESC LIMIT 25", (target.id,)) as cursor:
                rows = await cursor.fetchall()

        urls = [r[0] for r in rows] if rows else [str(target.display_avatar.url)]
        grid_file = await create_avatar_grid(urls)

        embed = discord.Embed(description=f"🖼️ **Aquí está el historial de avatares de {target.name}**", color=0x2b2d31)
        embed.set_author(name=target.name, icon_url=target.display_avatar.url)
        view = ProfileView(target, current_selected="avatars", current_page=0)

        if grid_file:
            file = discord.File(grid_file, filename="avatars.png")
            embed.set_image(url="attachment://avatars.png")
            await ctx.reply(embed=embed, file=file, view=view, mention_author=False)
        else:
            embed.set_image(url=str(target.display_avatar.url))
            await ctx.reply(embed=embed, view=view, mention_author=False)

    @commands.command(name="names", aliases=["usernames", "historynames"])
    async def names_cmd(self, ctx, user: discord.User = None):
        target = user or ctx.author
        try:
            await self.record_user(target)
        except Exception:
            pass

        view = ProfileView(target, current_selected="names", current_page=0)
        
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT display_name, timestamp FROM user_names WHERE user_id = ? ORDER BY timestamp DESC", (target.id,)) as cursor:
                rows = await cursor.fetchall()

        display_fallback = getattr(target, "display_name", target.name)
        if not rows:
            rows = [(display_fallback, int(time.time()))]

        total_pages = max(1, (len(rows) - 1) // 10 + 1)
        page_items = rows[:10]

        lines = []
        for idx, (name_val, ts_val) in enumerate(page_items):
            try:
                ts_num = int(ts_val)
            except Exception:
                ts_num = int(time.time())
            lines.append(f"`{idx + 1}.` **{name_val}** • <t:{ts_num}:R>")

        embed = discord.Embed(
            title="🌐 **Historial de nombres**",
            description=f"### {target.name}\n\n" + "\n".join(lines),
            color=0x2b2d31
        )
        embed.set_footer(text=f"Página 1/{total_pages} ({len(rows)} registros)")
        await ctx.reply(embed=embed, view=view, mention_author=False)

    @commands.command(name="tags", aliases=["historytags"])
    async def tags(self, ctx, user: discord.User = None):
        target = user or ctx.author
        try:
            await self.record_user(target)
        except Exception:
            pass

        view = ProfileView(target, current_selected="tags", current_page=0)

        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT tag, timestamp FROM user_tags WHERE user_id = ? ORDER BY timestamp DESC", (target.id,)) as cursor:
                rows = await cursor.fetchall()

        if not rows:
            rows = [(target.name, int(time.time()))]

        total_pages = max(1, (len(rows) - 1) // 10 + 1)
        page_items = rows[:10]

        lines = []
        for idx, (tag_val, ts_val) in enumerate(page_items):
            try:
                ts_num = int(ts_val)
            except Exception:
                ts_num = int(time.time())
            lines.append(f"`{idx + 1}.` **{tag_val}** • <t:{ts_num}:R>")

        embed = discord.Embed(
            title="🏷️ **Historial de Tags**",
            description=f"### {target.name}\n\n" + "\n".join(lines),
            color=0x2b2d31
        )
        embed.set_footer(text=f"Página 1/{total_pages} ({len(rows)} registros)")
        await ctx.reply(embed=embed, view=view, mention_author=False)

    @commands.command(name="historybanners", aliases=["banners"])
    async def historybanners(self, ctx, user: discord.User = None):
        target = user or ctx.author
        try:
            await self.record_user(target)
        except Exception:
            pass

        try:
            fetched_user = await self.bot.fetch_user(target.id)
        except Exception:
            fetched_user = target

        embed = discord.Embed(title=f"🎨 Banner de {target.name}", color=0x2b2d31)
        if fetched_user and getattr(fetched_user, "banner", None):
            embed.set_image(url=fetched_user.banner.url)
        else:
            embed.description = f"❌ **{target.name}** no tiene un banner configurado (mostrando avatar)."
            embed.set_image(url=str(target.display_avatar.url))

        view = ProfileView(target, current_selected="ficha", current_page=0)
        await ctx.reply(embed=embed, view=view, mention_author=False)

async def setup(bot):
    await bot.add_cog(Tracker(bot))
