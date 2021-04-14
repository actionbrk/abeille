""" Module d'enregistrement des messages """

import configparser
import hashlib
import os
import pathlib
from typing import Dict, List, Optional

import discord
from discord.ext import commands
from dotenv import load_dotenv
from models.message import Message
from peewee import Database, DoesNotExist, MySQLDatabase, OperationalError

# Chargement .env
load_dotenv()
db_host = os.getenv("DB_HOST")
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
salt = os.getenv("SALT").encode()  # type:ignore
iterations = int(os.getenv("ITER"))  # type:ignore
hash_name: str = os.getenv("HASHNAME")  # type:ignore


def get_message(message: discord.Message) -> Message:
    """ Convertir un message Discord en un message de BDD """
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
    """ Récupérer le cog Tracking """
    tracking_cog = bot.get_cog("Tracking")
    assert isinstance(tracking_cog, Tracking), "Impossible de récupérer le cog Tracking"
    return tracking_cog


class Tracking(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.tracked_guilds: Dict[int, Database] = {}
        self.ignored_channels: List[int] = []

        # Actualiser self.tracked_guilds au démarrage
        self._load_tracked_guilds()

    def get_guild_db(self, guild_id) -> Optional[Database]:
        """ Retourne la Database associée à l'ID de guild, None si pas trouvée """
        return self.tracked_guilds.get(guild_id)

    def _load_tracked_guilds(self):
        """ Charger les guilds à tracker et les channels à ignorer """
        config = configparser.ConfigParser(allow_no_value=True)
        p = pathlib.Path(__file__).parent.parent
        config.read(p / "config.ini")
        print("Chargement des guilds trackées...")
        for guild_id_str in config["Tracked"]:
            guild_id = int(guild_id_str)

            new_db = MySQLDatabase(
                f"{guild_id}_db",
                host=db_host,
                user=db_user,
                password=db_password,
                charset="utf8mb4",
                autoconnect=False,
            )

            try:
                new_db.connect()
                self.tracked_guilds[guild_id] = new_db
            except OperationalError:
                print(f"Base de données indisponible pour {guild_id}")
                continue
            finally:
                new_db.close()

            # Création tables
            with new_db:
                with new_db.bind_ctx([Message]):
                    new_db.create_tables([Message])

            print(f"Guild {guild_id} trackée")

        total_tracked = len(self.tracked_guilds)
        print(total_tracked, "guild(s) trackée(s)")

        # Ignorer channels
        print("Chargement des channels ignorés...")
        for section in config.sections():
            try:
                section_int = int(section)
            except ValueError:
                continue
            if section_int in self.tracked_guilds:
                for channel_id_str in config[section]:
                    channel_id = int(channel_id_str)
                    self.ignored_channels.append(channel_id)
                    print(f"{channel_id} ignoré")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """ Message détecté """

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


def setup(bot):
    bot.add_cog(Tracking(bot))
