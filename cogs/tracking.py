""" Module d'enregistrement des messages """

import configparser
import hashlib
import logging
import os
import pathlib
from typing import Dict, List, Optional
from datetime import datetime, date

import discord
from discord.ext import commands
from sqlite_utils import Database
from sqlite_utils.db import NotFoundError

from models.identity import Identity
from models.message import Message, MessageDay, MessageIndex
from models.trackedguild import TrackedGuild

# Chargement .env
# load_dotenv()
salt = os.getenv("SALT").encode()  # type:ignore
iterations = int(os.getenv("ITER"))  # type:ignore
hash_name: str = os.getenv("HASHNAME")  # type:ignore
dbs_folder_path = os.getenv("DBS_FOLDER_PATH")


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


class Tracking(commands.Cog):
    """Tracking module"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.tracked_guilds: Dict[int, TrackedGuild] = {}

        # Update self.tracked_guilds on start
        self._load_tracked_guilds()

    def _load_tracked_guilds(self):
        """Load tracked guilds and their settings"""
        logging.info("Loading tracked guilds...")
        config = configparser.ConfigParser(allow_no_value=True)
        p = pathlib.Path(__file__).parent.parent
        config.read(p / "config.ini")
        for guild_id_str in config["Tracked"]:
            guild_id = int(guild_id_str)

            new_db = Database(pathlib.Path(dbs_folder_path) / f"a_{guild_id}.db")

            # Création tables
            table_identity = new_db.create_table(
                "identity",
                {
                    "id": int,
                    "hashed_author_id": str,
                    "author_id": int,
                },
                pk="id",
                not_null={"id", "hashed_author_id"},
                if_not_exists=True,
            )
            table_identity.create_index(
                ["hashed_author_id"], unique=True, if_not_exists=True
            )
            table_identity.create_index(["author_id"], unique=True, if_not_exists=True)

            table_message = new_db.create_table(
                "message",
                {
                    "message_id": int,
                    "identity_id": int,
                    "channel_id": int,
                    "created_at": datetime,
                    "edited_at": datetime,
                    "content": str,
                    "reference_message_id": int,
                },
                pk="message_id",
                not_null={"message_id", "identity_id", "channel_id", "created_at"},
                foreign_keys=[("identity_id", "identity", "id")],
                if_not_exists=True,
            )
            if not table_message.detect_fts():
                table_message.enable_fts(
                    ["content"], create_triggers=True, tokenize="trigram"
                )

            new_db.create_table(
                "messageday",
                {
                    "date": date,
                    "count": int,
                },
                pk="date",
                not_null={"date", "count"},
                if_not_exists=True,
            )

            new_db.create_table(
                "attachment",
                {
                    "id": int,
                    "message_id": int,
                    "url": str,
                    "filename": str,
                    "size": int,
                    "voice_message_duration": float,
                    "is_spoiler": bool,
                },
                pk="id",
                not_null={"id", "message_id", "url", "filename", "size", "is_spoiler"},
                foreign_keys=[("message_id", "message", "message_id")],
                if_not_exists=True,
            )

            new_db.create_table(
                "reaction",
                {
                    "message_id": int,
                    "emoji_name": str,  # reaction.emoji.name if is_custom_emoji() else reaction.emoji
                    "emoji_id": int,
                    "identity_id": int,
                },
                pk=("message_id", "emoji_name", "emoji_id", "identity_id"),
                not_null={"message_id", "emoji_name", "identity_id"},
                foreign_keys=[
                    ("message_id", "message", "message_id"),
                    ("identity_id", "identity", "id"),
                ],
                if_not_exists=True,
            )

            # Get what was the last saved message before the bot went down
            tracked_guild = TrackedGuild(new_db, guild_id)
            last_saved_msgs = list(
                table_message.rows_where(order_by="message_id", limit=1)
            )
            if last_saved_msgs:
                tracked_guild.last_saved_msg = last_saved_msgs[0]

            # Ignore blacklisted channels
            # TODO: blacklist table
            # if config.has_section("IgnoredChannels") and config.has_option(
            #     "IgnoredChannels", guild_id_str
            # ):
            #     logging.info("Loading ignored channels...")
            #     ignored_channels_ids = [
            #         int(ignored_channel_str.strip())
            #         for ignored_channel_str in config.get(
            #             "IgnoredChannels", guild_id_str
            #         ).split(",")
            #     ]
            #     tracked_guild.ignored_channels_ids = ignored_channels_ids
            #     logging.info(
            #         "%d channel(s) ignored for tracked guild %d.",
            #         len(ignored_channels_ids),
            #         guild_id,
            #     )

            self.tracked_guilds[guild_id] = tracked_guild
            logging.info("Guild '%s' is tracked.", guild_id_str)

        total_tracked = len(self.tracked_guilds)
        logging.info("%d guild(s) are being tracked.", total_tracked)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Message sent"""
        # Si message privé
        if message.guild is None:
            return

        # Ignorer messages bot
        if message.author.bot:
            return

        guild_id = message.guild.id

        # Si le message vient d'une guild sans DB
        if not guild_id in self.tracked_guilds:
            logging.debug(
                "A message has been sent on a untracked guild ; it will not be saved."
            )
            return

        tracked_guild = self.tracked_guilds[guild_id]

        # Si channel ignoré
        if message.channel.id in tracked_guild.ignored_channels_ids:
            logging.debug(
                "A message has been sent on a blacklisted channel ; it will not be saved."
            )
            return

        self.insert_message(tracked_guild.database, message)

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        """Message deleted"""
        # Si message privé
        if payload.guild_id is None:
            return

        guild_id = payload.guild_id

        # Si le message vient d'une guild sans DB
        if not guild_id in self.tracked_guilds:
            return

        tracked_guild = self.tracked_guilds[guild_id]

        # TODO: Si channel ignoré
        # if message.channel.id in tracked_guild.ignored_channels_ids:
        #     return

        db = tracked_guild.database
        message_id = payload.message_id

        self.delete_message(db, message_id)

        logging.debug("Deleted message %d.", message_id)

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent):
        """Message edited"""
        # Si message privé
        if payload.guild_id is None:
            return

        guild_id = payload.guild_id

        # Si le message vient d'une guild sans DB
        if not guild_id in self.tracked_guilds:
            return

        tracked_guild = self.tracked_guilds[guild_id]

        # TODO: Si channel ignoré
        # if message.channel.id in tracked_guild.ignored_channels_ids:
        #     return

        db = tracked_guild.database
        message_id = payload.message_id
        guild = self.bot.get_channel(payload.channel_id)
        message = await guild.fetch_message(message_id)

        # Ignore bot messages
        if message.author.bot:
            return

        self.delete_message(db, message_id)
        self.insert_message(db, message)

        logging.debug("Edited message %d.", message_id)

    def delete_message(self, db: Database, message_id: int) -> None:
        """Delete message from db"""
        db["attachment"].delete_where("message_id = ?", [message_id])
        db["reaction"].delete_where("message_id = ?", [message_id])
        db["message"].delete_where("message_id = ?", [message_id])

    def insert_message(self, db: Database, message: discord.Message) -> None:
        """Insert message into db"""
        logging.debug("Inserting message %d...", message.id)

        # Get referenced message id
        reference_message_id = None
        if message.reference:
            reference_message_id = message.reference.message_id

        hashed_author_id = hashlib.pbkdf2_hmac(
            hash_name, str(message.author.id).encode(), salt, iterations
        ).hex()

        identity_list = list(
            db["identity"].rows_where("hashed_author_id = ?", [hashed_author_id])
        )
        if not identity_list:
            db["identity"].insert({"hashed_author_id": hashed_author_id})
            identity = list(
                db["identity"].rows_where("hashed_author_id = ?", [hashed_author_id])
            )[0]
        else:
            identity = identity_list[0]

        db["message"].insert(
            {
                "message_id": message.id,
                "identity_id": identity["id"],
                "channel_id": message.channel.id,
                "created_at": message.created_at,
                "edited_at": message.edited_at,
                "content": message.content,
                "reference_message_id": reference_message_id,
            }
        )

        # Attachments
        db["attachment"].insert_all(
            [
                {
                    "id": attachment.id,
                    "message_id": message.id,
                    "url": attachment.url,
                    "filename": attachment.filename,
                    "size": attachment.size,
                    "voice_message_duration": attachment.duration,
                    "is_spoiler": attachment.is_spoiler(),
                }
                for attachment in message.attachments
            ]
        )

        # Reactions
        # TODO: Ajouter les identity nécessaires des "réacteurs" au fil de l'eau
        reactions = 

        logging.debug("Inserted message %d.", message.id)


async def setup(bot):
    await bot.add_cog(Tracking(bot))
