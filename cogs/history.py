import logging
from datetime import datetime
from typing import List, Optional, Tuple

import discord
from discord.abc import Snowflake
from discord.ext import commands
from peewee import Database, DoesNotExist, fn, DateTimeField

from cogs.tracking import get_message, get_tracked_guild, get_tracked_guilds
from models.message import Message
from models.saveresult import SaveResult


class History(commands.Cog):
    """Save commands module"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    @commands.is_owner()
    async def save(self, ctx: commands.Context):
        """Complete save of all guilds"""
        logging.info("'save' command running...")

        tracked_guilds = get_tracked_guilds(self.bot).values()

        for tracked_guild_idx, tracked_guild in enumerate(tracked_guilds, 1):
            logging.info(
                "Saving guild [%d]... (%d/%d)",
                tracked_guild.guild_id,
                tracked_guild_idx,
                len(tracked_guilds),
            )

            db = tracked_guild.database

            guild = self.bot.get_guild(tracked_guild.guild_id)
            if guild is None:
                logging.warning("Guild [%d] is not accessible.")
                continue

            # Get available channels
            for channel in guild.text_channels:

                # Do not save a blacklisted channel
                if channel.id in tracked_guild.ignored_channels_ids:
                    logging.info(
                        "Channel [%d] is blacklisted and will not be saved.", channel.id
                    )
                    continue

                # Check if already saved messages in DB
                with db.bind_ctx([Message]):
                    is_unknown_channel = (
                        Message.get_or_none(Message.channel_id == channel.id) is None
                    )

                if is_unknown_channel:
                    logging.info(
                        "No saved message were found for channel '%s' [%d]. Saving all messages...",
                        channel.name,
                        channel.id,
                    )
                    try:
                        save_result = await self._save_from_channel(channel, count=None)
                        logging.info(save_result)
                    except Exception:
                        logging.warning(
                            "Cannot save channel '%s' [%d]", channel.name, channel.id
                        )
                else:
                    logging.info(
                        "Saved messages were found for channel '%s' [%d]. Saving older and newer messages...",
                        channel.name,
                        channel.id,
                    )
                    # try:
                    # TODO: Save older and newer messages
                    # except:
                    #     logging.warn(
                    #         "Cannot save channel '%s' [%d]", channel.name, channel.id
                    # )

                # try:
                # TODO: save_result = await self._save_from_channel(channel)
                # TODO: logging.info(save_result)
                # except:
                # logging.warn("Cannot save channel [%d]",channel.id)

            # if tracked_guild.last_saved_msg is not None:
            #     timestamp: datetime = datetime.fromisoformat(
            #         tracked_guild.last_saved_msg.timestamp
            #     )
            #     logging.info(
            #         "Saving new messages from guild '%d' since %s...",
            #         tracked_guild.guild_id,
            #         timestamp,
            #     )
            #     known_channels = await self._get_known_channels(tracked_guild.database)
            #     for channel in known_channels:
            #         save_result = await self._save_from_channel(
            #             channel, after=timestamp
            #         )
            #         logging.info(save_result)

        logging.info("'save' command done.")
        await ctx.send("`Done`")

    @commands.command()
    @commands.is_owner()
    async def saveall(self, ctx: commands.Context, guild_id: int, count: int = 20):
        """Sauvegarde les messages de tous les channels possibles à partir d'ici"""
        save_results = {}
        impossible_channels = []

        guild = self.bot.get_guild(guild_id)
        if guild is None:
            await ctx.reply("Je ne trouve pas cette guild")
            return

        tracked_guild = get_tracked_guild(self.bot, guild_id)

        # Détection des channels
        for channel in guild.channels:
            if not isinstance(channel, discord.TextChannel):
                continue

            # Si channel ignoré, passer
            if channel.id in tracked_guild.ignored_channels_ids:
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
        """Save old sur les channels connus en db"""
        db = get_tracked_guild(self.bot, guild_id).database
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
        count: int | None = 100,
        before: Snowflake | datetime | None = None,
        after: Snowflake | datetime | None = None,
        around: Snowflake | datetime | None = None,
        oldest_first: bool | None = None,
    ) -> SaveResult:
        """Enregistre les messages d'un channel dans la BDD associée"""
        guild = channel.guild
        db = get_tracked_guild(self.bot, guild.id).database

        save_result = SaveResult()

        with db.bind_ctx([Message]):
            async for message in channel.history(
                limit=count,
                before=before,
                after=after,
                around=around,
                oldest_first=oldest_first,
            ):
                save_result.trouves += 1

                # Progress
                if save_result.trouves % 500 == 0:
                    logging.info(f"{save_result.trouves} / {count}")

                # Ignorer messages bot
                if message.author.bot:
                    save_result.from_bot += 1
                    continue

                # Vérifier si le message existe avant d'enregistrer
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

    @commands.command()
    @commands.is_owner()
    async def channels(self, ctx: commands.Context, guild_id: Optional[int]):
        """Known channels"""
        max_lines = 15

        if guild_id is None:
            guild_id = ctx.channel.guild.id

        tracked_guild = get_tracked_guild(self.bot, guild_id)
        db = tracked_guild.database
        guild = self.bot.get_guild(guild_id)

        if guild is None:
            await ctx.send("Je ne trouve pas cette guild")
            return

        # Récupérer liste channels connus
        known_channels: List[Tuple[discord.TextChannel, int]] = []

        # Saved channels but cannot be retrieved
        unknown_channels: List[Tuple[int, int]] = []

        with db.bind_ctx([Message]):
            for channel_count in (
                Message.select(
                    Message.channel_id, fn.COUNT(Message.channel_id).alias("count")
                )
                .group_by(Message.channel_id)
                .order_by(fn.COUNT(Message.channel_id).desc())
            ):
                known_channel = self.bot.get_channel(channel_count.channel_id)
                if isinstance(known_channel, discord.TextChannel):
                    known_channels.append((known_channel, channel_count.count))
                else:
                    unknown_channels.append(
                        (channel_count.channel_id, channel_count.count)
                    )
        if not known_channels:
            await ctx.send("Aucun channel connu, d'abord utiliser saveall ou save")
            return

        embed = discord.Embed(
            title="Salons",
            description=f"Résumé des salons enregistrés sur le serveur **{guild.name}**.",
        )
        embed.set_author(name=guild.name, icon_url=guild.icon.url)
        known_channels_str = (
            "> *Ces salons sont actuellement enregistrés par Abeille.*\n"
        )
        known_channels_str += "\n".join(
            [
                f"{channel.name} - {msg_count} message(s)"
                for channel, msg_count in known_channels[:max_lines]
            ]
        )
        known_channels_str = self._append_hidden_channels_str(
            known_channels_str, len(known_channels[max_lines:])
        )

        unknown_channels_str = "> *Des messages ont été enregistrés sur ces salons, mais ces derniers ne sont plus accessibles par Abeille.*\n"
        unknown_channels_str += "\n".join(
            [
                f"`{channel_id}` - {msg_count} message(s)"
                for channel_id, msg_count in unknown_channels[:max_lines]
            ]
        )
        unknown_channels_str = self._append_hidden_channels_str(
            unknown_channels_str, len(unknown_channels[max_lines:])
        )
        embed.add_field(
            name="Salons enregistrés", value=known_channels_str, inline=False
        )
        embed.add_field(
            name="Salons inconnus", value=unknown_channels_str, inline=False
        )

        # Ignored channels
        ignored_channels_str = "Aucun salon ignoré."
        if tracked_guild.ignored_channels_ids:
            ignored_channels_strs = []
            for ignored_channel_id in tracked_guild.ignored_channels_ids[:max_lines]:
                ignored_channel = self.bot.get_channel(ignored_channel_id)
                if isinstance(ignored_channel, discord.TextChannel):
                    ignored_channels_strs.append(ignored_channel.name)
                else:
                    ignored_channels_strs.append(f"`{ignored_channel_id}`")
            ignored_channels_str = "\n".join(ignored_channels_strs)
            ignored_channels_str = self._append_hidden_channels_str(
                ignored_channels_str,
                len(tracked_guild.ignored_channels_ids[max_lines:]),
            )

        embed.add_field(name="Salons ignorés", value=ignored_channels_str, inline=False)

        await ctx.send(embed=embed)

    def _append_hidden_channels_str(
        self, channels_str: str, nb_hidden_channels: int
    ) -> str:
        if nb_hidden_channels:
            channels_str += "\n" + f"*+ {nb_hidden_channels} autre(s) salon(s)*"
        return channels_str

    async def _get_known_channels(self, db: Database) -> List[discord.TextChannel]:
        """Récupérer la liste des channels connus en db"""
        known_channels = []
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


async def setup(bot):
    await bot.add_cog(History(bot))
