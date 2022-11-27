import logging
from datetime import datetime
from typing import List, Optional, Tuple

import discord
from discord.abc import Snowflake
from discord.ext import commands
from peewee import DoesNotExist, fn

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

                # Get oldest message from DB
                with db.bind_ctx([Message]):
                    oldest_msg: Message = (
                        Message.select()
                        .where(Message.channel_id == channel.id)
                        .order_by(Message.message_id)
                        .get_or_none()
                    )

                if tracked_guild.last_saved_msg is None or oldest_msg is None:
                    logging.info(
                        "No saved message were found for channel '%s' [%d].",
                        channel.name,
                        channel.id,
                    )
                    logging.info(
                        "Saving all messages for channel '%s' [%d]...",
                        channel.name,
                        channel.id,
                    )
                    try:
                        save_result = await self._save_from_channel(channel, count=None)
                        logging.info(save_result)
                    except discord.Forbidden:
                        logging.warning(
                            "Saving channel '%s' [%d] is forbidden.",
                            channel.name,
                            channel.id,
                        )
                else:
                    logging.info(
                        "Saved messages were found for channel '%s' [%d].",
                        channel.name,
                        channel.id,
                    )

                    try:
                        logging.info(
                            "Saving older messages for channel '%s' [%d], before %s...",
                            channel.name,
                            channel.id,
                            oldest_msg.timestamp,
                        )
                        save_result = await self._save_from_channel(
                            channel,
                            before=datetime.fromisoformat(str(oldest_msg.timestamp)),
                        )
                        logging.info(save_result)
                        logging.info(
                            "Saving newer messages for channel '%s' [%d], after %s...",
                            channel.name,
                            channel.id,
                            tracked_guild.last_saved_msg.timestamp,
                        )
                        save_result = await self._save_from_channel(
                            channel,
                            after=datetime.fromisoformat(
                                str(tracked_guild.last_saved_msg.timestamp)
                            ),
                        )
                        logging.info(save_result)
                    except discord.Forbidden:
                        logging.warning(
                            "Saving channel '%s' [%d] is forbidden.",
                            channel.name,
                            channel.id,
                        )

            # Clean not found channels
            # Does not delete channel with missing permissions
            logging.info("Cleaning known but unavailable channels...")
            with db.bind_ctx([Message]):
                for known_channel_id in Message.select(Message.channel_id).distinct():
                    known_channel = self.bot.get_channel(known_channel_id.channel_id)

                    clean_this_channel = False

                    # Check if channel is deleted
                    is_channel_found = isinstance(
                        known_channel,
                        discord.TextChannel,
                    )
                    if not is_channel_found:
                        clean_this_channel = True
                        logging.info(
                            "Channel [%d] is not available. Delete all messages...",
                            known_channel_id.channel_id,
                        )
                    # Check if channel is not allowed for Abeille (missing permissions) or other problems
                    else:
                        # Channel is found but can be unaccessible
                        try:
                            [msg async for msg in known_channel.history(limit=1)]
                        except discord.Forbidden:
                            clean_this_channel = True
                            logging.info(
                                "Channel %s [%d] is forbidden.",
                                known_channel.name,
                                known_channel.id,
                            )

                    if clean_this_channel:
                        logging.info(
                            "Delete channel [%d] in database...",
                            known_channel_id.channel_id,
                        )
                        Message.delete().where(
                            Message.channel_id == known_channel_id.channel_id
                        ).execute()
                        logging.info(
                            "Deleted channel [%d].", known_channel_id.channel_id
                        )

            logging.info("Cleaning done.")

        logging.info("'save' command done.")
        await ctx.send("`Done`")

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


async def setup(bot):
    await bot.add_cog(History(bot))
