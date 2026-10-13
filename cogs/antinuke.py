import discord
from discord.ext import commands
import aiosqlite
import math
from config import DB_NAME

class ConfirmView(discord.ui.View):
    def __init__(self, author: discord.Member):
        super().__init__(timeout=60)
        self.author = author
        self.value = None

    @discord.ui.button(label="Nuke", style=discord.ButtonStyle.danger, custom_id="nuke_confirm")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ No puedes usar este botón.", ephemeral=True)
            return
        self.value = True
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, custom_id="nuke_cancel")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ No puedes usar este botón.", ephemeral=True)
            return
        self.value = False
        self.stop()

class WhitelistPaginator(discord.ui.View):
    def __init__(self, author: discord.Member, items: list, per_page: int = 10):
        super().__init__(timeout=60)
        self.author = author
        self.items = items
        self.per_page = per_page
        self.current_page = 0
        self.max_page = math.ceil(len(items) / per_page) or 1
        self.update_buttons()

    def update_buttons(self):
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page >= self.max_page - 1
        self.page_indicator.label = f"Página {self.current_page + 1}/{self.max_page}"

    def get_page_embed(self) -> discord.Embed:
        start = self.current_page * self.per_page
        end = start + self.per_page
        current_items = self.items[start:end]

        formatted_list = "\n".join(
            [f"`{start + i + 1}.` <@{user_id}> (`{user_id}`)" for i, user_id in enumerate(current_items)]
        ) if current_items else "Sin usuarios en whitelist"

        embed = discord.Embed(
            title="📜 **Antinuke Whitelist**",
            description=formatted_list,
            color=0x2b2d31
        )
        embed.set_footer(text=f"Total: {len(self.items)} usuarios/bots en whitelist")
        return embed

    @discord.ui.button(emoji="◀", style=discord.ButtonStyle.secondary, custom_id="prev_page")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            return await interaction.response.send_message("❌ No puedes usar este botón.", ephemeral=True)
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_page_embed(), view=self)

    @discord.ui.button(label="Página 1/1", style=discord.ButtonStyle.secondary, disabled=True, custom_id="page_num")
    async def page_indicator(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(emoji="▶", style=discord.ButtonStyle.secondary, custom_id="next_page")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            return await interaction.response.send_message("❌ No puedes usar este botón.", ephemeral=True)
        if self.current_page < self.max_page - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_page_embed(), view=self)

class Antinuke(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def init_db(self):
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS antinuke_admins (
                    guild_id INTEGER,
                    user_id INTEGER,
                    PRIMARY KEY (guild_id, user_id)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS antinuke_whitelist (
                    guild_id INTEGER,
                    user_id INTEGER,
                    PRIMARY KEY (guild_id, user_id)
                )
            """)
            await db.commit()

    async def cog_load(self):
        await self.init_db()

    async def is_an_admin(self, ctx) -> bool:
        if not ctx.guild:
            return False
        if ctx.author.id == ctx.guild.owner_id:
            return True
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute(
                "SELECT 1 FROM antinuke_admins WHERE guild_id = ? AND user_id = ?",
                (ctx.guild.id, ctx.author.id)
            ) as cursor:
                row = await cursor.fetchone()
                return row is not None

    async def send_an_admin_required_alert(self, ctx):
        embed = discord.Embed(
            description=f"⚠️ {ctx.author.mention}: You must be an **antinuke admin** to run this command.",
            color=0xFEE75C
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.group(name="antinuke", aliases=["an"], invoke_without_command=True)
    async def antinuke(self, ctx):
        if not await self.is_an_admin(ctx):
            return await self.send_an_admin_required_alert(ctx)

        embed = discord.Embed(
            title="🛡️ **Antinuke System**",
            description=(
                "El sistema de **Antinuke** está activo y protegiendo este servidor.\n\n"
                "> **Estado del Servidor:** `Protegido`\n"
                "> **Acciones Monitoreadas:** `Kicks`, `Bans`, `Canales`, `Roles`, `Webhooks`, `Bots`\n\n"
                "⚠️ *Usa `,an admin` para gestionar administradores o `,an whitelist` para eximir usuarios de sanciones.*"
            ),
            color=0x2b2d31
        )
        embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon.url if ctx.guild.icon else self.bot.user.display_avatar.url)
        embed.set_footer(text=f"Propietario: {ctx.guild.owner}", icon_url=ctx.guild.owner.display_avatar.url)
        await ctx.reply(embed=embed, mention_author=False)

    @antinuke.command(name="admin")
    async def antinuke_admin(self, ctx, user: discord.User = None):
        if ctx.author.id != ctx.guild.owner_id:
            embed = discord.Embed(
                description=f"⚠️ {ctx.author.mention}: **Solo el Propietario del Servidor** puede añadir o remover Antinuke Admins.",
                color=0x2b2d31
            )
            return await ctx.reply(embed=embed, mention_author=False)

        if not user:
            async with aiosqlite.connect(DB_NAME) as db:
                async with db.execute("SELECT user_id FROM antinuke_admins WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                    rows = await cursor.fetchall()
            admins_list = [f"<@{r[0]}> (`{r[0]}`)" for r in rows] if rows else ["Ninguno asignado"]
            embed = discord.Embed(
                title="🛡️ **Antinuke Admins**",
                description="\n".join(admins_list),
                color=0x2b2d31
            )
            return await ctx.reply(embed=embed, mention_author=False)

        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT 1 FROM antinuke_admins WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, user.id)) as cursor:
                exists = await cursor.fetchone()

            if exists:
                await db.execute("DELETE FROM antinuke_admins WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, user.id))
                await db.commit()
                embed = discord.Embed(
                    description=f"✅ Se ha **removido** a {user.mention} de los Antinuke Admins.",
                    color=0x2b2d31
                )
            else:
                await db.execute("INSERT INTO antinuke_admins (guild_id, user_id) VALUES (?, ?)", (ctx.guild.id, user.id))
                await db.commit()
                embed = discord.Embed(
                    description=f"✅ Se ha **otorgado** rango de **Antinuke Admin** a {user.mention}.",
                    color=0x2b2d31
                )

        await ctx.reply(embed=embed, mention_author=False)

    @antinuke.group(name="whitelist", aliases=["wl"], invoke_without_command=True)
    async def antinuke_whitelist(self, ctx, user: discord.User = None):
        """Añade/Remueve un usuario o despliega la lista paginada si no se pasa argumento."""
        if not await self.is_an_admin(ctx):
            return await self.send_an_admin_required_alert(ctx)

        if not user:
            return await self.whitelist_list(ctx)

        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT 1 FROM antinuke_whitelist WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, user.id)) as cursor:
                exists = await cursor.fetchone()

            if exists:
                await db.execute("DELETE FROM antinuke_whitelist WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, user.id))
                await db.commit()
                embed = discord.Embed(
                    description=f"✅ Se ha **removido** a {user.mention} de la **Antinuke Whitelist**.",
                    color=0x2b2d31
                )
            else:
                await db.execute("INSERT INTO antinuke_whitelist (guild_id, user_id) VALUES (?, ?)", (ctx.guild.id, user.id))
                await db.commit()
                embed = discord.Embed(
                    description=f"✅ {user.mention} ha sido añadido a la **Antinuke Whitelist**.",
                    color=0x2b2d31
                )

        await ctx.reply(embed=embed, mention_author=False)

    @antinuke_whitelist.command(name="list")
    async def whitelist_list(self, ctx):
        """Lista la whitelist con paginación limpia."""
        if not await self.is_an_admin(ctx):
            return await self.send_an_admin_required_alert(ctx)

        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT user_id FROM antinuke_whitelist WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                rows = await cursor.fetchall()

        user_ids = [r[0] for r in rows]

        paginator = WhitelistPaginator(author=ctx.author, items=user_ids, per_page=10)
        embed = paginator.get_page_embed()
        
        # Si hay más de una página se muestran los botones de navegación
        if paginator.max_page > 1:
            await ctx.reply(embed=embed, view=paginator, mention_author=False)
        else:
            await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="nuke")
    @commands.has_permissions(manage_channels=True)
    async def nuke(self, ctx):
        view = ConfirmView(ctx.author)
        
        embed = discord.Embed(
            description="⚠️ ¿Estás seguro de que deseas **reiniciar (nuke)** este canal?",
            color=0x2b2d31
        )
        message = await ctx.reply(embed=embed, view=view, mention_author=False)

        await view.wait()

        if view.value is None:
            timeout_embed = discord.Embed(
                description="⏳ El tiempo para confirmar el nuke ha expirado.",
                color=0x2b2d31
            )
            await message.edit(embed=timeout_embed, view=None)
            return

        if view.value:
            channel = ctx.channel
            position = channel.position

            new_channel = await channel.clone(reason=f"Nuke ejecutado por {ctx.author}")
            await new_channel.edit(position=position)
            await channel.delete()

            if isinstance(new_channel, discord.TextChannel):
                done_embed = discord.Embed(
                    description=f"💣 Canal reiniciado correctamente por {ctx.author.mention}.",
                    color=0x2b2d31
                )
                await new_channel.send(embed=done_embed)
        else:
            cancel_embed = discord.Embed(
                description="❌ Acción de nuke cancelada.",
                color=0x2b2d31
            )
            await message.edit(embed=cancel_embed, view=None)

async def setup(bot):
    await bot.add_cog(Antinuke(bot))
