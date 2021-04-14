import datetime
import time
from typing import List, Union

import discord
from discord.abc import Snowflake
from discord.ext import commands
from peewee import Database, DoesNotExist

from cogs.tracking import get_message, get_tracking_cog
from models.message import Message


class SaveResult:
    def __init__(self):
        self.trouves = 0
        self.sauves = 0
        self.deja_sauves = 0
        self.from_bot = 0

    def __str__(self) -> str:
        return f"{self.sauves} enregistrés sur {self.trouves} trouvés ({self.from_bot} provenant de bots, {self.deja_sauves} déjà enregistrés)"


class History(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    @commands.is_owner()
    async def saveold(self, ctx: commands.Context, channel_id: int, count: int):
        tracking_cog = get_tracking_cog(self.bot)
        channel = self.bot.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            await ctx.reply(f"Impossible de trouver ce salon ({channel_id})")
            return

        db = tracking_cog.tracked_guilds[channel.guild.id]

        # Si channel ignoré, passer
        if channel.id in tracking_cog.ignored_channels:
            await ctx.send(f"Channel {channel.name} ignoré")
            return

        time_debut = time.time()
        msg_bot = await ctx.send("Enregistrement...")

        # Récupérer le plus ancien message du channel
        with db:
            with db.bind_ctx([Message]):
                oldest = (
                    Message.select()
                    .where(Message.channel_id == channel_id)
                    .order_by(Message.message_id)
                    .get()
                )

        # discord.Message correspondant
        oldest_msg: discord.Message = await channel.fetch_message(oldest)

        # Enregistrement
        save_result = await self._save_from_channel(channel, count, before=oldest_msg)

        print("Fin", time.time() - time_debut)
        await msg_bot.edit(content=f"{count} demandés\n{save_result}")

    @commands.command()
    @commands.is_owner()
    async def save(self, ctx: commands.Context, channel_id: int, count: int = 20):
        """ Sauvegarde les messages dans le passé à partir d'ici """
        channel = self.bot.get_channel(channel_id)
        tracking_cog = get_tracking_cog(self.bot)
        if not isinstance(channel, discord.TextChannel):
            await ctx.reply(f"Impossible de trouver ce salon ({channel_id})")
            return

        # Si channel ignoré, passer
        if channel.id in tracking_cog.ignored_channels:
            await ctx.send(f"Channel {channel.name} ignoré")
            return

        time_debut = time.time()
        print("Début")

        save_result = await self._save_from_channel(channel, count)  # type: ignore

        print("Fin", time.time() - time_debut)
        await ctx.send(f"{count} demandés\n{save_result}")

    @commands.command()
    @commands.is_owner()
    async def saveall(self, ctx: commands.Context, guild_id: int, count: int = 20):
        """ Sauvegarde les messages de tous les channels possibles à partir d'ici """
        save_results = {}
        impossible_channels = []
        tracking_cog = get_tracking_cog(self.bot)

        guild = self.bot.get_guild(guild_id)
        if guild is None:
            await ctx.reply("Je ne trouve pas cette guild")
            return

        # Détection des channels
        for channel in guild.channels:
            if not isinstance(channel, discord.TextChannel):
                continue

            # Si channel ignoré, passer
            if channel.id in tracking_cog.ignored_channels:
                await ctx.send(f"Channel {channel.name} ignoré")
                continue

            try:
                save_results[channel.name] = await self._save_from_channel(
                    channel, count
                )
            except:
                impossible_channels.append(channel)

        for name, save_result in save_results.items():
            await ctx.send(f"**{name}**\n{save_result}")

        impossible_channels_str = []
        for impossible_channel in impossible_channels:
            impossible_channels_str.append(impossible_channel.name)
        await ctx.send("Je n'ai pas pu enregistrer les autres channels")
        # await ctx.send("\n".join(impossible_channels_str))

    @commands.command()
    @commands.is_owner()
    async def saveoldall(self, ctx: commands.Context, guild_id: int, count: int = 20):
        """ Save old sur les channels connus en db """
        tracking_cog = get_tracking_cog(self.bot)
        db = tracking_cog.tracked_guilds[guild_id]
        guild = self.bot.get_guild(guild_id)

        if guild is None:
            await ctx.send("Je ne trouve pas cette guild")
            return

        # Récupérer liste channels connus
        known_channels = await self._get_known_channels(db)
        if not known_channels:
            await ctx.send("Aucun channel connu, d'abord utiliser saveall ou save")
            return
        await ctx.send(
            f"J'ai trouvé **{len(known_channels)}** channels connus en db..."
        )

        # Parcours channels
        for channel in known_channels:
            msg_bot = await ctx.send(f"J'enregistre le channel **{channel.name}**...")
            # Récupérer le plus ancien message du channel
            with db:
                with db.bind_ctx([Message]):
                    try:
                        oldest = (
                            Message.select()
                            .where(Message.channel_id == channel.id)
                            .order_by(Message.message_id)
                            .get()
                        )
                    except DoesNotExist:
                        print(f"Pas de message en db pour le channel {channel}")
                        continue

            # discord.Message correspondant
            try:
                oldest_msg: discord.Message = await channel.fetch_message(oldest)
            except discord.NotFound:
                print(
                    f"Le plus ancien message enregistré du channel {channel} n'existe plus"
                )
            except discord.Forbidden:
                print(f"Problème de droit pour le channel {channel}")

            # Enregistrement
            try:
                save_result = await self._save_from_channel(
                    channel, count, before=oldest_msg
                )
                await msg_bot.edit(
                    content=f"**{channel.name}**\n{save_result} ({oldest_msg.created_at})"
                )
            except discord.Forbidden as exc:
                await msg_bot.edit(content=f"**{channel.name}**\nErreur: {exc}")

        await ctx.send("Fini !")

    async def _save_from_channel(
        self,
        channel: discord.TextChannel,
        count: int = 100,
        before: Union[Snowflake, datetime.datetime] = None,
        after: Union[Snowflake, datetime.datetime] = None,
        around: Union[Snowflake, datetime.datetime] = None,
        oldest_first: bool = None,
    ) -> SaveResult:
        """ Enregistre les messages d'un channel dans la BDD associée """
        tracking_cog = get_tracking_cog(self.bot)
        guild = channel.guild
        db: Database = tracking_cog.tracked_guilds[guild.id]

        save_result = SaveResult()

        async for message in channel.history(
            limit=count,
            before=before,
            after=after,
            around=around,
            oldest_first=oldest_first,
        ):
            save_result.trouves += 1

            # Ignorer messages bot
            if message.author.bot:
                save_result.from_bot += 1
                continue

            with db:
                with db.bind_ctx([Message]):
                    # Vérifier si le message existe avant d'enregistrer
                    # TODO: Plutôt faire select().count() ?
                    try:
                        Message.get_by_id(message.id)
                        save_result.deja_sauves += 1
                        continue
                    except DoesNotExist:
                        pass

                    # Créer le message inexistant
                    msg = get_message(message)
                    msg.save(force_insert=True)
                    save_result.sauves += 1

        return save_result

    async def _get_known_channels(self, db: Database) -> List[discord.TextChannel]:
        """ Récupérer la liste des channels connus en db """
        known_channels = []
        with db:
            with db.bind_ctx([Message]):
                for known_channel_id in Message.select(Message.channel_id).distinct():
                    known_channel = self.bot.get_channel(known_channel_id.channel_id)
                    if not isinstance(known_channel, discord.TextChannel):
                        print(
                            f"Impossible de déterminer le channel correspondant à l'id {known_channel_id}"
                        )
                        continue
                    known_channels.append(known_channel)

        return known_channels


def setup(bot):
    bot.add_cog(History(bot))
