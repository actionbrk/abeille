""" Module d'enregistrement des messages """

import hashlib
import logging
import os
from typing import Dict, List, Optional

import discord
from discord.ext import commands
from models.identity import Identity
from models.message import Message, MessageDay, MessageIndex
from peewee import DoesNotExist, OperationalError
from playhouse.sqlite_ext import SqliteExtDatabase

from models.trackedguild import TrackedGuild

salt = os.getenv("SALT").encode()  # type:ignore
iterations = int(os.getenv("ITER"))  # type:ignore
hash_name: str = os.getenv("HASHNAME")  # type:ignore


def get_message(message: discord.Message) -> Message:
    """Convertir un message Discord en un message de BDD"""
    message_id = message.id
    author_id = hashlib.pbkdf2_hmac(
        hash_name, str(message.author.id).encode(), salt, iterations
    ).hex()
    channel_id = message.channel.id
    timestamp = message.created_at
    content = message.content
    attachment_url = None
    if message.attachments:
        attachment_url = message.attachments[0].url

    return Message(
        message_id=message_id,
        author_id=author_id,
        channel_id=channel_id,
        timestamp=timestamp,
        content=content,
        attachment_url=attachment_url,
    )


def get_tracked_guild(bot: commands.Bot, guild_id: int) -> TrackedGuild:
    """Get tracked guild from ID"""
    tracking_cog: Optional["Tracking"] = bot.get_cog("Tracking")  # type: ignore
    if tracking_cog is None:
        raise Exception("Impossible de récupérer le cog Tracking")
    return tracking_cog.tracked_guilds[guild_id]


def get_tracked_guilds(bot: commands.Bot) -> Dict[int, TrackedGuild]:
    """Get tracked guilds"""
    tracking_cog: Optional["Tracking"] = bot.get_cog("Tracking")  # type: ignore
    if tracking_cog is None:
        raise Exception("Impossible de récupérer le cog Tracking")
    return tracking_cog.tracked_guilds


async def load_tracked_guilds(bot: commands.Bot):
    """Load tracked guilds"""
    tracking_cog: Optional["Tracking"] = bot.get_cog("Tracking")  # type: ignore
    if tracking_cog is None:
        raise Exception("Impossible de récupérer le cog Tracking")
    return await tracking_cog.load_tracked_guilds()


class Tracking(commands.Cog):
    """Tracking module"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.tracked_guilds: Dict[int, TrackedGuild] = {}

    async def load_tracked_guilds(self):
        """Load tracked guilds and their settings"""
        logging.info("Loading available guilds...")

        async for guild in self.bot.fetch_guilds():

            guild_id = guild.id
            new_db = SqliteExtDatabase(f"/db/{guild_id}.db")

            try:
                new_db.connect()
                tracked_guild = TrackedGuild(new_db, guild_id)
            except OperationalError:
                logging.error("Base de données indisponible pour %d", guild_id)
                continue
            finally:
                new_db.close()

            with new_db.bind_ctx([Message, MessageIndex, MessageDay, Identity]):
                # Création tables
                new_db.create_tables([Message, MessageIndex, MessageDay, Identity])
                # Création triggers
                try:
                    new_db.execute_sql(
                        "CREATE TRIGGER message_ad AFTER DELETE ON message BEGIN INSERT INTO messageindex(messageindex, rowid, content) VALUES('delete', old.message_id, old.content); END;"
                    )
                    new_db.execute_sql(
                        """CREATE TRIGGER message_ai AFTER INSERT ON message BEGIN
                        INSERT INTO messageindex(rowid, content) VALUES (new.message_id, new.content);
                        END;"""
                    )
                    new_db.execute_sql(
                        """CREATE TRIGGER message_au AFTER UPDATE ON message BEGIN INSERT INTO messageindex(messageindex, rowid, content) VALUES('delete', old.message_id, old.content);
                        INSERT INTO messageindex(rowid, content) VALUES (new.message_id, new.content); END;"""
                    )
                except Exception as exc:
                    logging.warning("Triggers could not be created: %s", exc)

                # Get what was the last saved message before the bot went down
                tracked_guild.last_saved_msg = (
                    Message.select().order_by(Message.message_id.desc()).get_or_none()
                )

            self.tracked_guilds[guild_id] = tracked_guild
            logging.info("Guild '%d' is tracked.", guild_id)

        total_tracked = len(self.tracked_guilds)
        logging.info("%d guild(s) are being tracked.", total_tracked)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Message sent"""
        # Si message privé
        if not message.guild:
            return

        # Ignorer messages bot
        if message.author.bot:
            return

        guild_id = message.guild.id

        # Si le message vient d'une guild sans DB
        if not guild_id in self.tracked_guilds:
            return

        tracked_guild = self.tracked_guilds[guild_id]

        # Si channel ignoré
        if message.channel.id in tracked_guild.ignored_channels_ids:
            return

        db = tracked_guild.database

        msg = get_message(message)

        with db.bind_ctx([Message]):
            msg.save(force_insert=True)

        logging.debug("Saved message %d.", message.id)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Message deleted"""
        # Si message privé
        if not message.guild:
            return

        # Ignorer messages bot
        if message.author.bot:
            return

        guild_id = message.guild.id

        # Si le message vient d'une guild sans DB
        if not guild_id in self.tracked_guilds:
            return

        tracked_guild = self.tracked_guilds[guild_id]

        # Si channel ignoré
        if message.channel.id in tracked_guild.ignored_channels_ids:
            return

        db = tracked_guild.database

        # Supprimer
        with db.bind_ctx([Message]):
            Message.delete_by_id(message.id)

        logging.debug("Deleted message %d.", message.id)

    @commands.Cog.listener()
    async def on_message_edit(self, _before: discord.Message, after: discord.Message):
        """Message edited"""

        # Si message privé
        if not after.guild:
            return

        # Ignorer messages bot
        if after.author.bot:
            return

        guild_id = after.guild.id

        # Si le message vient d'une guild sans DB
        if not guild_id in self.tracked_guilds:
            return

        tracked_guild = self.tracked_guilds[guild_id]

        # Si channel ignoré
        if after.channel.id in tracked_guild.ignored_channels_ids:
            return

        db = tracked_guild.database

        msg = get_message(after)

        with db.bind_ctx([Message]):
            try:
                Message.get_by_id(after.id)
                msg.save()
            except DoesNotExist:
                msg.save(force_insert=True)

        logging.debug("Edited message %d.", after.id)


async def setup(bot):
    await bot.add_cog(Tracking(bot))
