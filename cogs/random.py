import configparser
import hashlib
import pathlib
from typing import Any, List, Optional

import discord
import os
from peewee import SQL, Database
from cogs.tracking import get_tracked_guild

from models.message import Message
from discord import app_commands

from discord.app_commands import Choice
from discord.ext import commands

salt = os.getenv("SALT").encode()  # type:ignore
iterations = int(os.getenv("ITER"))  # type:ignore
hash_name: str = os.getenv("HASHNAME")  # type:ignore


class Random(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="random",
        description="Un message ou un média aléatoire provenant de ce salon.",
    )
    @app_commands.describe(
        channel="Salon sur lequel choisir un message au hasard.",
        media="Uniquement des images.",
        length="Taille minimale du message.",
        member="Auteur du message.",
    )
    @app_commands.choices(
        length=[
            Choice(name="Gros messages (>~250 caractères)", value=250),
            Choice(name="Très gros messages (>~500 caractères)", value=500),
        ]
    )
    @app_commands.guild_only()
    async def random(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel],
        media: Optional[bool],
        length: Optional[int],
        member: Optional[discord.Member]
        # TODO: contains (random qui contient un terme)
    ):
        """Random message"""
        await interaction.response.defer(thinking=True)

        if not interaction.guild_id:
            await interaction.followup.send("Can't find guild id.")
            return

        # Specified channel or interaction channel by default
        channel_id = interaction.channel_id

        fallback_channel = None

        if channel:
            # TODO: Prevent user if specified channel is nsfw while interaction is done in sfw channel
            if channel.is_nsfw() and not interaction.channel.is_nsfw():
                fallback_channel = interaction.channel
            else:
                channel_id = channel.id

        db = get_tracked_guild(self.bot, interaction.guild_id).database

        message = await get_random_message(db, channel_id, media, length, member)

        if message is None:
            await interaction.followup.send(
                f"Je n'ai pas trouvé de message correspondant sur le salon <#{channel_id}>."
            )
        else:
            text_to_send = []
            if message.content:
                text_to_send.append(message.content)
            if message.attachment_url:
                text_to_send.append(message.attachment_url)
            await interaction.followup.send(
                "\n".join(text_to_send),
                view=RandomView(
                    channel_id, media, length, member, db, interaction.guild_id
                ),
            )
            if fallback_channel:
                await interaction.followup.send(
                    f"Le salon spécifié étant NSFW, le /random a été réalisé sur le salon <#{fallback_channel.id}>.",
                    ephemeral=True,
                )


async def get_random_message(
    db: Database,
    channel_id: int,
    media: Optional[bool],
    length: Optional[int],
    member: Optional[discord.Member],
):
    with db:
        with db.bind_ctx([Message]):
            params_list: List[Any] = [channel_id]
            query_str = [
                """
                message_id > ((SELECT min(message_id) FROM message) + (
                ABS(RANDOM()) % ((SELECT max(message_id) FROM message)-(SELECT min(message_id) FROM message))
                ))
                AND channel_id=?"""
            ]

            if media:
                query_str.append("AND attachment_url is not null")

            if length and length > 0:
                query_str.append("AND length(content) > ?")
                params_list.append(length)

            if member:
                query_str.append("AND author_id=?")
                author_id = hashlib.pbkdf2_hmac(
                    hash_name, str(member.id).encode(), salt, iterations
                ).hex()
                params_list.append(author_id)

            sql: SQL = SQL(
                " ".join(query_str),
                params_list,
            )
            return Message.select().where(sql).get_or_none()


async def setup(bot):
    await bot.add_cog(Random(bot))


class RandomView(discord.ui.View):
    def __init__(
        self,
        channel_id: int,
        media: Optional[bool],
        length: Optional[int],
        member: Optional[discord.Member],
        db: Database,
        guild_id: int,
    ):
        super().__init__(timeout=180)
        self.channel_id = channel_id
        self.media = media
        self.length = length
        self.member = member
        self.db = db
        self.guild_id = guild_id

        config = configparser.ConfigParser(allow_no_value=True)
        p = pathlib.Path(__file__).parent.parent
        config.read(p / "config.ini")

        guild_id_str = str(guild_id)
        self.again_role_needed = None
        if guild_id_str in config["RandomNeedsRole"]:
            self.again_role_needed = config["RandomNeedsRole"][guild_id_str]
        if guild_id_str in config["RandomAgainEmoji"]:
            self.again.emoji = config["RandomAgainEmoji"][guild_id_str]

    @discord.ui.button(label="Encore", style=discord.ButtonStyle.primary)
    async def again(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = configparser.ConfigParser(allow_no_value=True)
        p = pathlib.Path(__file__).parent.parent
        config.read(p / "config.ini")
        if self.again_role_needed:
            if interaction.user.get_role(int(self.again_role_needed)) is None:
                role_needed = interaction.guild.get_role(int(self.again_role_needed))
                await interaction.user.send(
                    f"Vous devez avoir le rôle **{role_needed.name}** pour utiliser ce bouton. 🐝",
                )
                return

        message = await get_random_message(
            self.db, self.channel_id, self.media, self.length, self.member
        )

        text_to_send = []
        if message.content:
            text_to_send.append(message.content)
        if message.attachment_url:
            text_to_send.append(message.attachment_url)

        # Make sure to update the message with our updated selves
        await interaction.response.edit_message(
            content="\n".join(text_to_send), view=self
        )
