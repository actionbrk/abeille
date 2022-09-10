""" Module d'enregistrement des messages """

import configparser
import hashlib
import logging
import os
import pathlib
from typing import Dict, List, Optional

import discord
from discord.ext import commands
from models.message import Message, MessageDay, MessageIndex
from peewee import Database, DoesNotExist, OperationalError
from playhouse.sqlite_ext import SqliteExtDatabase

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


def get_tracking_cog(bot: commands.Bot) -> "Tracking":
    """Récupérer le cog Tracking"""
    tracking_cog: Optional["Tracking"] = bot.get_cog("Tracking")  # type: ignore
    if tracking_cog is None:
        raise Exception("Impossible de récupérer le cog Tracking")
    return tracking_cog


class Tracking(commands.Cog):
    """Tracking module"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.tracked_guilds: Dict[int, Database] = {}
        self.ignored_channels: List[int] = []

        # Actualiser self.tracked_guilds au démarrage
        self._load_tracked_guilds()

    def get_guild_db(self, guild_id) -> Optional[Database]:
        """Retourne la Database associée à l'ID de guild, None si pas trouvée"""
        return self.tracked_guilds.get(guild_id)

    def _load_tracked_guilds(self):
        """Charger les guilds à tracker et les channels à ignorer"""
        logging.info("Loading tracked guilds...")
        config = configparser.ConfigParser(allow_no_value=True)
        p = pathlib.Path(__file__).parent.parent
        config.read(p / "config.ini")
        for guild_id_str in config["Tracked"]:
            guild_id = int(guild_id_str)

            # TODO: Custom db folder path (outside of project folder....)
            new_db = SqliteExtDatabase(pathlib.Path(dbs_folder_path) / f"{guild_id}.db")

            try:
                new_db.connect()
                self.tracked_guilds[guild_id] = new_db
            except OperationalError:
                logging.error("Base de données indisponible pour %s", guild_id_str)
                continue
            finally:
                new_db.close()

            # Création tables
            with new_db:
                with new_db.bind_ctx([Message, MessageIndex, MessageDay]):
                    # Création tables
                    new_db.create_tables([Message, MessageIndex, MessageDay])
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

                    # TODO: Commande dédiée ? MessageIndex.rebuild()
                    # TODO: Commande dédiée ? MessageIndex.optimize()

            logging.info("Guild '%s' is tracked.", guild_id_str)

        total_tracked = len(self.tracked_guilds)
        logging.info("%d guild(s) are being tracked.", total_tracked)

        # Ignorer channels
        logging.info("Loading ignored guilds...")
        for section in config.sections():
            try:
                section_int = int(section)
            except ValueError:
                continue
            if section_int in self.tracked_guilds:
                for channel_id_str in config[section]:
                    channel_id = int(channel_id_str)
                    self.ignored_channels.append(channel_id)
                    logging.info("Channel '%d' is ignored.", channel_id)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Message sent"""

        # TODO: Enregistrer en BDD le timestamp du dernier message enregistré pour relancer un
        # saveall depuis cette date lors du lancement du cog

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

        # Si channel ignoré
        if message.channel.id in self.ignored_channels:
            return

        db = self.tracked_guilds[guild_id]

        msg = get_message(message)

        with db:
            with db.bind_ctx([Message]):
                msg.save(force_insert=True)

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

        # Si channel ignoré
        if message.channel.id in self.ignored_channels:
            return

        db = self.tracked_guilds[guild_id]

        # Supprimer
        with db:
            with db.bind_ctx([Message]):
                Message.delete_by_id(message.id)

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

        # Si channel ignoré
        if after.channel.id in self.ignored_channels:
            return

        db = self.tracked_guilds[guild_id]

        msg = get_message(after)

        with db:
            with db.bind_ctx([Message]):
                try:
                    Message.get_by_id(after.id)
                    msg.save()
                except DoesNotExist:
                    msg.save(force_insert=True)


async def setup(bot):
    await bot.add_cog(Tracking(bot))
