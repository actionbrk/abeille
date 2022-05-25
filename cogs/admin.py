""" Commandes d'administration """

import logging
import os

import discord
from discord.ext import commands

from cogs.tracking import get_tracking_cog
from models.message import Message, MessageIndex

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
        tracking_cog = get_tracking_cog(self.bot)
        for guild_id, db in tracking_cog.tracked_guilds.items():
            with db:
                with db.bind_ctx([MessageIndex]):
                    logging.info("Optimizing %s...", str(guild_id))
                    MessageIndex.optimize()
                    logging.info("Optimized.")

    @commands.command()
    @commands.is_owner()
    async def rebuild(self, ctx: commands.Context):
        """Rebuild MessageIndex of every databases"""
        tracking_cog = get_tracking_cog(self.bot)
        for guild_id, db in tracking_cog.tracked_guilds.items():
            with db:
                with db.bind_ctx([MessageIndex]):
                    logging.info("Rebuilding %s...", str(guild_id))
                    MessageIndex.rebuild()
                    logging.info("Rebuilt.")

    @commands.command(name="recap", aliases=["récap"])
    @commands.guild_only()
    @commands.check(is_admin)
    async def check(self, ctx: commands.Context):
        """Vérifie quels channels sont enregistrés"""
        assert ctx.guild is not None, "Impossible de récupérer la guild"
        await self._check(ctx, ctx.guild.id)

    @commands.command(name="recapid", aliases=["récapid"])
    @commands.guild_only()
    @commands.is_owner()
    async def check_id(self, ctx: commands.Context, guild_id: int):
        """Vérifie quels channels sont enregistrés (id)"""
        await self._check(ctx, guild_id)

    async def _check(self, ctx: commands.Context, guild_id: int):
        """Vérifie quels channels sont enregistrés"""
        tracking_cog = get_tracking_cog(self.bot)
        db = tracking_cog.tracked_guilds[guild_id]
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            await ctx.reply(f"Guild inconnue ({guild_id})")
            return

        ok_channels = []
        nok_channels = []
        ignored = []

        start_msg = await ctx.author.send("Je fais un récap... 🐝")

        for channel in guild.channels:
            if not isinstance(channel, discord.TextChannel):
                continue

            # Si channel ignoré
            if channel.id in tracking_cog.ignored_channels:
                ignored.append(f"🚫 {channel.name}")
                continue

            try:
                [message async for message in channel.history(limit=10)]
            except discord.Forbidden as _exc:
                nok_channels.append(f"⭕ {channel.name}")
                continue

            # Compter nombre de messages enregistrés
            with db:
                with db.bind_ctx([Message]):
                    count = (
                        Message.select().where(Message.channel_id == channel.id).count()
                    )

            ok_channels.append(f"✅ {channel.name} ({count} messages enregistrés)")

        await start_msg.delete()
        await ctx.author.send(
            f"🐝 J'enregistre actuellement **{len(ok_channels)}** salon(s) écrit(s).\n"
            + "\n".join(ok_channels)
        )
        await ctx.author.send(
            f"🐝 Je n'ai pas la permission d'enregistrer **{len(nok_channels)}** salon(s) écrit(s).\n"
            + "\n".join(nok_channels)
        )
        await ctx.author.send(
            f"🐝 J'ignore **{len(ignored)}** salon(s) écrit(s).\n" + "\n".join(ignored)
        )

    async def cog_command_error(self, ctx: commands.Context, error):
        if isinstance(error, (commands.BadArgument, commands.MissingRequiredArgument)):
            await ctx.author.send("Vous avez mal utilisé la commande ! 🐝")
            return
        await ctx.author.send(f"Quelque chose s'est mal passée. 🐝 ({error})")

    @check.error
    @check_id.error
    async def _admin_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.author.send("Seuls les admins peuvent exécuter cette commande. 🐝")


async def setup(bot):
    await bot.add_cog(Admin(bot))
