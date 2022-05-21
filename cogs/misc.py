import logging
from typing import Optional
import discord
from discord import app_commands
from discord.ext import commands
from common.utils import DEV_GUILD


class Misc(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="bzz", description="Bzz bzz (ping) ! 🐝")
    async def ping(self, interaction: discord.Interaction):
        """Ping"""
        await interaction.response.send_message("Je fonctionne ! 🐝")

    @commands.command()
    @commands.is_owner()
    async def sync(self, ctx: commands.Context):
        """Sync commands globally"""
        await self._sync_commands()

    @commands.command()
    @commands.is_owner()
    async def syncdev(self, ctx: commands.Context):
        """Sync commands globally"""
        await self._sync_commands(guild=DEV_GUILD)

    @commands.command()
    @commands.is_owner()
    async def clear(self, ctx: commands.Context, guild: Optional[str] = None):
        """Sync commands globally"""
        await self._clear_commands(guild=guild)

    @commands.command()
    @commands.is_owner()
    async def cleardev(self, ctx: commands.Context):
        """Sync commands globally"""
        await self._clear_commands(guild=DEV_GUILD)

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
