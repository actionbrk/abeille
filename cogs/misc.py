import asyncio
import logging
from typing import Optional

import discord
from common.utils import DEV_GUILD
from discord import app_commands
from discord.ext import commands
from models.message import Message
from peewee import fn

from cogs.tracking import get_tracking_cog


class Misc(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="bzz", description="Bzz bzz (ping) ! 🐝")
    async def ping(self, interaction: discord.Interaction):
        """Ping"""
        await interaction.response.send_message("Je fonctionne ! 🐝")

    @app_commands.command(
        name="random",
        description="Un message ou un média aléatoire provenant de ce salon.",
    )
    async def random(self, interaction: discord.Interaction):
        """Random message"""
        tracking_cog = get_tracking_cog(self.bot)
        db = tracking_cog.tracked_guilds[interaction.guild_id]

        with db:
            with db.bind_ctx([Message]):
                message: Message = (
                    Message.select()
                    .where(
                        (Message.channel_id == interaction.channel_id)
                        & (
                            Message.attachment_url.is_null(False)
                            | Message.content.is_null(False)
                        )
                    )
                    .order_by(fn.Random())
                    .get()
                )

        await interaction.response.send_message(
            message.attachment_url or message.content
        )

        # Delete message in 2 minutes
        await asyncio.sleep(120)
        await interaction.delete_original_message()

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
    async def clear(self, ctx: commands.Context, guild_str: Optional[str] = None):
        """Sync commands globally"""
        guild = None
        if guild_str:
            guild = discord.Object(id=int(guild_str))
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
