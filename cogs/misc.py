"""Misc"""

import logging
import os
import pathlib
import platform
import sqlite3
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

dbs_folder_path = os.getenv("DBS_FOLDER_PATH")


class Misc(commands.Cog):
    """Miscellaneous commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="info", description="Informations sur l'instance d'Abeille 🐝"
    )
    @app_commands.guild_only()
    async def info(self, interaction: discord.Interaction):
        """Shown instance information"""
        size_bytes = os.path.getsize(
            pathlib.Path(dbs_folder_path) / f"{interaction.guild_id}.db"
        )
        size_go = f"{size_bytes/(1024*1024*1024):.1f}"
        app_info = await self.bot.application_info()
        bot_user = self.bot.user
        bot_name = f"{bot_user.name}#{bot_user.discriminator}" if bot_user else "Unknown"

        embed = discord.Embed(
            title=f"{size_go} GB d'espace est utilisé pour *{interaction.guild.name}*",
            description=f"Il s'agit de l'espace utilisé par Abeille pour fonctionner correctement sur ce serveur.",
        )
        embed.add_field(
            name=f"Informations du système exécutant {bot_name}",
            value=f"""
                Système : {platform.platform(aliased=True)}
                SQLite {sqlite3.sqlite_version}
                discord.py {discord.__version__}
                """,
            inline=False,
        )
        embed.set_author(
            name=bot_name,
            icon_url=bot_user.avatar.url if bot_user and bot_user.avatar else None,
        )
        embed.set_footer(
            text=f"{bot_name} est maintenu par {app_info.owner.name}",
            icon_url=app_info.owner.avatar.url if app_info.owner.avatar else None,
        )
        await interaction.response.send_message(embed=embed)

    @commands.command()
    @commands.is_owner()
    async def sync(self, ctx: commands.Context):
        """Sync commands globally"""
        await self._sync_commands()

    @commands.command()
    @commands.is_owner()
    async def clear(self, ctx: commands.Context, guild_str: Optional[str] = None):
        """Clear commands for a guild"""
        guild = None
        if guild_str:
            guild = discord.Object(id=int(guild_str))
        await self._clear_commands(guild=guild)

    @commands.command()
    @commands.is_owner()
    async def fetch(self, ctx: commands.Context):
        """Fetch commands globally"""
        list_commands = await self.bot.tree.fetch_commands()
        print("fetching...")
        for command in list_commands:
            print(f"{command.name} ({command.id})")

    @commands.command()
    @commands.is_owner()
    async def logging(self, ctx: commands.Context, level: str):
        """Define logging level"""
        level = level.upper()
        logging.getLogger().setLevel(level)
        await ctx.send(f"`Logging set to {level}`")

    async def _sync_commands(self, *, guild: Optional[discord.abc.Snowflake] = None):
        """Synchronize commands (to guild or globally)"""
        logging.info("Syncing commands...")
        if guild:
            self.bot.tree.copy_global_to(guild=guild)
            await self.bot.tree.sync(guild=guild)
        else:
            await self.bot.tree.sync()
        logging.info("Commands synced.")

    async def _clear_commands(self, *, guild: Optional[discord.abc.Snowflake] = None):
        """Clear and synchronize commands (to guild or globally)"""
        logging.info("Clearing and syncing commands...")
        self.bot.tree.clear_commands(guild=guild)
        synced_commands = await self.bot.tree.sync(guild=guild)
        logging.info("Commands synced.")
        for sync_command in synced_commands:
            print(f"{sync_command.name} ({sync_command.id})")


async def setup(bot):
    await bot.add_cog(Misc(bot))
