import logging
from datetime import date

import discord
from discord.ext import commands, tasks
from peewee import RawQuery
from cogs.tracking import get_tracked_guilds
from models import message


class MessageDay(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.task_messageday.start()

    def cog_unload(self):
        self.task_messageday.cancel()

    @commands.command()
    @commands.is_owner()
    async def messageday(self, ctx: commands.Context):
        """Force MessaegDay update"""
        await self._update_messageday()

    @tasks.loop(hours=24)
    async def task_messageday(self):
        await self._update_messageday()

    async def _update_messageday(self):
        until_day = date.today()

        for guild_id, tracked_guild in get_tracked_guilds(self.bot).items():
            db = tracked_guild.database
            with db.bind_ctx([message.MessageDay]):
                logging.info("Updating MessageDay for guild %s...", str(guild_id))

                # Clean table
                delete_query = message.MessageDay.delete()
                delete_query.execute(db)

                # Update table
                query = RawQuery(
                    """
                INSERT INTO messageday
                SELECT DATE(message.timestamp), COUNT(message.message_id)
                FROM message
                WHERE DATE(message.timestamp) < ?
                GROUP BY DATE(message.timestamp)
                ORDER BY DATE(message.timestamp);""",
                    params=([until_day]),
                )
                query.execute(db)

                logging.info("Updated.")


async def setup(bot):
    await bot.add_cog(MessageDay(bot))
