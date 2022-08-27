import asyncio
import logging
from typing import Optional

import discord
from common.utils import DEV_GUILD
from discord import app_commands
from discord.ext import commands
from models.message import Message
from peewee import SQL

from cogs.tracking import get_tracking_cog


class Misc(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="bzz", description="Bzz bzz (ping) ! 🐝")
    async def ping(self, interaction: discord.Interaction):
        """Ping"""
        await interaction.response.send_message("Je fonctionne ! 🐝")

    # TODO: Channel parameter (not nsfw?)
    @app_commands.command(
        name="random",
        description="Un message ou un média aléatoire provenant de ce salon.",
    )
    @app_commands.describe(
        channel="Salon sur lequel choisir un message au hasard.",
        media="Uniquement des images.",
    )
    @app_commands.guild_only()
    async def random(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel],
        media: Optional[bool],
        # TODO: min_length
        # TODO: user?
        # TODO: contains (random qui contient un terme)
        # TODO:
    ):
        """Random message"""
        await interaction.response.defer(thinking=True)

        if not interaction.guild_id:
            await interaction.followup.send("Can't find guild id.")
            return

        # Specified channel or interaction channel by default
        channel_id = interaction.channel_id

        fallback_channel = None

        if channel:
            # TODO: Prevent user if specified channel is nsfw while interaction is done in sfw channel
            if channel.is_nsfw() and not interaction.channel.is_nsfw():
                fallback_channel = interaction.channel
            else:
                channel_id = channel.id

        # Message type
        filter_expression = Message.channel_id == channel_id
        if media:
            filter_expression &= Message.attachment_url.is_null(False)

        tracking_cog = get_tracking_cog(self.bot)
        db = tracking_cog.tracked_guilds[interaction.guild_id]

        with db:
            with db.bind_ctx([Message]):
                params_list = [channel_id]
                query_str = [
                    """
                    message_id > ((SELECT min(message_id) FROM message) + (
                    ABS(RANDOM()) % ((SELECT max(message_id) FROM message)-(SELECT min(message_id) FROM message))
                    ))
                    AND channel_id=?"""
                ]

                if media:
                    query_str.append("AND attachment_url is not null")

                sql: SQL = SQL(
                    " ".join(query_str),
                    params_list,
                )
                message: Message = Message.select().where(sql).get_or_none()

        if message is None:
            await interaction.followup.send(
                f"Je n'ai pas trouvé de message sur le salon <#{interaction.channel_id}>."
            )
        else:
            await interaction.followup.send(message.attachment_url or message.content)
            if fallback_channel:
                await interaction.followup.send(
                    f"Le salon spécifié étant NSFW, le /random a été réalisé sur le salon <#{fallback_channel.id}>.",
                    ephemeral=True,
                )

        # Delete message in 2 minutes
        await asyncio.sleep(120)
        await interaction.delete_original_response()

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
