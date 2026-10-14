import discord
from discord.ext import commands
import aiosqlite
from config import DB_NAME

class BleedButtonsView(discord.ui.View):
    def __init__(self, guild: discord.Guild, chat_channel_id: int = None, vc_channel_id: int = None):
        super().__init__(timeout=None)
        
        chat_url = f"https://discord.com/channels/{guild.id}/{chat_channel_id}" if chat_channel_id else f"https://discord.com/channels/{guild.id}"
        vc_url = f"https://discord.com/channels/{guild.id}/{vc_channel_id}" if vc_channel_id else f"https://discord.com/channels/{guild.id}"

        self.add_item(discord.ui.Button(label="Chat Here", url=chat_url, style=discord.ButtonStyle.link))
        self.add_item(discord.ui.Button(label=f"Create {guild.name} VC", url=vc_url, style=discord.ButtonStyle.link))

class ConfigScriptModal(discord.ui.Modal):
    def __init__(self, parent_view, system_type: str, current_msg: str):
        super().__init__(title=f"Configurar {system_type.capitalize()}")
        self.parent_view = parent_view
        self.system_type = system_type

        self.script = discord.ui.TextInput(
            label="Mensaje del sistema",
            style=discord.TextStyle.paragraph,
            placeholder="Escribe el contenido del mensaje...",
            default=current_msg,
            required=True,
            max_length=2000
        )
        self.add_item(self.script)

    async def on_submit(self, interaction: discord.Interaction):
        table_map = {"welcome": "welcomes", "goodbye": "goodbyes", "boostmsg": "boosts"}
        table_name = table_map.get(self.system_type, "welcomes")
        
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                f"UPDATE {table_name} SET message = ? WHERE guild_id = ?",
                (self.script.value, interaction.guild.id)
            )
            await db.commit()

        await self.parent_view.refresh_panel(interaction)

class ChatChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, parent_view):
        # ✅ PERMITE CANALES DE TEXTO Y DE ANUNCIOS/NOTICIAS
        super().__init__(
            placeholder="Canal para el botón 'Chat Here'...", 
            channel_types=[discord.ChannelType.text, discord.ChannelType.news], 
            row=1
        )
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        selected_ch = self.values[0]
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS welcomes (
                    guild_id INTEGER PRIMARY KEY, 
                    channel_id INTEGER, 
                    status INTEGER DEFAULT 1, 
                    message TEXT,
                    chat_channel_id INTEGER,
                    vc_channel_id INTEGER
                )
            """)
            await db.execute("UPDATE welcomes SET chat_channel_id = ? WHERE guild_id = ?", (selected_ch.id, interaction.guild.id))
            await db.commit()
        await self.parent_view.refresh_panel(interaction)

class VcChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, parent_view):
        super().__init__(placeholder="Canal para el botón 'Create VC'...", channel_types=[discord.ChannelType.voice], row=2)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        selected_ch = self.values[0]
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS welcomes (
                    guild_id INTEGER PRIMARY KEY, 
                    channel_id INTEGER, 
                    status INTEGER DEFAULT 1, 
                    message TEXT,
                    chat_channel_id INTEGER,
                    vc_channel_id INTEGER
                )
            """)
            await db.execute("UPDATE welcomes SET vc_channel_id = ? WHERE guild_id = ?", (selected_ch.id, interaction.guild.id))
            await db.commit()
        await self.parent_view.refresh_panel(interaction)

class ConfigPanelView(discord.ui.View):
    def __init__(self, ctx, system_type: str):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.system_type = system_type
        table_map = {"welcome": "welcomes", "goodbye": "goodbyes", "boostmsg": "boosts"}
        self.table = table_map.get(system_type, "welcomes")
        
        self.add_item(ChannelSelectMenu(self.table, self))
        
        if system_type == "welcome":
            self.add_item(ChatChannelSelect(self))
            self.add_item(VcChannelSelect(self))

    async def refresh_panel(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_NAME) as db:
            if self.system_type == "welcome":
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS welcomes (
                        guild_id INTEGER PRIMARY KEY, 
                        channel_id INTEGER, 
                        status INTEGER DEFAULT 1, 
                        message TEXT,
                        chat_channel_id INTEGER,
                        vc_channel_id INTEGER
                    )
                """)
                async with db.execute(f"SELECT channel_id, status, message, chat_channel_id, vc_channel_id FROM {self.table} WHERE guild_id = ?", (interaction.guild.id,)) as cursor:
                    row = await cursor.fetchone()
                ch_id, status, msg, chat_ch, vc_ch = row if row else (None, 0, "• Please read our rules.\n• Boost for perks.", None, None)
                chat_mention = f"<#{chat_ch}>" if chat_ch else "*Predeterminado*"
                vc_mention = f"<#{vc_ch}>" if vc_ch else "*Predeterminado*"
            else:
                await db.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.table} (
                        guild_id INTEGER PRIMARY KEY, 
                        channel_id INTEGER, 
                        status INTEGER DEFAULT 1, 
                        message TEXT
                    )
                """)
                async with db.execute(f"SELECT channel_id, status, message FROM {self.table} WHERE guild_id = ?", (interaction.guild.id,)) as cursor:
                    row = await cursor.fetchone()
                ch_id, status, msg = row if row else (None, 0, "• Please read our rules.\n• Boost for perks.")

        channel_mention = f"<#{ch_id}>" if ch_id else "*Ninguno*"
        status_text = "✔ Enabled" if status == 1 else "❌ Disabled"

        embed = discord.Embed(color=0x78b159 if status == 1 else 0x2b2d31)
        embed.set_author(name=f"{self.system_type.capitalize()} configuration")
        embed.add_field(name="Channel", value=channel_mention, inline=True)
        embed.add_field(name="Status", value=status_text, inline=True)
        
        if self.system_type == "welcome":
            embed.add_field(name="Botón Chat", value=chat_mention, inline=True)
            embed.add_field(name="Botón VC", value=vc_mention, inline=True)

        embed.add_field(name="Message", value=f"```text\n{str(msg)[:500]}\n```", inline=False)

        try:
            await interaction.response.edit_message(embed=embed, view=self)
        except discord.InteractionResponded:
            await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="Set message", style=discord.ButtonStyle.secondary, row=3)
    async def set_message(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute(f"SELECT message FROM {self.table} WHERE guild_id = ?", (interaction.guild.id,)) as cursor:
                row = await cursor.fetchone()
        current_msg = row[0] if row and row[0] else "Escribe tu mensaje aquí..."
        await interaction.response.send_modal(ConfigScriptModal(self, self.system_type, current_msg))

    @discord.ui.button(label="Disable", style=discord.ButtonStyle.danger, row=3)
    async def disable_system(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(f"UPDATE {self.table} SET status = 0 WHERE guild_id = ?", (interaction.guild.id,))
            await db.commit()
        await self.refresh_panel(interaction)

    @discord.ui.button(label="Preview", style=discord.ButtonStyle.secondary, row=3)
    async def preview_system(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user
        guild = interaction.guild

        async with aiosqlite.connect(DB_NAME) as db:
            if self.system_type == "welcome":
                async with db.execute(f"SELECT message, chat_channel_id, vc_channel_id FROM {self.table} WHERE guild_id = ?", (guild.id,)) as cursor:
                    row = await cursor.fetchone()
                desc, chat_ch, vc_ch = row if row else ("Mensaje de prueba", None, None)
            else:
                async with db.execute(f"SELECT message FROM {self.table} WHERE guild_id = ?", (guild.id,)) as cursor:
                    row = await cursor.fetchone()
                desc = row[0] if row and row[0] else "Mensaje de prueba"

        embed = discord.Embed(description=desc, color=0x2b2d31)
        guild_icon = guild.icon.url if guild.icon else self.ctx.bot.user.display_avatar.url
        
        if self.system_type == "welcome":
            embed.set_author(name=f"We now have {guild.member_count} members!", icon_url=guild_icon)
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"Rep /{guild.name.lower()} for Pic Perms!")
            view = BleedButtonsView(guild, chat_ch, vc_ch)
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

    @discord.ui.button(label="Reset", style=discord.ButtonStyle.danger, row=3)
    async def reset_system(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(f"DELETE FROM {self.table} WHERE guild_id = ?", (interaction.guild.id,))
            await db.commit()
        await self.refresh_panel(interaction)

class ChannelSelectMenu(discord.ui.ChannelSelect):
    def __init__(self, table_name: str, parent_view: ConfigPanelView):
        # ✅ PERMITE CANALES DE TEXTO Y DE ANUNCIOS/NOTICIAS
        super().__init__(
            placeholder="Selecciona el canal...", 
            channel_types=[discord.ChannelType.text, discord.ChannelType.news], 
            row=0
        )
        self.table_name = table_name
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        selected_ch = self.values[0]
        default_msg = "• Please read our rules.\n• Boost for perks.\n• Invite your friends!"

        async with aiosqlite.connect(DB_NAME) as db:
            if self.table_name == "welcomes":
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS welcomes (
                        guild_id INTEGER PRIMARY KEY, 
                        channel_id INTEGER, 
                        status INTEGER DEFAULT 1, 
                        message TEXT,
                        chat_channel_id INTEGER,
                        vc_channel_id INTEGER
                    )
                """)
                await db.execute("""
                    INSERT INTO welcomes (guild_id, channel_id, status, message)
                    VALUES (?, ?, 1, ?)
                    ON CONFLICT(guild_id) DO UPDATE SET channel_id = ?, status = 1
                """, (interaction.guild.id, selected_ch.id, default_msg, selected_ch.id))
            else:
                await db.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.table_name} (
                        guild_id INTEGER PRIMARY KEY, 
                        channel_id INTEGER, 
                        status INTEGER DEFAULT 1, 
                        message TEXT
                    )
                """)
                await db.execute(f"""
                    INSERT INTO {self.table_name} (guild_id, channel_id, status, message)
                    VALUES (?, ?, 1, ?)
                    ON CONFLICT(guild_id) DO UPDATE SET channel_id = ?, status = 1
                """, (interaction.guild.id, selected_ch.id, default_msg, selected_ch.id))
            await db.commit()

        await self.parent_view.refresh_panel(interaction)

class SetupPanel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="welcome", aliases=["wlc"])
    @commands.has_permissions(administrator=True)
    async def welcome(self, ctx):
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS welcomes (
                    guild_id INTEGER PRIMARY KEY, 
                    channel_id INTEGER, 
                    status INTEGER DEFAULT 1, 
                    message TEXT,
                    chat_channel_id INTEGER,
                    vc_channel_id INTEGER
                )
            """)
            async with db.execute("SELECT channel_id, status, message, chat_channel_id, vc_channel_id FROM welcomes WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()

        ch_id, status, msg, chat_ch, vc_ch = row if row else (None, 0, "No configurado", None, None)
        channel_mention = f"<#{ch_id}>" if ch_id else "*Ninguno*"
        
        embed = discord.Embed(color=0x78b159 if status == 1 else 0x2b2d31)
        embed.set_author(name="Welcome configuration")
        embed.add_field(name="Channel", value=channel_mention, inline=True)
        embed.add_field(name="Status", value="✔ Enabled" if status == 1 else "❌ Disabled", inline=True)
        embed.add_field(name="Botón Chat", value=f"<#{chat_ch}>" if chat_ch else "*Predeterminado*", inline=True)
        embed.add_field(name="Botón VC", value=f"<#{vc_ch}>" if vc_ch else "*Predeterminado*", inline=True)
        embed.add_field(name="Message", value=f"```text\n{str(msg)[:500]}\n```", inline=False)

        view = ConfigPanelView(ctx, "welcome")
        await ctx.reply(embed=embed, view=view, mention_author=False)

    @commands.command(name="goodbye", aliases=["despedida"])
    @commands.has_permissions(administrator=True)
    async def goodbye(self, ctx):
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("CREATE TABLE IF NOT EXISTS goodbyes (guild_id INTEGER PRIMARY KEY, channel_id INTEGER, status INTEGER DEFAULT 1, message TEXT)")
            async with db.execute("SELECT channel_id, status, message FROM goodbyes WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()

        ch_id, status, msg = row if row else (None, 0, "No configurado")
        channel_mention = f"<#{ch_id}>" if ch_id else "*Ninguno*"
        
        embed = discord.Embed(color=0x78b159 if status == 1 else 0x2b2d31)
        embed.set_author(name="Goodbye configuration")
        embed.add_field(name="Channel", value=channel_mention, inline=True)
        embed.add_field(name="Status", value="✔ Enabled" if status == 1 else "❌ Disabled", inline=True)
        embed.add_field(name="Message", value=f"```text\n{str(msg)[:500]}\n```", inline=False)

        view = ConfigPanelView(ctx, "goodbye")
        await ctx.reply(embed=embed, view=view, mention_author=False)

    @commands.command(name="boostmsg", aliases=["boost"])
    @commands.has_permissions(administrator=True)
    async def boostmsg(self, ctx):
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("CREATE TABLE IF NOT EXISTS boosts (guild_id INTEGER PRIMARY KEY, channel_id INTEGER, status INTEGER DEFAULT 1, message TEXT)")
            async with db.execute("SELECT channel_id, status, message FROM boosts WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()

        ch_id, status, msg = row if row else (None, 0, "No configurado")
        channel_mention = f"<#{ch_id}>" if ch_id else "*Ninguno*"
        
        embed = discord.Embed(color=0x78b159 if status == 1 else 0x2b2d31)
        embed.set_author(name="Boostmsg configuration")
        embed.add_field(name="Channel", value=channel_mention, inline=True)
        embed.add_field(name="Status", value="✔ Enabled" if status == 1 else "❌ Disabled", inline=True)
        embed.add_field(name="Message", value=f"```text\n{str(msg)[:500]}\n```", inline=False)

        view = ConfigPanelView(ctx, "boostmsg")
        await ctx.reply(embed=embed, view=view, mention_author=False)

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

            raw_msg = row[2] or "¡Gracias por mejorar el servidor, {user}!"
            formatted_msg = raw_msg.replace("{user}", after.mention)\
                                  .replace("{server}", guild.name)\
                                  .replace("{count}", str(guild.premium_subscription_count))

            embed = discord.Embed(description=formatted_msg, color=0xb845ff)
            guild_icon = guild.icon.url if guild.icon else self.bot.user.display_avatar.url
            embed.set_author(name=f"@{after.name} mejoró el servidor 💜", icon_url=after.display_avatar.url)
            embed.set_footer(text=f"{guild.premium_subscription_count} boosts • Lvl {guild.premium_tier}", icon_url=guild_icon)
            
            await channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(SetupPanel(bot))
