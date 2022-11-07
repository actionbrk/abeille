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
        owner = self.bot.get_user(self.bot.owner_id)
        bot_name = f"{self.bot.user.name}#{self.bot.user.discriminator}"

        embed = discord.Embed(
            title=f"{size_go} GB d'espace est utilisé pour *{interaction.guild.name}*",
            description=f"Il s'agit des données enregistrées par Abeille lui permettant de fonctionner sur ce serveur.",
        )
        embed.add_field(
            name=f"Informations du système exécutant {bot_name}",
            value=f"""
                Système d'exploitation : {platform.platform()}
                SQLite {sqlite3.sqlite_version}
                discord.py {discord.__version__}
                """,
            inline=False,
        )
        embed.set_author(
            name=bot_name,
            icon_url=self.bot.user.avatar.url,
        )
        embed.set_footer(
            text=f"{bot_name} est maintenu par {owner.name}#{owner.discriminator}",
            icon_url=owner.avatar.url,
        )
        await interaction.response.send_message(
            content="<@168378684497985536> <@339928611937189888>", embed=embed
        )

    @commands.command()
    @commands.is_owner()
    async def sync(self, ctx: commands.Context):
        """Sync commands globally"""
        await self._sync_commands()

    @commands.command()
    @commands.is_owner()
    async def clear(self, ctx: commands.Context, guild_str: Optional[str] = None):
        """Sync commands globally"""
        guild = None
        if guild_str:
            guild = discord.Object(id=int(guild_str))
        await self._clear_commands(guild=guild)

    @commands.command()
    @commands.is_owner()
    async def fetch(self, ctx: commands.Context):
        """Sync commands globally"""
        list_commands = await self.bot.tree.fetch_commands()
        print("fetching...")
        for command in list_commands:
            print(f"{command.name} ({command.id})")

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
