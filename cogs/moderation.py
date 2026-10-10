import discord
from discord.ext import commands
import aiosqlite
import re
import aiohttp
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
# VISTA INTERACTIVA DE CONFIRMACIÓN PARA UNBAN
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
            await self.ctx.guild.unban(self.target_user, reason=f"[Unban por {self.ctx.author}]: {self.reason}")

            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute("DELETE FROM hardbans WHERE guild_id = ? AND user_id = ?", (self.ctx.guild.id, self.target_user.id))
                await db.commit()

            await interaction.response.defer()
            await self.message.delete()

            try:
                await self.ctx.message.add_reaction("👍")
            except discord.HTTPException:
                pass

        except Exception as e:
            embed = discord.Embed(description=f"Ocurrió un error al desbanear al usuario: `{e}`", color=0x1e1f22)
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


# =========================================================
# VISTA INTERACTIVA DE GESTIÓN DE CANAL DE VOZ (Interfaz)
# =========================================================
class VoiceControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("❌ Debes estar conectado a un canal de voz para usar estos controles.", ephemeral=True)
            return False
        return True

    @discord.ui.button(emoji="🔒", style=discord.ButtonStyle.secondary, custom_id="vc_lock", row=0)
    async def lock_vc(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.user.voice.channel
        await channel.set_permissions(interaction.guild.default_role, connect=False)
        await interaction.response.send_message("🔒 Canal de voz bloqueado.", ephemeral=True)

    @discord.ui.button(emoji="🔓", style=discord.ButtonStyle.secondary, custom_id="vc_unlock", row=0)
    async def unlock_vc(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.user.voice.channel
        await channel.set_permissions(interaction.guild.default_role, connect=True)
        await interaction.response.send_message("🔓 Canal de voz desbloqueado.", ephemeral=True)

    @discord.ui.button(emoji="🙈", style=discord.ButtonStyle.secondary, custom_id="vc_hide", row=0)
    async def hide_vc(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.user.voice.channel
        await channel.set_permissions(interaction.guild.default_role, view_channel=False)
        await interaction.response.send_message("🙈 Canal de voz ocultado.", ephemeral=True)

    @discord.ui.button(emoji="👀", style=discord.ButtonStyle.secondary, custom_id="vc_unhide", row=0)
    async def unhide_vc(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.user.voice.channel
        await channel.set_permissions(interaction.guild.default_role, view_channel=True)
        await interaction.response.send_message("👀 Canal de voz visible.", ephemeral=True)

    @discord.ui.button(emoji="👥", style=discord.ButtonStyle.secondary, custom_id="vc_limit", row=1)
    async def limit_vc(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.user.voice.channel
        current = channel.user_limit
        new_limit = 0 if current > 0 else 5
        await channel.edit(user_limit=new_limit)
        await interaction.response.send_message(f"👥 Límite cambiado a: {'Sin límite' if new_limit == 0 else new_limit}", ephemeral=True)

    @discord.ui.button(emoji="➕", style=discord.ButtonStyle.secondary, custom_id="vc_allow", row=1)
    async def allow_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("ℹ️ Usa `/vc allow @usuario` para permitir el acceso.", ephemeral=True)

    @discord.ui.button(emoji="👢", style=discord.ButtonStyle.secondary, custom_id="vc_kick", row=1)
    async def kick_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("ℹ️ Usa `/vc kick @usuario` para expulsar a alguien.", ephemeral=True)

    @discord.ui.button(emoji="✏️", style=discord.ButtonStyle.secondary, custom_id="vc_rename", row=1)
    async def rename_vc(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("ℹ️ Usa `/vc name <nombre>` para cambiar el nombre.", ephemeral=True)


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.snipes = {}
        self.active_jtc = {}
    # ---------------------------------------------------------
    # LISTENERS GLOBALES
    # ---------------------------------------------------------
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS hardbans (
                    guild_id INTEGER, user_id INTEGER, reason TEXT, moderator_id INTEGER,
                    banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (guild_id, user_id)
                )
            """)
            async with db.execute("SELECT reason FROM hardbans WHERE guild_id = ? AND user_id = ?", (member.guild.id, member.id)) as cursor:
                row = await cursor.fetchone()
                if row:
                    try:
                        await member.ban(reason=f"[Hardban Automático]: {row[0]}")
                    except discord.HTTPException:
                        pass

            await db.execute("CREATE TABLE IF NOT EXISTS welcomes (guild_id INTEGER PRIMARY KEY, channel_id INTEGER, message TEXT)")
            async with db.execute("SELECT channel_id, message FROM welcomes WHERE guild_id = ?", (member.guild.id,)) as cursor:
                w_row = await cursor.fetchone()
                if w_row:
                    ch_id, text = w_row
                    channel = member.guild.get_channel(ch_id)
                    if channel:
                        formatted_text = text.replace("{user}", member.mention).replace("{server}", member.guild.name)
                        embed = discord.Embed(description=formatted_text, color=0x2b2d31)
                        embed.set_author(name=f"Welcome, @{member.name}!", icon_url=member.display_avatar.url)
                        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("CREATE TABLE IF NOT EXISTS goodbyes (guild_id INTEGER PRIMARY KEY, channel_id INTEGER, message TEXT)")
            async with db.execute("SELECT channel_id, message FROM goodbyes WHERE guild_id = ?", (member.guild.id,)) as cursor:
                g_row = await cursor.fetchone()
                if g_row:
                    ch_id, text = g_row
                    channel = member.guild.get_channel(ch_id)
                    if channel:
                        formatted_text = text.replace("{user}", str(member)).replace("{server}", member.guild.name)
                        embed = discord.Embed(description=formatted_text, color=0x2b2d31)
                        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.premium_since is None and after.premium_since is not None:
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute("CREATE TABLE IF NOT EXISTS boosts (guild_id INTEGER PRIMARY KEY, channel_id INTEGER, message TEXT)")
                async with db.execute("SELECT channel_id, message FROM boosts WHERE guild_id = ?", (after.guild.id,)) as cursor:
                    b_row = await cursor.fetchone()
                    if b_row:
                        ch_id, text = b_row
                        channel = after.guild.get_channel(ch_id)
                        if channel:
                            formatted_text = text.replace("{user}", after.mention).replace("{server}", after.guild.name)
                            embed = discord.Embed(description=formatted_text, color=0xff73fa)
                            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS jtc_config (
                    guild_id INTEGER PRIMARY KEY, category_id INTEGER, jtc_channel_id INTEGER
                )
            """)
            async with db.execute("SELECT category_id, jtc_channel_id FROM jtc_config WHERE guild_id = ?", (member.guild.id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    cat_id, jtc_ch_id = row
                    if after.channel and after.channel.id == jtc_ch_id:
                        category = member.guild.get_channel(cat_id)
                        new_vc = await member.guild.create_voice_channel(
                            name=f"🔊 ┃ {member.name}",
                            category=category,
                            reason=f"Canal temporal JTC de {member}"
                        )
                        await member.move_to(new_vc)
                        self.active_jtc[new_vc.id] = member.id

                    if before.channel and before.channel.id in self.active_jtc:
                        if len(before.channel.members) == 0:
                            try:
                                await before.channel.delete(reason="Canal temporal JTC vacío")
                            except Exception:
                                pass
                            self.active_jtc.pop(before.channel.id, None)

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
    # COMANDO SETUP VC & INTERFACE
    # ---------------------------------------------------------
    @commands.command(name="setupvc", aliases=["setupinterface"])
    @commands.has_permissions(administrator=True)
    async def setup_vc(self, ctx):
        # Primero eliminamos el mensaje del comando si es posible
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

        guild = ctx.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=False, add_reactions=False)
        }

        try:
            # 1. Crear categoría y canales
            category = await guild.create_category("VC", reason="Configuración de canales de voz y panel")
            text_channel = await guild.create_text_channel("📝 ┃ interface", category=category, overwrites=overwrites)
            voice_channel = await guild.create_voice_channel("➕ ┃ jtc", category=category)

            # 2. Guardar en la base de datos
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS jtc_config (
                        guild_id INTEGER PRIMARY KEY, category_id INTEGER, jtc_channel_id INTEGER
                    )
                """)
                await db.execute(
                    "INSERT INTO jtc_config (guild_id, category_id, jtc_channel_id) VALUES (?, ?, ?) ON CONFLICT(guild_id) DO UPDATE SET category_id = ?, jtc_channel_id = ?",
                    (guild.id, category.id, voice_channel.id, category.id, voice_channel.id)
                )
                await db.commit()

            # 3. Enviar el embed con la vista de botones
            embed = discord.Embed(
                description=(
                    "Puede utilizar esta interfaz para administrar su canal de voz.\n\n"
                    "¡También puede utilizar los comandos con barra diagonal `/vc`!"
                ),
                color=0x2b2d31
            )
            embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.display_avatar.url)
            view = VoiceControlView()
            
            await text_channel.send(embed=embed, view=view)
            await ctx.send(f"✅ ¡Sistema de canales de voz e interfaz configurado correctamente en la categoría {category.name}!", delete_after=10)

        except Exception as e:
            # Si ocurre cualquier error, lo imprimimos en la consola de tu terminal para saber exacto qué falló
            print(f"❌ Error detallado en setupvc: {e}")
            await ctx.send(f"❌ Ocurrió un error al configurar el panel: `{e}`", delete_after=15)

    # ---------------------------------------------------------
    # ROLES Y COMANDO ,r
    # ---------------------------------------------------------
    @commands.command(name="roles", aliases=["rolelist", "roleslist"])
    async def list_roles(self, ctx):
        roles = [r for r in reversed(ctx.guild.roles) if not r.is_default()]
        if not roles:
            embed = discord.Embed(description="Este servidor no tiene roles personalizados.", color=0x1e1f22)
            return await ctx.reply(embed=embed, mention_author=False)

        paginator = RolesPaginator(ctx, roles, per_page=10)
        embed = paginator.build_embed()
        paginator.message = await ctx.reply(embed=embed, view=paginator, mention_author=False)

    @commands.group(name="r", invoke_without_command=True)
    @commands.has_permissions(manage_roles=True)
    async def role_group(self, ctx, member: discord.Member = None, *, roles_input: str = None):
        if member and roles_input:
            role_names = [r.strip() for r in roles_input.split(",")]
            assigned, removed = [], []
            for r_name in role_names:
                role = discord.utils.get(ctx.guild.roles, name=r_name)
                if role:
                    if role in member.roles:
                        await member.remove_roles(role)
                        removed.append(role.name)
                    else:
                        await member.add_roles(role)
                        assigned.append(role.name)
            embed = discord.Embed(
                description=f"✅ Roles actualizados para {member.mention}\n> Agregados: `{', '.join(assigned) or 'Ninguno'}`\n> Retirados: `{', '.join(removed) or 'Ninguno'}`",
                color=0x2ecc71
            )
            return await ctx.reply(embed=embed, mention_author=False)

        embed = discord.Embed(
            description="### **Comando: role**\n\nAñade un rol si el miembro no lo tiene, o lo retira si ya lo tiene.\n\n```text\nSintaxis: ,r <usuario> <rol, rol, ...>\n         ,r <create|edit|icon|delete>\nEjemplo:  ,r @Juan Moderadores, Miembro\n```",
            color=0x1e1f22
        )
        embed.set_author(name=f"{self.bot.user.name} ayuda", icon_url=self.bot.user.display_avatar.url)
        await ctx.reply(embed=embed, mention_author=False)

    @role_group.command(name="create")
    @commands.has_permissions(manage_roles=True)
    async def role_create(self, ctx, *, name: str):
        try:
            role = await ctx.guild.create_role(name=name, reason=f"Creado por {ctx.author}")
            embed = discord.Embed(description=f"✅ {ctx.author.mention}: Se ha creado el rol {role.mention} exitosamente.", color=0x2ecc71)
            await ctx.reply(embed=embed, mention_author=False)
        except Exception as e:
            await ctx.reply(f"❌ Error al crear el rol: `{e}`", mention_author=False)

    @role_group.command(name="icon")
    @commands.has_permissions(manage_roles=True)
    async def role_icon(self, ctx, role: discord.Role, *, icon_input: str = None):
        if not ctx.guild.premium_tier >= 2:
            return await ctx.reply("❌ Este servidor necesita ser Nivel 2 de Boost para usar iconos en los roles.", mention_author=False)
        if not icon_input:
            embed = discord.Embed(
                description="### **Comando: role icon**\n\nEstablece el icono de un rol con un emoji, URL o adjunto, o retíralo.\n\n```text\nSintaxis: ,r icon <rol> [emoji|URL|remove]\nEjemplo:  ,r icon Moderadores remove\n```",
                color=0x1e1f22
            )
            embed.set_author(name=f"{self.bot.user.name} ayuda", icon_url=self.bot.user.display_avatar.url)
            return await ctx.reply(embed=embed, mention_author=False)

        try:
            icon_data = None
            if icon_input.lower() == "remove":
                icon_data = None
            elif ctx.message.attachments:
                icon_data = await ctx.message.attachments[0].read()
            elif icon_input.startswith("http"):
                async with aiohttp.ClientSession() as session:
                    async with session.get(icon_input) as resp:
                        if resp.status == 200:
                            icon_data = await resp.read()
            await role.edit(display_icon=icon_data, reason=f"Modificado por {ctx.author}")
            await ctx.message.add_reaction("👍")
        except Exception as e:
            await ctx.reply(f"❌ No se pudo actualizar el icono: `{e}`", mention_author=False)

    # ---------------------------------------------------------
    # COMANDO ,drag
    # ---------------------------------------------------------
    @commands.command(name="drag", aliases=["d"])
    @commands.has_permissions(move_members=True)
    async def drag(self, ctx, *, args: str = None):
        if not args:
            embed = discord.Embed(
                description="### **Comando: drag**\n\nMueve miembros a un canal de voz. Sepáralos con comas. Usa `|` antes del destino para evitar nombres ambiguos.\n\n```text\nSintaxis: ,drag <usuario, usuario, ...> [canal]\n         drag <usuario, ...> | <canal>\nEjemplo:  ,drag @Juan, 123456789012345678 | General\n```",
                color=0x1e1f22
            )
            embed.set_author(name=f"{self.bot.user.name} ayuda", icon_url=self.bot.user.display_avatar.url)
            return await ctx.reply(embed=embed, mention_author=False)

        target_channel = None
        members_str = args

        if "|" in args:
            parts = args.split("|")
            members_str = parts[0].strip()
            ch_name = parts[1].strip()
            target_channel = discord.utils.get(ctx.guild.voice_channels, name=ch_name) or discord.utils.get(ctx.guild.stage_channels, name=ch_name)
        else:
            target_channel = ctx.author.voice.channel if ctx.author.voice else None

        if not target_channel:
            return await ctx.reply("❌ Debes estar en un canal de voz o especificar uno válido usando `|`.", mention_author=False)

        member_items = [m.strip() for m in members_str.split(",")]
        moved_count = 0

        for item in member_items:
            member = None
            if item.startswith("<@") and item.endswith(">"):
                m_id = re.findall(r"[0-9]+", item)
                if m_id:
                    member = ctx.guild.get_member(int(m_id[0]))
            elif item.isdigit():
                member = ctx.guild.get_member(int(item))
            else:
                member = discord.utils.get(ctx.guild.members, name=item)

            if member and member.voice:
                try:
                    await member.move_to(target_channel, reason=f"Drag por {ctx.author}")
                    moved_count += 1
                except Exception:
                    pass

        await ctx.message.add_reaction("👍" if moved_count > 0 else "❌")


  
    class WelcomeView(discord.ui.View):
     def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        chat_url = f"https://discord.com/channels/{guild_id}"
        vc_url = f"https://discord.com/channels/{guild_id}"
        
        self.add_item(discord.ui.Button(label="Chat Here", url=chat_url, style=discord.ButtonStyle.link))
        self.add_item(discord.ui.Button(label="Create Saki VC", url=vc_url, style=discord.ButtonStyle.link))


# =========================================================
# COMANDOS Y EVENTOS DE BIENVENIDA, GOODBYE Y BOOST
# =========================================================
class Server(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ---------------------------------------------------------
    # SISTEMA DE BIENVENIDA
    # ---------------------------------------------------------
    @commands.group(name="welcome", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def welcome(self, ctx):
        embed = discord.Embed(
            description="### **Sistema de Bienvenidas**\n\n```text\nSintaxis: ,welcome set <canal> <mensaje>\n         ,welcome remove\n```",
            color=0x1e1f22
        )
        await ctx.reply(embed=embed, mention_author=False)

    @welcome.command(name="set")
    @commands.has_permissions(administrator=True)
    async def welcome_set(self, ctx, channel: discord.TextChannel, *, message: str):
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("CREATE TABLE IF NOT EXISTS welcomes (guild_id INTEGER PRIMARY KEY, channel_id INTEGER, message TEXT)")
            await db.execute(
                "INSERT INTO welcomes (guild_id, channel_id, message) VALUES (?, ?, ?) ON CONFLICT(guild_id) DO UPDATE SET channel_id = ?, message = ?",
                (ctx.guild.id, channel.id, message, channel.id, message)
            )
            await db.commit()
        await ctx.message.add_reaction("👍")

    @welcome.command(name="remove", aliases=["delete"])
    @commands.has_permissions(administrator=True)
    async def welcome_remove(self, ctx):
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("DELETE FROM welcomes WHERE guild_id = ?", (ctx.guild.id,))
            await db.commit()
        await ctx.message.add_reaction("👍")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT channel_id, message FROM welcomes WHERE guild_id = ?", (guild.id,)) as cursor:
                row = await cursor.fetchone()

        if not row:
            return

        channel_id, custom_message = row
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

        # Personaliza el mensaje con el usuario, servidor y total de miembros
        content = custom_message.replace("{user}", member.mention).replace("{server}", guild.name).replace("{members}", str(guild.member_count))

        embed = discord.Embed(
            description=(
                f"We now have **{guild.member_count}** members!\n\n"
                "• Please read our rules.\n"
                "• Boost for perks.\n"
                "• Invite your friends!"
            ),
            color=0x2b2d31
        )
        
        if guild.icon:
            embed.set_author(name=guild.name, icon_url=guild.icon.url)
        else:
            embed.set_author(name=guild.name)

        view = WelcomeView(guild.id)
        await channel.send(content=content, embed=embed, view=view)
        
    # ---------------------------------------------------------
    # SISTEMA DE DESPEDIDAS (GOODBYE)
    # ---------------------------------------------------------
    @commands.group(name="goodbye", aliases=["despedida"], invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def goodbye(self, ctx):
        embed = discord.Embed(
            description="### **Sistema de Despedidas**\n\n```text\nSintaxis: ,goodbye set <canal> <mensaje>\n         ,goodbye remove\n```",
            color=0x1e1f22
        )
        await ctx.reply(embed=embed, mention_author=False)

    @goodbye.command(name="set")
    @commands.has_permissions(administrator=True)
    async def goodbye_set(self, ctx, channel: discord.TextChannel, *, message: str):
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("CREATE TABLE IF NOT EXISTS goodbyes (guild_id INTEGER PRIMARY KEY, channel_id INTEGER, message TEXT)")
            await db.execute(
                "INSERT INTO goodbyes (guild_id, channel_id, message) VALUES (?, ?, ?) ON CONFLICT(guild_id) DO UPDATE SET channel_id = ?, message = ?",
                (ctx.guild.id, channel.id, message, channel.id, message)
            )
            await db.commit()
        await ctx.message.add_reaction("👍")

    @goodbye.command(name="remove", aliases=["delete"])
    @commands.has_permissions(administrator=True)
    async def goodbye_remove(self, ctx):
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("DELETE FROM goodbyes WHERE guild_id = ?", (ctx.guild.id,))
            await db.commit()
        await ctx.message.add_reaction("👍")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        guild = member.guild
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT channel_id, message FROM goodbyes WHERE guild_id = ?", (guild.id,)) as cursor:
                row = await cursor.fetchone()

        if not row:
            return

        channel_id, custom_message = row
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

        formatted_message = custom_message.replace("{user}", member.name).replace("{server}", guild.name)
        await channel.send(formatted_message)

    # ---------------------------------------------------------
    # SISTEMA DE BOOSTS (BOOSTMSG)
    # ---------------------------------------------------------
    @commands.group(name="boostmsg", aliases=["boost"], invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def boostmsg(self, ctx):
        embed = discord.Embed(
            description="### **Sistema de Mensajes de Boost**\n\n```text\nSintaxis: ,boostmsg set <canal> <mensaje>\n         ,boostmsg remove\n```",
            color=0x1e1f22
        )
        await ctx.reply(embed=embed, mention_author=False)

    @boostmsg.command(name="set")
    @commands.has_permissions(administrator=True)
    async def boostmsg_set(self, ctx, channel: discord.TextChannel, *, message: str):
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("CREATE TABLE IF NOT EXISTS boosts (guild_id INTEGER PRIMARY KEY, channel_id INTEGER, message TEXT)")
            await db.execute(
                "INSERT INTO boosts (guild_id, channel_id, message) VALUES (?, ?, ?) ON CONFLICT(guild_id) DO UPDATE SET channel_id = ?, message = ?",
                (ctx.guild.id, channel.id, message, channel.id, message)
            )
            await db.commit()
        await ctx.message.add_reaction("👍")

    @boostmsg.command(name="remove", aliases=["delete"])
    @commands.has_permissions(administrator=True)
    async def boostmsg_remove(self, ctx):
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("DELETE FROM boosts WHERE guild_id = ?", (ctx.guild.id,))
            await db.commit()
        await ctx.message.add_reaction("👍")

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.premium_since is None and after.premium_since is not None:
            guild = after.guild
            async with aiosqlite.connect(DB_NAME) as db:
                async with db.execute("SELECT channel_id, message FROM boosts WHERE guild_id = ?", (guild.id,)) as cursor:
                    row = await cursor.fetchone()

            if not row:
                return

            channel_id, custom_message = row
            channel = self.bot.get_channel(channel_id)
            if not channel:
                return

            formatted_message = custom_message.replace("{user}", after.name).replace("{server}", guild.name)
            await channel.send(formatted_message)
    # ---------------------------------------------------------
    # UTILIDADES Y MODERACIÓN
    # ---------------------------------------------------------
    @commands.command(name="s", aliases=["snipe"])
    async def snipe(self, ctx):
        snipe_data = self.snipes.get(ctx.channel.id)
        if not snipe_data:
            return await ctx.reply("No hay ningún mensaje borrado recientemente en este canal.", mention_author=False)

        embed = discord.Embed(description=snipe_data["content"] or "*[Mensaje sin texto o solo archivo]*", color=0x2b2d31, timestamp=snipe_data["created_at"])
        embed.set_author(name=f"{snipe_data['author']} ({snipe_data['author'].id})", icon_url=snipe_data["author"].display_avatar.url)
        if snipe_data["attachment"]:
            embed.set_image(url=snipe_data["attachment"])
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="cs", aliases=["clearsnipe"])
    @commands.has_permissions(manage_messages=True)
    async def clear_snipe(self, ctx):
        if ctx.channel.id in self.snipes:
            del self.snipes[ctx.channel.id]
        try:
            await ctx.message.add_reaction("✅")
        except discord.HTTPException:
            pass

    @commands.command(name="ban")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, user: discord.User = None, *, reason: str = "No especificada"):
        if user is None:
            return await ctx.reply("Sintaxis: `,ban <usuario> [razón]`", mention_author=False)
        await ctx.guild.ban(user, reason=f"[Ban por {ctx.author}]: {reason}")
        await ctx.message.add_reaction("👍")

    # ---------------------------------------------------------
    # HARDBANS Y LISTA HARDBAN
    # ---------------------------------------------------------
    @commands.group(name="hb", aliases=["hardban"], invoke_without_command=True)
    @commands.has_permissions(ban_members=True)
    async def hardban(self, ctx, user: discord.User = None, *, reason: str = "No especificada"):
        if user is None:
            embed = discord.Embed(description="### **Comando: hardban**\n\nBanea de forma permanente y registra en lista negra.\n\n```text\nSintaxis: ,hb <usuario> [razón]\n         ,hb list\n```", color=0x1e1f22)
            return await ctx.reply(embed=embed, mention_author=False)

        # Verificación de Administrador del Antinuke
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT 1 FROM antinuke_admins WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, ctx.author.id)) as cursor:
                is_an_admin = await cursor.fetchone()

        if not is_an_admin and ctx.author.id != ctx.guild.owner_id:
            embed = discord.Embed(
                description=f"⚠️ {ctx.author.mention}: Debes ser **administrador del antinuke** para ejecutar este comando.",
                color=0x2b2d31
            )
            return await ctx.reply(embed=embed, mention_author=False)

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
            async with db.execute("SELECT user_id, reason FROM hardbans WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                rows = await cursor.fetchall()

        if not rows:
            embed = discord.Embed(
                description="### **Hardbans**\n\nNo se encontraron registros de hardbans activos en este servidor.",
                color=0x2b2d31
            )
            embed.set_footer(text="Página 1/1 • 0 registros\nen honor a lockfile")
            return await ctx.reply(embed=embed, mention_author=False)

        list_entries = []
        for i, (u_id, reason) in enumerate(rows[:10], start=1):
            list_entries.append(f"`{i}` <@{u_id}> — `{u_id}`")

        embed = discord.Embed(
            title="Hardbans",
            description="\n".join(list_entries),
            color=0x2b2d31
        )
        embed.set_footer(text=f"Página 1/1 • {len(rows)} registros\nen honor a lockfile")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="unban")
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx, user: discord.User = None, *, reason: str = "No especificada"):
        if user is None:
            return await ctx.reply("Sintaxis: `,unban <ID_o_Usuario> [razón]`", mention_author=False)

        is_hardbanned = False
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT reason FROM hardbans WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, user.id)) as cursor:
                if await cursor.fetchone():
                    is_hardbanned = True

        warning_text = f"⚠️ {ctx.author.mention}: User **{user.name}** is hardbanned. Are you sure you would like to undo this?" if is_hardbanned else f"⚠️ {ctx.author.mention}: Are you sure you want to unban **{user.name}**?"
        embed_confirm = discord.Embed(description=warning_text, color=0x2b2d31)
        view = UnbanConfirmView(ctx, user, reason)
        view.message = await ctx.reply(embed=embed_confirm, view=view, mention_author=False)

    @commands.command(name="lock")
    @commands.has_permissions(manage_channels=True)
    async def lock(self, ctx, channel: discord.TextChannel = None):
        target = channel or ctx.channel
        await target.set_permissions(ctx.guild.default_role, send_messages=False)
        try:
            await ctx.message.add_reaction("🔒")
        except Exception:
            pass

    @commands.command(name="unlock")
    @commands.has_permissions(manage_channels=True)
    async def unlock(self, ctx, channel: discord.TextChannel = None):
        target = channel or ctx.channel
        await target.set_permissions(ctx.guild.default_role, send_messages=True)
        try:
            await ctx.message.add_reaction("🔓")
        except Exception:
            pass

    @commands.command(name="hide")
    @commands.has_permissions(manage_channels=True)
    async def hide(self, ctx, channel: discord.TextChannel = None):
        target = channel or ctx.channel
        await target.set_permissions(ctx.guild.default_role, view_channel=False)
        embed = discord.Embed(description=f"✅ {ctx.author.mention}: Se aplicó **ocultación** a {target.mention}.", color=0x2ecc71)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="unhide")
    @commands.has_permissions(manage_channels=True)
    async def unhide(self, ctx, channel: discord.TextChannel = None):
        target = channel or ctx.channel
        await target.set_permissions(ctx.guild.default_role, view_channel=True)
        embed = discord.Embed(description=f"✅ {ctx.author.mention}: Se aplicó **visibilidad** a {target.mention}.", color=0x2ecc71)
        await ctx.reply(embed=embed, mention_author=False)

   
    

    # ---------------------------------------------------------
    # REGLAS Y PREMIUM (CONSERVADOS ÍNTEGRAMENTE)
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

    @commands.command(name="premium", aliases=["booster", "premiums"])
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

