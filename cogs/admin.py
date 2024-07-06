""" Commandes d'administration """

import logging
import os

import discord
import pandas
from discord.ext import commands
from peewee import RawQuery

from cogs.tracking import get_tracked_guild, get_tracked_guilds
from models.message import MessageIndex

# Chargement paramètres DB
salt = os.getenv("SALT").encode()  # type:ignore
iterations = int(os.getenv("ITER"))  # type:ignore
hash_name: str = os.getenv("HASHNAME")  # type:ignore


async def is_admin(ctx: commands.Context):
    """Vrai si administrateur de la guild"""
    if not isinstance(ctx.author, discord.Member):
        return False
    return ctx.author.guild_permissions.administrator


class Admin(commands.Cog):
    """Admin commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    @commands.is_owner()
    async def optimize(self, ctx: commands.Context):
        """Optimize MessageIndex of every databases"""
        for guild_id, tracked_guild in get_tracked_guilds(self.bot).items():
            db = tracked_guild.database
            with db.bind_ctx([MessageIndex]):
                logging.info("Optimizing %s...", str(guild_id))
                MessageIndex.optimize()
                logging.info("Optimized.")

    @commands.command()
    @commands.is_owner()
    async def rebuild(self, ctx: commands.Context):
        """Rebuild MessageIndex of every databases"""
        for guild_id, tracked_guild in get_tracked_guilds(self.bot).items():
            db = tracked_guild.database
            with db.bind_ctx([MessageIndex]):
                logging.info("Rebuilding %s...", str(guild_id))
                MessageIndex.rebuild()
                logging.info("Rebuilt.")

    @commands.command()
    @commands.is_owner()
    async def sql(self, ctx: commands.Context, guild_id: int, *, query: str):
        """Execute raw sql query"""
        db = get_tracked_guild(self.bot, guild_id).database
        with db:
            query_sql, _query_params = RawQuery(query).sql()
            logging.info("Executing database request...")
            df = pandas.read_sql_query(query_sql, db.connection())
            logging.info("Database request answered.")

        await ctx.send(str(df))


async def setup(bot):
    await bot.add_cog(Admin(bot))
