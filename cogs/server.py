import discord
from discord.ext import commands
import time
import aiosqlite
from config import DB_NAME

# =========================================================
# VISTA DE BOTONES PARA ENLACES (BLEED STYLE)
# =========================================================
class BleedButtonsView(discord.ui.View):
    def __init__(self, guild: discord.Guild):
        super().__init__(timeout=None)
        chat_url = f"https://discord.com/channels/{guild.id}"
        vc_url = f"https://discord.com/channels/{guild.id}"

        self.add_item(discord.ui.Button(label="Chat Here", url=chat_url, style=discord.ButtonStyle.link))
        self.add_item(discord.ui.Button(label=f"Create {guild.name} VC", url=vc_url, style=discord.ButtonStyle.link))


# =========================================================
# MODAL PARA EDITAR EL MENSAJE / SCRIPT
# =========================================================
class ConfigScriptModal(discord.ui.Modal):
    def __init__(self, parent_view, system_type: str, current_msg: str):
        super().__init__(title=f"Configurar {system_type.capitalize()}")
        self.parent_view = parent_view
        self.system_type = system_type

        self.script = discord.ui.TextInput(
            label="Mensaje o script del embed",
            style=discord.TextStyle.paragraph,
            placeholder="Escribe el contenido del mensaje...",
            default=current_msg,
            required=True,
            max_length=2000
        )
        self.add_item(self.script)

    async def on_submit(self, interaction: discord.Interaction):
        table_name = "welcomes" if self.system_type == "welcome" else ("goodbyes" if self.system_type == "goodbye" else "boosts")
        
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    guild_id INTEGER PRIMARY KEY,
                    channel_id INTEGER,
                    status INTEGER DEFAULT 1,
                    message TEXT
                )
            """)
            await db.execute(
                f"UPDATE {table_name} SET message = ? WHERE guild_id = ?",
                (self.script.value, interaction.guild.id)
            )
            await db.commit()

        await self.parent_view.refresh_panel(interaction)


# =========================================================
# PANEL DE CONFIGURACIÓN INTERACTIVO (GREED STYLE)
# =========================================================
class ConfigPanelView(discord.ui.View):
    def __init__(self, ctx, system_type: str):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.system_type = system_type
        self.table = "welcomes" if system_type == "welcome" else ("goodbyes" if system_type == "goodbye" else "boosts")

    async def refresh_panel(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute(f"SELECT channel_id, status, message FROM {self.table} WHERE guild_id = ?", (interaction.guild.id,)) as cursor:
                row = await cursor.fetchone()

        ch_id, status, msg = row if row else (None, 0, "• Please read our rules.\n• Boost for perks.\n• Invite your friends!")
        channel_mention = f"<#{ch_id}>" if ch_id else "*Ninguno*"
        status_text = "✔ Enabled" if status == 1 else "❌ Disabled"

        embed = discord.Embed(color=0x78b159 if status == 1 else 0x2b2d31)
        embed.set_author(name=f"{self.system_type.capitalize()} configuration")
        embed.add_field(name="Channel", value=channel_mention, inline=True)
        embed.add_field(name="Status", value=status_text, inline=True)
        embed.add_field(name="Auto-delete", value="`Off`", inline=True)
        embed.add_field(name="Message", value=f"```text\n{msg[:500]}\n```", inline=False)

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="Selecciona un canal...", row=0)
    async def select_channel(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        selected_ch = select.values[0]
        default_msg = "• Please read our rules.\n• Boost for perks.\n• Invite your friends!"

        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table} (
                    guild_id INTEGER PRIMARY KEY, channel_id INTEGER, status INTEGER DEFAULT 1, message TEXT
                )
            """)
            await db.execute(f"""
                INSERT INTO {self.table} (guild_id, channel_id, status, message)
                VALUES (?, ?, 1, ?)
                ON CONFLICT(guild_id) DO UPDATE SET channel_id = ?, status = 1
            """, (interaction.guild.id, selected_ch.id, default_msg, selected_ch.id))
            await db.commit()

        await self.refresh_panel(interaction)

    @discord.ui.button(label="Set message", style=discord.ButtonStyle.secondary, row=1)
    async def set_message(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute(f"SELECT message FROM {self.table} WHERE guild_id = ?", (interaction.guild.id,)) as cursor:
                row = await cursor.fetchone()
        current_msg = row[0] if row and row[0] else "Escribe tu mensaje aquí..."
        await interaction.response.send_modal(ConfigScriptModal(self, self.system_type, current_msg))

    @discord.ui.button(label="Disable", style=discord.ButtonStyle.danger, row=1)
    async def disable_system(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(f"UPDATE {self.table} SET status = 0 WHERE guild_id = ?", (interaction.guild.id,))
            await db.commit()
        await self.refresh_panel(interaction)

    @discord.ui.button(label="Preview", style=discord.ButtonStyle.secondary, row=1)
    async def preview_system(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user
        guild = interaction.guild

        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute(f"SELECT message FROM {self.table} WHERE guild_id = ?", (guild.id,)) as cursor:
                row = await cursor.fetchone()
        desc = row[0] if row and row[0] else "Mensaje de prueba"

        embed = discord.Embed(description=desc, color=0x2b2d31)
        guild_icon = guild.icon.url if guild.icon else self.ctx.bot.user.display_avatar.url
        
        if self.system_type == "welcome":
            embed.set_author(name=f"We now have {guild.member_count} members!", icon_url=guild_icon)
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"Rep /{guild.name.lower()} for Pic Perms!")
            view = BleedButtonsView(guild)
            content = f"Welcome, {member.mention}!"
        elif self.system_type == "goodbye":
            embed.set_author(name=f"Goodbye, {member.name}", icon_url=guild_icon)
            embed.set_thumbnail(url=member.display_avatar.url)
            view = None
            content = f"Goodbye, {member.mention}."
        else:
            embed.set_author(name=f"New Server Boost!", icon_url=guild_icon)
            embed.set_thumbnail(url=member.display_avatar.url)
            view = None
            content = f"Thanks for boosting, {member.mention}!"

        await interaction.response.send_message(content=content, embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Reset", style=discord.ButtonStyle.danger, row=1)
    async def reset_system(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(f"DELETE FROM {self.table} WHERE guild_id = ?", (interaction.guild.id,))
            await db.commit()
        await self.refresh_panel(interaction)


class Server(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ---------------------------------------------------------
    # COMANDOS GENERALES (Ping & Serverinfo)
    # ---------------------------------------------------------
    @commands.command(name="ping")
    async def ping(self, ctx):
        start_time = time.monotonic()
        msg = await ctx.send("🏓 Calculando latencia...")
        end_time = time.monotonic()
        
        api_latency = round(self.bot.latency * 1000)
        bot_latency = round((end_time - start_time) * 1000)

        embed = discord.Embed(
            description=f"⚡ **API Latency:** `{api_latency}ms`\n⏱️ **Response Time:** `{bot_latency}ms`",
            color=0x2b2d31
        )
        await msg.edit(content=None, embed=embed)

    @commands.command(name="serverinfo", aliases=["si"])
    async def server_info(self, ctx):
        guild = ctx.guild
        embed = discord.Embed(title=f"🏰 {guild.name}", color=0x2b2d31)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        embed.add_field(name="ID", value=f"`{guild.id}`", inline=True)
        embed.add_field(name="Dueño", value=f"{guild.owner.mention}", inline=True)
        embed.add_field(name="Miembros", value=f"`{guild.member_count}`", inline=True)
        embed.add_field(name="Canales", value=f"`{len(guild.channels)}`", inline=True)
        embed.add_field(name="Roles", value=f"`{len(guild.roles)}`", inline=True)
        embed.add_field(name="Boosts", value=f"`{guild.premium_subscription_count}` (Nivel {guild.premium_tier})", inline=True)
        
        await ctx.send(embed=embed)

    # ---------------------------------------------------------
    # SISTEMA DE BIENVENIDA (WELCOME) CON PANEL INTERACTIVO
    # ---------------------------------------------------------
    @commands.group(name="welcome", aliases=["wlc"], invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def welcome(self, ctx):
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT channel_id, status, message FROM welcomes WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()

        ch_id, status, msg = row if row else (None, 0, "No configurado")
        channel_mention = f"<#{ch_id}>" if ch_id else "*Ninguno*"
        status_text = "✔ Enabled" if status == 1 else "❌ Disabled"

        embed = discord.Embed(color=0x78b159 if status == 1 else 0x2b2d31)
        embed.set_author(name="Welcome configuration")
        embed.add_field(name="Channel", value=channel_mention, inline=True)
        embed.add_field(name="Status", value=status_text, inline=True)
        embed.add_field(name="Auto-delete", value="`Off`", inline=True)
        embed.add_field(name="Message", value=f"```text\n{str(msg)[:500]}\n```", inline=False)

        view = ConfigPanelView(ctx, "welcome")
        await ctx.reply(embed=embed, view=view, mention_author=False)

    # ---------------------------------------------------------
    # SISTEMA DE DESPEDIDAS (GOODBYE) CON PANEL INTERACTIVO
    # ---------------------------------------------------------
    @commands.group(name="goodbye", aliases=["despedida"], invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def goodbye(self, ctx):
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT channel_id, status, message FROM goodbyes WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()

        ch_id, status, msg = row if row else (None, 0, "No configurado")
        channel_mention = f"<#{ch_id}>" if ch_id else "*Ninguno*"
        status_text = "✔ Enabled" if status == 1 else "❌ Disabled"

        embed = discord.Embed(color=0x78b159 if status == 1 else 0x2b2d31)
        embed.set_author(name="Goodbye configuration")
        embed.add_field(name="Channel", value=channel_mention, inline=True)
        embed.add_field(name="Status", value=status_text, inline=True)
        embed.add_field(name="Auto-delete", value="`Off`", inline=True)
        embed.add_field(name="Message", value=f"```text\n{str(msg)[:500]}\n```", inline=False)

        view = ConfigPanelView(ctx, "goodbye")
        await ctx.reply(embed=embed, view=view, mention_author=False)

    # ---------------------------------------------------------
    # SISTEMA DE BOOSTS (BOOSTMSG) CON PANEL INTERACTIVO
    # ---------------------------------------------------------
    @commands.group(name="boostmsg", aliases=["boost"], invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def boostmsg(self, ctx):
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT channel_id, status, message FROM boosts WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()

        ch_id, status, msg = row if row else (None, 0, "No configurado")
        channel_mention = f"<#{ch_id}>" if ch_id else "*Ninguno*"
        status_text = "✔ Enabled" if status == 1 else "❌ Disabled"

        embed = discord.Embed(color=0x78b159 if status == 1 else 0x2b2d31)
        embed.set_author(name="Boostmsg configuration")
        embed.add_field(name="Channel", value=channel_mention, inline=True)
        embed.add_field(name="Status", value=status_text, inline=True)
        embed.add_field(name="Auto-delete", value="`Off`", inline=True)
        embed.add_field(name="Message", value=f"```text\n{str(msg)[:500]}\n```", inline=False)

        view = ConfigPanelView(ctx, "boostmsg")
        await ctx.reply(embed=embed, view=view, mention_author=False)

    # ---------------------------------------------------------
    # LISTENERS GLOBALES (EVENTOS AUTOMÁTICOS)
    # ---------------------------------------------------------
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT channel_id, status, message FROM welcomes WHERE guild_id = ?", (guild.id,)) as cursor:
                row = await cursor.fetchone()
        
        if not row or row[1] != 1 or not row[0]:
            return
        
        channel = guild.get_channel(row[0])
        if not channel:
            return

        embed = discord.Embed(description=row[2], color=0x2b2d31)
        guild_icon = guild.icon.url if guild.icon else self.bot.user.display_avatar.url
        embed.set_author(name=f"We now have {guild.member_count} members!", icon_url=guild_icon)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Rep /{guild.name.lower()} for Pic Perms!")

        view = BleedButtonsView(guild)
        await channel.send(content=f"Welcome, {member.mention}!", embed=embed, view=view)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        guild = member.guild
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT channel_id, status, message FROM goodbyes WHERE guild_id = ?", (guild.id,)) as cursor:
                row = await cursor.fetchone()
        
        if not row or row[1] != 1 or not row[0]:
            return
        
        channel = guild.get_channel(row[0])
        if not channel:
            return

        embed = discord.Embed(description=row[2], color=0x2b2d31)
        guild_icon = guild.icon.url if guild.icon else self.bot.user.display_avatar.url
        embed.set_author(name=f"Goodbye, {member.name}", icon_url=guild_icon)
        embed.set_thumbnail(url=member.display_avatar.url)
        await channel.send(content=f"Goodbye, {member.mention}.", embed=embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.premium_since is None and after.premium_since is not None:
            guild = after.guild
            async with aiosqlite.connect(DB_NAME) as db:
                async with db.execute("SELECT channel_id, status, message FROM boosts WHERE guild_id = ?", (guild.id,)) as cursor:
                    row = await cursor.fetchone()
            
            if not row or row[1] != 1 or not row[0]:
                return
            
            channel = guild.get_channel(row[0])
            if not channel:
                return

            embed = discord.Embed(description=row[2], color=0xff73fa)
            guild_icon = guild.icon.url if guild.icon else self.bot.user.display_avatar.url
            embed.set_author(name=f"New Server Boost!", icon_url=guild_icon)
            embed.set_thumbnail(url=after.display_avatar.url)
            await channel.send(content=f"Thanks for boosting, {after.mention}!", embed=embed)

async def setup(bot):
    await bot.add_cog(Server(bot))
