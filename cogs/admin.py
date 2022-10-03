""" Commandes d'administration """

import logging
import os

import discord
from discord.ext import commands

from cogs.tracking import get_tracked_guilds
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
            with db:
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

    async def cog_command_error(self, ctx: commands.Context, error):
        if isinstance(error, (commands.BadArgument, commands.MissingRequiredArgument)):
            await ctx.author.send("Vous avez mal utilisé la commande ! 🐝")
            return
        await ctx.author.send(f"Quelque chose s'est mal passée. 🐝 ({error})")


async def setup(bot):
    await bot.add_cog(Admin(bot))
