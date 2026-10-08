import discord
from discord.ext import commands
import aiosqlite
from config import DB_NAME

# =========================================================
# VISTA INTERACTIVA DE PAGINACIÓN (Roles)
# =========================================================
class RolesPaginator(discord.ui.View):
    def __init__(self, ctx, items, per_page=10):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.items = items
        self.per_page = per_page
        self.current_page = 0
        self.total_pages = max(1, (len(items) - 1) // per_page + 1)
        self.message = None
        self.update_buttons()

    def update_buttons(self):
        self.btn_prev.disabled = (self.current_page == 0)
        self.btn_next.disabled = (self.current_page >= self.total_pages - 1)

    def build_embed(self) -> discord.Embed:
        start = self.current_page * self.per_page
        end = start + self.per_page
        page_items = self.items[start:end]

        lines = [
            f"`{start + idx + 1}` {role.mention}"
            for idx, role in enumerate(page_items)
        ]

        embed = discord.Embed(
            title="Roles",
            description="\n".join(lines) if lines else "*No hay roles registrados.*",
            color=0x2b2d31
        )
        
        embed.set_author(
            name=f"@{self.ctx.guild.name}",
            icon_url=self.ctx.guild.icon.url if self.ctx.guild.icon else self.ctx.author.display_avatar.url
        )
        
        embed.set_footer(
            text=f"Página {self.current_page + 1}/{self.total_pages} ({len(self.items)} registros)"
        )
        return embed

    @discord.ui.button(label="Anterior", style=discord.ButtonStyle.secondary)
    async def btn_prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("No puedes interactuar con este menú.", ephemeral=True)

        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Siguiente", style=discord.ButtonStyle.secondary)
    async def btn_next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("No puedes interactuar con este menú.", ephemeral=True)

        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        try:
            if self.message:
                await self.message.edit(view=self)
        except Exception:
            pass


# =========================================================
# VISTA INTERACTIVA DE CONFIRMACIÓN PARA UNBAN (Estilo Bleed/Louu)
# =========================================================
class UnbanConfirmView(discord.ui.View):
    def __init__(self, ctx, target_user: discord.User, reason: str):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.target_user = target_user
        self.reason = reason
        self.message = None

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("No puedes interactuar con esta confirmación.", ephemeral=True)

        try:
            # 1. Desbanear de Discord
            await self.ctx.guild.unban(self.target_user, reason=f"[Unban por {self.ctx.author}]: {self.reason}")

            # 2. Remover de la base de datos de Hardban si existe
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute("DELETE FROM hardbans WHERE guild_id = ? AND user_id = ?", (self.ctx.guild.id, self.target_user.id))
                await db.commit()

            # 3. Eliminar el mensaje de advertencia y reaccionar con 👍
            await interaction.response.defer()
            await self.message.delete()

            try:
                await self.ctx.message.add_reaction("👍")
            except discord.HTTPException:
                pass

        except Exception as e:
            embed = discord.Embed(
                description="### **Comando: unban**\n\n"
                            f"Ocurrió un error al desbanear al usuario: `{e}`\n\n"
                            "```text\n"
                            "Sintaxis: ,unban <ID_o_Usuario> [razón]\n"
                            "Ejemplo:  ,unban 123456789012345678 Perdonado\n"
                            "```",
                color=0x1e1f22
            )
            embed.set_author(name=f"{self.ctx.bot.user.name} ayuda", icon_url=self.ctx.bot.user.display_avatar.url)
            await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("No puedes interactuar con esta confirmación.", ephemeral=True)

        await interaction.response.defer()
        await self.message.delete()

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        try:
            if self.message:
                await self.message.edit(view=self)
        except Exception:
            pass


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.snipes = {}

    # ---------------------------------------------------------
    # LISTENER HARDBAN AUTOMÁTICO
    # ---------------------------------------------------------
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS hardbans (
                    guild_id INTEGER,
                    user_id INTEGER,
                    reason TEXT,
                    moderator_id INTEGER,
                    banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (guild_id, user_id)
                )
            """)
            async with db.execute("SELECT reason FROM hardbans WHERE guild_id = ? AND user_id = ?", (member.guild.id, member.id)) as cursor:
                row = await cursor.fetchone()
                if row:
                    try:
                        await member.ban(reason=f"[Hardban Automático]: {row[0]}")
                    except discord.HTTPException:
                        pass

    # ---------------------------------------------------------
    # LISTENER SNIPE
    # ---------------------------------------------------------
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        self.snipes[message.channel.id] = {
            "content": message.content,
            "author": message.author,
            "created_at": message.created_at,
            "attachment": message.attachments[0].url if message.attachments else None
        }

    # ---------------------------------------------------------
    # COMANDO ,roles
    # ---------------------------------------------------------
    @commands.command(name="roles", aliases=["rolelist", "roleslist"])
    async def list_roles(self, ctx):
        roles = [r for r in reversed(ctx.guild.roles) if not r.is_default()]

        if not roles:
            embed = discord.Embed(
                description="### **Comando: roles**\n\n"
                            "Este servidor no tiene roles personalizados.\n\n"
                            "```text\n"
                            "Sintaxis: ,roles\n"
                            "Ejemplo:  ,roles\n"
                            "```",
                color=0x1e1f22
            )
            embed.set_author(name=f"{self.bot.user.name} ayuda", icon_url=self.bot.user.display_avatar.url)
            return await ctx.reply(embed=embed, mention_author=False)

        paginator = RolesPaginator(ctx, roles, per_page=10)
        embed = paginator.build_embed()
        paginator.message = await ctx.reply(embed=embed, view=paginator, mention_author=False)

    # ---------------------------------------------------------
    # COMANDO ,s (Snipe)
    # ---------------------------------------------------------
    @commands.command(name="s", aliases=["snipe"])
    async def snipe(self, ctx):
        snipe_data = self.snipes.get(ctx.channel.id)

        if not snipe_data:
            embed = discord.Embed(
                description="### **Comando: snipe**\n\n"
                            "No hay ningún mensaje borrado recientemente en este canal.\n\n"
                            "```text\n"
                            "Sintaxis: ,s\n"
                            "Ejemplo:  ,s\n"
                            "```",
                color=0x1e1f22
            )
            embed.set_author(name=f"{self.bot.user.name} ayuda", icon_url=self.bot.user.display_avatar.url)
            return await ctx.reply(embed=embed, mention_author=False)

        embed = discord.Embed(
            description=snipe_data["content"] or "*[Mensaje sin texto o solo archivo]*",
            color=0x2b2d31,
            timestamp=snipe_data["created_at"]
        )
        embed.set_author(
            name=f"{snipe_data['author']} ({snipe_data['author'].id})",
            icon_url=snipe_data["author"].display_avatar.url
        )
        if snipe_data["attachment"]:
            embed.set_image(url=snipe_data["attachment"])

        await ctx.reply(embed=embed, mention_author=False)

    # ---------------------------------------------------------
    # COMANDO ,cs (Clear Snipe)
    # ---------------------------------------------------------
    @commands.command(name="cs", aliases=["clearsnipe"])
    @commands.has_permissions(manage_messages=True)
    async def clear_snipe(self, ctx):
        if ctx.channel.id in self.snipes:
            del self.snipes[ctx.channel.id]

        try:
            await ctx.message.add_reaction("✅")
        except discord.HTTPException:
            pass

    # ---------------------------------------------------------
    # COMANDO ,ban (Ban Normal)
    # ---------------------------------------------------------
    @commands.command(name="ban")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, user: discord.User = None, *, reason: str = "No especificada"):
        if user is None:
            embed = discord.Embed(
                description="### **Comando: ban**\n\n"
                            "Banea a un usuario del servidor.\n\n"
                            "```text\n"
                            "Sintaxis: ,ban <usuario> [razón]\n"
                            "Ejemplo:  ,ban @usuario Spam\n"
                            "```",
                color=0x1e1f22
            )
            embed.set_author(name=f"{self.bot.user.name} ayuda", icon_url=self.bot.user.display_avatar.url)
            return await ctx.reply(embed=embed, mention_author=False)

        if user.id == ctx.author.id or user.id == self.bot.user.id:
            embed = discord.Embed(
                description="### **Comando: ban**\n\n"
                            "Usuario no válido para sanción.\n\n"
                            "```text\n"
                            "Sintaxis: ,ban <usuario> [razón]\n"
                            "Ejemplo:  ,ban @usuario Spam\n"
                            "```",
                color=0x1e1f22
            )
            embed.set_author(name=f"{self.bot.user.name} ayuda", icon_url=self.bot.user.display_avatar.url)
            return await ctx.reply(embed=embed, mention_author=False)

        try:
            await ctx.guild.ban(user, reason=f"[Ban por {ctx.author}]: {reason}", delete_message_days=1)
            await ctx.message.add_reaction("👍")
        except discord.Forbidden:
            embed = discord.Embed(
                description="### **Comando: ban**\n\n"
                            "No tengo permisos suficientes para banear a este usuario.\n\n"
                            "```text\n"
                            "Sintaxis: ,ban <usuario> [razón]\n"
                            "Ejemplo:  ,ban @usuario Spam\n"
                            "```",
                color=0x1e1f22
            )
            embed.set_author(name=f"{self.bot.user.name} ayuda", icon_url=self.bot.user.display_avatar.url)
            return await ctx.reply(embed=embed, mention_author=False)
        except Exception:
            embed = discord.Embed(
                description="### **Comando: ban**\n\n"
                            "Ocurrió un error al intentar banear al usuario.\n\n"
                            "```text\n"
                            "Sintaxis: ,ban <usuario> [razón]\n"
                            "Ejemplo:  ,ban @usuario Spam\n"
                            "```",
                color=0x1e1f22
            )
            embed.set_author(name=f"{self.bot.user.name} ayuda", icon_url=self.bot.user.display_avatar.url)
            return await ctx.reply(embed=embed, mention_author=False)

    # ---------------------------------------------------------
    # COMANDO ,an / ,antinuke
    # ---------------------------------------------------------
    @commands.group(name="an", aliases=["antinuke"], invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def antinuke(self, ctx):
        embed = discord.Embed(
            description="### **Comando: antinuke**\n\n"
                        "Gestiona la lista de administradores permitidos en la protección antinuke.\n\n"
                        "```text\n"
                        "Sintaxis: ,an admin <usuario>\n"
                        "         ,an unadmin <usuario>\n"
                        "         ,an admins\n"
                        "Ejemplo:  ,an admin @usuario\n"
                        "```",
            color=0x1e1f22
        )
        embed.set_author(name=f"{self.bot.user.name} ayuda", icon_url=self.bot.user.display_avatar.url)
        return await ctx.reply(embed=embed, mention_author=False)

    @antinuke.command(name="admin")
    @commands.has_permissions(administrator=True)
    async def antinuke_admin(self, ctx, user: discord.User = None):
        if user is None:
            embed = discord.Embed(
                description="### **Comando: antinuke admin**\n\n"
                            "Agrega a un usuario a la lista blanca de antinuke.\n\n"
                            "```text\n"
                            "Sintaxis: ,an admin <usuario>\n"
                            "Ejemplo:  ,an admin @usuario\n"
                            "```",
                color=0x1e1f22
            )
            embed.set_author(name=f"{self.bot.user.name} ayuda", icon_url=self.bot.user.display_avatar.url)
            return await ctx.reply(embed=embed, mention_author=False)

        try:
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS antinuke_admins (
                        guild_id INTEGER,
                        user_id INTEGER,
                        PRIMARY KEY (guild_id, user_id)
                    )
                """)
                await db.execute(
                    "INSERT INTO antinuke_admins (guild_id, user_id) VALUES (?, ?) ON CONFLICT(guild_id, user_id) DO NOTHING",
                    (ctx.guild.id, user.id)
                )
                await db.commit()

            await ctx.message.add_reaction("👍")
        except Exception:
            embed = discord.Embed(
                description="### **Comando: antinuke admin**\n\n"
                            "Ocurrió un error al agregar al usuario a la lista blanca.\n\n"
                            "```text\n"
                            "Sintaxis: ,an admin <usuario>\n"
                            "Ejemplo:  ,an admin @usuario\n"
                            "```",
                color=0x1e1f22
            )
            embed.set_author(name=f"{self.bot.user.name} ayuda", icon_url=self.bot.user.display_avatar.url)
            return await ctx.reply(embed=embed, mention_author=False)

    @antinuke.command(name="unadmin")
    @commands.has_permissions(administrator=True)
    async def antinuke_unadmin(self, ctx, user: discord.User = None):
        if user is None:
            embed = discord.Embed(
                description="### **Comando: antinuke unadmin**\n\n"
                            "Remueve a un usuario de la lista blanca de antinuke.\n\n"
                            "```text\n"
                            "Sintaxis: ,an unadmin <usuario>\n"
                            "Ejemplo:  ,an unadmin @usuario\n"
                            "```",
                color=0x1e1f22
            )
            embed.set_author(name=f"{self.bot.user.name} ayuda", icon_url=self.bot.user.display_avatar.url)
            return await ctx.reply(embed=embed, mention_author=False)

        try:
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS antinuke_admins (
                        guild_id INTEGER,
                        user_id INTEGER,
                        PRIMARY KEY (guild_id, user_id)
                    )
                """)
                await db.execute(
                    "DELETE FROM antinuke_admins WHERE guild_id = ? AND user_id = ?",
                    (ctx.guild.id, user.id)
                )
                await db.commit()

            await ctx.message.add_reaction("👍")
        except Exception:
            embed = discord.Embed(
                description="### **Comando: antinuke unadmin**\n\n"
                            "Ocurrió un error al remover al usuario de la lista blanca.\n\n"
                            "```text\n"
                            "Sintaxis: ,an unadmin <usuario>\n"
                            "Ejemplo:  ,an unadmin @usuario\n"
                            "```",
                color=0x1e1f22
            )
            embed.set_author(name=f"{self.bot.user.name} ayuda", icon_url=self.bot.user.display_avatar.url)
            return await ctx.reply(embed=embed, mention_author=False)

    @antinuke.command(name="admins", aliases=["list"])
    @commands.has_permissions(administrator=True)
    async def antinuke_admins_list(self, ctx):
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS antinuke_admins (
                    guild_id INTEGER,
                    user_id INTEGER,
                    PRIMARY KEY (guild_id, user_id)
                )
            """)
            async with db.execute("SELECT user_id FROM antinuke_admins WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                rows = await cursor.fetchall()

        if not rows:
            embed = discord.Embed(
                description="### **Comando: antinuke admins**\n\n"
                            "No hay ningún usuario registrado como administrador de antinuke en este servidor.\n\n"
                            "```text\n"
                            "Sintaxis: ,an admins\n"
                            "Ejemplo:  ,an admins\n"
                            "```",
                color=0x1e1f22
            )
            embed.set_author(name=f"{self.bot.user.name} ayuda", icon_url=self.bot.user.display_avatar.url)
            return await ctx.reply(embed=embed, mention_author=False)

        list_entries = []
        for i, (u_id,) in enumerate(rows, start=1):
            user_obj = self.bot.get_user(u_id)
            user_name = user_obj.name if user_obj else f"ID: {u_id}"
            list_entries.append(f"`{i}.` **{user_name}** (`{u_id}`)")

        embed = discord.Embed(
            title=f"Administradores Antinuke — {ctx.guild.name}",
            description="\n".join(list_entries[:10]),
            color=0x2b2d31
        )
        embed.set_footer(text=f"Total de administradores: {len(rows)}")
        await ctx.reply(embed=embed, mention_author=False)

    # ---------------------------------------------------------
    # COMANDO ,c / ,clear
    # ---------------------------------------------------------
    @commands.command(name="c", aliases=["clear", "purge"])
    @commands.has_permissions(manage_messages=True)
    async def clear_messages(self, ctx, arg1: str = None, arg2: int = None):
        if arg1 is None:
            embed = discord.Embed(
                description="### **Comando: clear**\n\n"
                            "Elimina mensajes sin confirmación ni respuesta.\n\n"
                            "```text\n"
                            "Sintaxis: ,clear <cantidad>\n"
                            "         clear <usuario> [cantidad]\n"
                            "Ejemplo: ,clear 200\n"
                            "```",
                color=0x1e1f22
            )
            embed.set_author(name=f"{self.bot.user.name} ayuda", icon_url=self.bot.user.display_avatar.url)
            return await ctx.reply(embed=embed, mention_author=False)

        target_member = None
        amount = 100

        if arg1.isdigit():
            amount = int(arg1)
        else:
            try:
                target_member = await commands.MemberConverter().convert(ctx, arg1)
                if arg2 is not None:
                    amount = arg2
            except commands.BadArgument:
                embed = discord.Embed(
                    description="### **Comando: clear**\n\n"
                                "Usuario no válido.\n\n"
                                "```text\n"
                                "Sintaxis: ,clear <cantidad>\n"
                                "         clear <usuario> [cantidad]\n"
                                "Ejemplo: ,clear 200\n"
                                "```",
                    color=0x1e1f22
                )
                embed.set_author(name=f"{self.bot.user.name} ayuda", icon_url=self.bot.user.display_avatar.url)
                return await ctx.reply(embed=embed, mention_author=False)

        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

        def check(m):
            return m.author.id == target_member.id if target_member else True

        await ctx.channel.purge(limit=amount, check=check)

    # ---------------------------------------------------------
    # COMANDOS ,hb / ,hardban Y ,hb list
    # ---------------------------------------------------------
    @commands.group(name="hb", aliases=["hardban"], invoke_without_command=True)
    @commands.has_permissions(ban_members=True)
    async def hardban(self, ctx, user: discord.User = None, *, reason: str = "No especificada"):
        if user is None:
            embed = discord.Embed(
                description="### **Comando: hardban**\n\n"
                            "Banea a un usuario de forma permanente y lo registra en la lista negra del servidor.\n\n"
                            "```text\n"
                            "Sintaxis: ,hb <usuario> [razón]\n"
                            "         ,hb list\n"
                            "Ejemplo:  ,hb @usuario Spam masivo\n"
                            "```",
                color=0x1e1f22
            )
            embed.set_author(name=f"{self.bot.user.name} ayuda", icon_url=self.bot.user.display_avatar.url)
            return await ctx.reply(embed=embed, mention_author=False)

        if user.id == ctx.author.id or user.id == self.bot.user.id:
            embed = discord.Embed(
                description="### **Comando: hardban**\n\n"
                            "Usuario no válido para sanción.\n\n"
                            "```text\n"
                            "Sintaxis: ,hb <usuario> [razón]\n"
                            "         ,hb list\n"
                            "Ejemplo:  ,hb @usuario Spam masivo\n"
                            "```",
                color=0x1e1f22
            )
            embed.set_author(name=f"{self.bot.user.name} ayuda", icon_url=self.bot.user.display_avatar.url)
            return await ctx.reply(embed=embed, mention_author=False)

        try:
            await ctx.guild.ban(user, reason=f"[Hardban por {ctx.author}]: {reason}", delete_message_days=7)

            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS hardbans (
                        guild_id INTEGER, user_id INTEGER, reason TEXT, moderator_id INTEGER,
                        banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (guild_id, user_id)
                    )
                """)
                await db.execute(
                    "INSERT INTO hardbans (guild_id, user_id, reason, moderator_id) VALUES (?, ?, ?, ?) ON CONFLICT(guild_id, user_id) DO UPDATE SET reason = ?, moderator_id = ?",
                    (ctx.guild.id, user.id, reason, ctx.author.id, reason, ctx.author.id)
                )
                await db.commit()

            await ctx.message.add_reaction("👍")
        except discord.Forbidden:
            embed = discord.Embed(
                description="### **Comando: hardban**\n\n"
                            "No tengo permisos suficientes para banear a este usuario.\n\n"
                            "```text\n"
                            "Sintaxis: ,hb <usuario> [razón]\n"
                            "         ,hb list\n"
                            "Ejemplo:  ,hb @usuario Spam masivo\n"
                            "```",
                color=0x1e1f22
            )
            embed.set_author(name=f"{self.bot.user.name} ayuda", icon_url=self.bot.user.display_avatar.url)
            return await ctx.reply(embed=embed, mention_author=False)
        except Exception:
            embed = discord.Embed(
                description="### **Comando: hardban**\n\n"
                            "Ocurrió un error al ejecutar el Hardban.\n\n"
                            "```text\n"
                            "Sintaxis: ,hb <usuario> [razón]\n"
                            "         ,hb list\n"
                            "Ejemplo:  ,hb @usuario Spam masivo\n"
                            "```",
                color=0x1e1f22
            )
            embed.set_author(name=f"{self.bot.user.name} ayuda", icon_url=self.bot.user.display_avatar.url)
            return await ctx.reply(embed=embed, mention_author=False)

    @hardban.command(name="list")
    @commands.has_permissions(ban_members=True)
    async def hardban_list(self, ctx):
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS hardbans (
                    guild_id INTEGER, user_id INTEGER, reason TEXT, moderator_id INTEGER,
                    banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (guild_id, user_id)
                )
            """)
            async with db.execute("SELECT user_id, reason, moderator_id, banned_at FROM hardbans WHERE guild_id = ? ORDER BY banned_at DESC", (ctx.guild.id,)) as cursor:
                rows = await cursor.fetchall()

        if not rows:
            embed = discord.Embed(
                description="### **Comando: hardban list**\n\n"
                            "No hay ningún usuario registrado en la lista de Hardban de este servidor.\n\n"
                            "```text\n"
                            "Sintaxis: ,hb list\n"
                            "Ejemplo:  ,hb list\n"
                            "```",
                color=0x1e1f22
            )
            embed.set_author(name=f"{self.bot.user.name} ayuda", icon_url=self.bot.user.display_avatar.url)
            return await ctx.reply(embed=embed, mention_author=False)

        list_entries = []
        for i, (u_id, reason, mod_id, date) in enumerate(rows, start=1):
            mod_user = self.bot.get_user(mod_id)
            mod_name = mod_user.name if mod_user else f"ID: {mod_id}"
            list_entries.append(f"`{i}.` **ID:** `{u_id}` | **Razón:** {reason}\n> *Mod:* `{mod_name}` • *Fecha:* {date[:10]}")

        embed = discord.Embed(
            title=f"Lista de Hardbans — {ctx.guild.name}",
            description="\n\n".join(list_entries[:10]),
            color=0x2b2d31
        )
        embed.set_footer(text=f"Total de sancionados: {len(rows)}")
        await ctx.reply(embed=embed, mention_author=False)

    # ---------------------------------------------------------
    # COMANDO ,unban (DETECCIÓN DE HARDBAN + ADVERTENCIA ESTILO BLEED)
    # ---------------------------------------------------------
    @commands.command(name="unban")
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx, user: discord.User = None, *, reason: str = "No especificada"):
        if user is None:
            embed = discord.Embed(
                description="### **Comando: unban**\n\n"
                            "Desbanea a un usuario y remueve su registro de Hardban.\n\n"
                            "```text\n"
                            "Sintaxis: ,unban <ID_o_Usuario> [razón]\n"
                            "Ejemplo:  ,unban 123456789012345678 Perdonado\n"
                            "```",
                color=0x1e1f22
            )
            embed.set_author(name=f"{self.bot.user.name} ayuda", icon_url=self.bot.user.display_avatar.url)
            return await ctx.reply(embed=embed, mention_author=False)

        # 1. Verificar si el usuario está en la BD de Hardban
        is_hardbanned = False
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS hardbans (
                    guild_id INTEGER, user_id INTEGER, reason TEXT, moderator_id INTEGER,
                    banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (guild_id, user_id)
                )
            """)
            async with db.execute("SELECT reason FROM hardbans WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, user.id)) as cursor:
                row = await cursor.fetchone()
                if row:
                    is_hardbanned = True

        # 2. Verificar si está baneado en Discord
        is_discord_banned = False
        try:
            ban_entry = await ctx.guild.fetch_ban(user)
            if ban_entry:
                is_discord_banned = True
        except discord.NotFound:
            pass
        except discord.Forbidden:
            embed = discord.Embed(
                description="### **Comando: unban**\n\n"
                            "No tengo permisos suficientes para verificar los baneos de este servidor.\n\n"
                            "```text\n"
                            "Sintaxis: ,unban <ID_o_Usuario> [razón]\n"
                            "Ejemplo:  ,unban 123456789012345678 Perdonado\n"
                            "```",
                color=0x1e1f22
            )
            embed.set_author(name=f"{self.bot.user.name} ayuda", icon_url=self.bot.user.display_avatar.url)
            return await ctx.reply(embed=embed, mention_author=False)

        # Si no tiene ningún tipo de ban
        if not is_discord_banned and not is_hardbanned:
            embed = discord.Embed(
                description="### **Comando: unban**\n\n"
                            "Este usuario no se encuentra baneado ni registrado en la lista de Hardban.\n\n"
                            "```text\n"
                            "Sintaxis: ,unban <ID_o_Usuario> [razón]\n"
                            "Ejemplo:  ,unban 123456789012345678 Perdonado\n"
                            "```",
                color=0x1e1f22
            )
            embed.set_author(name=f"{self.bot.user.name} ayuda", icon_url=self.bot.user.display_avatar.url)
            return await ctx.reply(embed=embed, mention_author=False)

        # 3. Mensaje de advertencia idéntico al de la imagen si detecta Hardban
        if is_hardbanned:
            warning_text = f"⚠️ {ctx.author.mention}: User **{user.name}** is hardbanned. Are you sure you would like to undo this?"
        else:
            warning_text = f"⚠️ {ctx.author.mention}: Are you sure you want to unban **{user.name}**?"

        embed_confirm = discord.Embed(
            description=warning_text,
            color=0x2b2d31
        )

        view = UnbanConfirmView(ctx, user, reason)
        view.message = await ctx.reply(embed=embed_confirm, view=view, mention_author=False)

    @commands.command(name="lock")
    @commands.has_permissions(manage_channels=True)
    async def lock(self, ctx, channel: discord.TextChannel = None):
        target_channel = channel or ctx.channel
        await target_channel.set_permissions(ctx.guild.default_role, send_messages=False)
        try:
            await ctx.message.add_reaction("🔒")
        except Exception:
            pass

    @commands.command(name="unlock")
    @commands.has_permissions(manage_channels=True)
    async def unlock(self, ctx, channel: discord.TextChannel = None):
        target_channel = channel or ctx.channel
        await target_channel.set_permissions(ctx.guild.default_role, send_messages=True)
        try:
            await ctx.message.add_reaction("🔓")
        except Exception:
            pass

    @commands.command(name="hide")
    @commands.has_permissions(manage_channels=True)
    async def hide(self, ctx, channel: discord.TextChannel = None):
        target_channel = channel or ctx.channel
        await target_channel.set_permissions(ctx.guild.default_role, view_channel=False)
        
        embed = discord.Embed(
            description=f"✅ {ctx.author.mention}: Se aplicó **ocultación** a {target_channel.mention}. Se siguen aplicando los permisos específicos de roles y miembros.",
            color=0x2ecc71
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="unhide")
    @commands.has_permissions(manage_channels=True)
    async def unhide(self, ctx, channel: discord.TextChannel = None):
        target_channel = channel or ctx.channel
        await target_channel.set_permissions(ctx.guild.default_role, view_channel=True)
        
        embed = discord.Embed(
            description=f"✅ {ctx.author.mention}: Se aplicó **visibilidad** a {target_channel.mention}. Se siguen aplicando los permisos específicos de roles y miembros.",
            color=0x2ecc71
        )
        await ctx.reply(embed=embed, mention_author=False)

    # ---------------------------------------------------------
    # COMANDO ,nuke
    # ---------------------------------------------------------
    @commands.command(name="nuke")
    @commands.has_permissions(manage_channels=True)
    async def nuke(self, ctx, channel: discord.abc.GuildChannel = None):
        target = channel or ctx.channel
        pos = target.position
        new_channel = await target.clone(reason=f"Nuke ejecutado por {ctx.author}")
        await target.delete(reason=f"Nuke ejecutado por {ctx.author}")
        await new_channel.edit(position=pos)

    # ---------------------------------------------------------
    # COMANDOS ,reglas Y ,premium (CONSERVAN SUS EMOJIS)
    # ---------------------------------------------------------
    @commands.command(name="reglas", aliases=["rules"])
    @commands.has_permissions(administrator=True)
    async def reglas(self, ctx):
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

        embed1 = discord.Embed(
            description=(
                "🤖 **REGLAMENTO DEL SERVIDOR.**\n\n"
                "> *Cualquier situación especificada o no especificada en este reglamento si se es considerada inapropiada podrá acarrear sanciones.*\n\n"
                "> *Los términos y condiciones de Discord también aplican para este servidor al igual que cualquier otro.*\n\n"
                "> [**Términos y condiciones de uso de Discord**](https://discord.com/terms)\n"
                "> [**Políticas de privacidad de Discord**](https://discord.com/privacy)"
            ),
            color=0xd63031
        )
        embed2 = discord.Embed(
            description=(
                "🌸 **Reglas generales:**\n\n"
                "✨ **Respetarse entre todos**\n"
                "> Trata a todos con respeto y cortesía en todo momento. No se tolerará el acoso, la discriminación, los insultos o cualquier comportamiento ofensivo.\n\n"
                "✨ **Lenguaje apropiado:**\n"
                "> Mantén un lenguaje apropiado y evita el uso de blasfemias, insultos o contenido ofensivo en los canales de texto y voz.\n\n"
                "✨ **No spam ni flood**\n"
                "> No hagas spam en ningún canal. Esto incluye publicidad no autorizada, repetición excesiva de mensajes o caracteres, y mensajes irrelevantes.\n\n"
                "✨ **No contenido inapropiado**\n"
                "> No compartas contenido pornográfico, violento, ilegal o cualquier tipo de contenido que viole los términos de servicio de Discord."
            ),
            color=0xe67e22
        )
        embed3 = discord.Embed(
            description=(
                "🌸 **Reglas de Contenido:**\n\n"
                "✨ **Contenido Apropiado**\n"
                "> Publica contenido en el canal adecuado y mantén los temas relacionados con los canales correspondientes.\n\n"
                "✨ **Derechos de autor**\n"
                "> No compartas contenido con derechos de autor sin permiso. Respeta los derechos de propiedad intelectual.\n\n"
                "✨ **No spoilers**\n"
                "> Si compartes información sobre películas, series o videojuegos, utiliza la etiqueta de \"spoiler\" y evita dar detalles importantes sin advertir."
            ),
            color=0xd63031
        )
        embed4 = discord.Embed(
            description=(
                "🌸 **Reglas de Voz y Video:**\n\n"
                "✨ **No micrófono abierto**\n"
                "> Si tienes ruido mantén tu micrófono en modo push-to-talk en canales de voz, a menos que estés en un canal específico designado para charlas generales.\n\n"
                "✨ **Respeto en voz**\n"
                "> No interrumpas a otros cuando estén hablando. Espera tu turno y evita hablar de forma inapropiada."
            ),
            color=0xe67e22
        )
        embed5 = discord.Embed(
            description=(
                "🌸 **Reglas de Seguridad:**\n\n"
                "✨ **No compartas información personal**\n"
                "> No compartas información personal, como direcciones, números de teléfono o información de cuentas personales.\n\n"
                "✨ **No aceptes solicitudes de amistad de desconocidos**\n"
                "> No aceptes solicitudes de amistad de personas que no conozcas fuera del servidor.\n\n"
                "✨ **Mantén tu cuenta segura**\n"
                "> No compartas tu contraseña ni hagas clic en enlaces sospechosos.\n\n"
                "✨ **Prohibición de cuentas alternas**\n"
                "> No utilices cuentas alternativas para evadir sanciones o reglas."
            ),
            color=0xd63031
        )
        embed6 = discord.Embed(
            description=(
                "🌸 **Reglas de Moderación:**\n\n"
                "✨ **Sigue las instrucciones de los moderadores**\n"
                "> Si un moderador te pide que hagas algo o detengas una acción, coopera con ellos de inmediato.\n\n"
                "✨ **Apelaciones y quejas**\n"
                "> Si tienes problemas con las acciones de un moderador, dirígete a un administrador o utiliza un canal específico para apelaciones o quejas."
            ),
            color=0xe67e22
        )

        await ctx.send(embed=embed1)
        await ctx.send(embed=embed2)
        await ctx.send(embeds=[embed3, embed4])
        await ctx.send(embeds=[embed5, embed6])

    @commands.command(name="premium", aliases=["boost", "booster", "premiums"])
    @commands.has_permissions(administrator=True)
    async def premium(self, ctx):
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

        embed = discord.Embed(
            title="Información de los premiums",
            description=(
                "🤎 **Tier 1 (Booster):**\n"
                "• !clearavatars\n"
                "• !clearnames\n"
                "• !tags\n\n"

                "🔘 **Tier 2:**\n"
                "• Todo lo del Tier 1\n"
                "• !cleartags\n"
                "• !autopurge\n"
                "• !autoplay\n"
                "• Comando !mstats parcial (muestra la cantidad de personas que han visto tus historiales, pero no el listado de quienes lo han visto)\n\n"

                "⚡ **Tier 3:**\n"
                "• Todo lo del Tier 2\n"
                "• Comando !mstats completo (Muestra una lista de las ultimas 10 personas que han visto tus nombres, tags, avatares)\n\n"

                "🔮 **Tier 4:**\n"
                "• Todo lo del Tier 3\n"
                "• !ghostmode (Oculta tus vistas a los historiales de otras personas, no apareceras en el listado de los usuarios con tier 3 que pueden ver quienes han visto sus historiales)\n"
                "• Permite que en 3 de los servidores que puedes gestionar el bot cambies su perfil (avatar, nombre y banner), si es compartido la cantidad de servidores aumenta a 5\n\n"

                "👑 **Tier 5:**\n"
                "• Todo lo del Tier 4\n"
                "• El número de servidores en los que puedes modificar el perfil del bot sube a 5 en el plan individual y 10 en el compartido\n"
                "• Ver registros de uso de comandos, permite saber quién uso que comando en cualquier servidor.\n"
                "• Ver logs en el servidor de soporte (Okaa)\n"
                "• Ver Auditoria.\n"
                "• Agregar emojis y stickers al servidor si hay espacios libres\n\n"

                "🍃 **Nota: Para pagar con PayPal abre un ticket**"
            ),
            color=0xff4757
        )
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Moderation(bot))