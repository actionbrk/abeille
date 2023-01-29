import configparser
import hashlib
import logging
import os
import pathlib
from typing import Any, List, Optional

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands
from peewee import SQL, Database

from cogs.tracking import get_tracked_guild
from models.message import Message

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
        if not interaction.guild_id:
            await interaction.response.send_message("Can't find guild id.")
            return

        # Specified channel or interaction channel by default
        channel_id = interaction.channel_id

        if channel:
            # TODO: Prevent user if specified channel is nsfw while interaction is done in sfw channel
            if channel.is_nsfw() and not interaction.channel.is_nsfw():
                await interaction.response.send_message(
                    "Impossible de lancer un /random sur un salon NSFW depuis un salon SFW.",
                    ephemeral=True,
                )
                return
            else:
                channel_id = channel.id

        db = get_tracked_guild(self.bot, interaction.guild_id).database

        await RandomView(
            interaction,
            self.bot,
            channel_id,
            media,
            length,
            member,
            db,
        ).start()


async def get_random_message(
    db: Database,
    channel_id: int,
    media: Optional[bool],
    length: Optional[int],
    member: Optional[discord.Member],
) -> Message:
    """Get a random message"""
    with db.bind_ctx([Message]):
        params_list: List[Any] = [channel_id, channel_id, channel_id, channel_id]
        query_str = [
            """
            message_id > ((SELECT min(message_id) FROM message WHERE channel_id=?) + (
            ABS(RANDOM()) % ((SELECT max(message_id) FROM message WHERE channel_id=?)-(SELECT min(message_id) FROM message WHERE channel_id=?))
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


async def get_embed(message: discord.Message) -> discord.Embed:
    reply_text = ""
    reply_thumb = None
    if message.reference:
        try:
            reference_msg: discord.Message = await message.channel.fetch_message(
                message.reference.message_id
            )
            reply_text = f"> **{reference_msg.author.name}** · <t:{int(reference_msg.created_at.timestamp())}>\n> {reference_msg.content if reference_msg.content else '[Contenu multimédia]'}\n\n"
            _reply_img = [
                a
                for a in reference_msg.attachments
                if a.content_type
                in ["image/jpeg", "image/png", "image/gif", "image/webp"]
            ]
            if _reply_img:
                reply_thumb = _reply_img[0]
        except Exception as exc:
            logging.warn("Failed to fetch message's reference.")

    message_content = message.content

    content = reply_text + message_content

    em = discord.Embed(
        description=content, timestamp=message.created_at, color=0x2F3136
    )
    em.set_author(name=message.author.name, icon_url=message.author.display_avatar.url)
    em.set_footer(text=f"#{message.channel.name}")

    image_preview = None
    media_links = []
    for a in message.attachments:
        if (
            a.content_type in ["image/jpeg", "image/png", "image/gif", "image/webp"]
            and not image_preview
        ):
            image_preview = a.url
        else:
            media_links.append(a.url)
    for msge in message.embeds:
        if msge.image and not image_preview:
            image_preview = msge.image.url
        elif msge.thumbnail and not image_preview:
            image_preview = msge.thumbnail.url

    if image_preview:
        em.set_image(url=image_preview)
    if reply_thumb:
        em.set_thumbnail(url=reply_thumb)
    if media_links:
        linkstxt = [f"[[{l.split('/')[-1]}]]({l})" for l in media_links]
        em.add_field(name="Média(s)", value="\n".join(linkstxt))

    return em


async def setup(bot):
    await bot.add_cog(Random(bot))


class RandomView(discord.ui.View):
    def __init__(
        self,
        interaction: discord.Interaction,
        bot: commands.Bot,
        channel_id: int,
        media: Optional[bool],
        length: Optional[int],
        member: Optional[discord.Member],
        db: Database,
    ):
        # Timeout has to be strictly lower than 15min=900s (since interaction is dead after this time)
        super().__init__(timeout=720)
        self.initial_interaction = interaction
        self.channel_id = channel_id
        self.media = media
        self.length = length
        self.member = member
        self.db = db
        self.message: discord.InteractionMessage = None
        self.bot = bot
        self.go_to_message_button: discord.ui.Button = None

    async def on_timeout(self) -> None:
        self.clear_items()
        await self.message.edit(view=self)

    async def start(self):
        random_msg = await get_random_message(
            self.db, self.channel_id, self.media, self.length, self.member
        )

        if random_msg is None:
            await self.initial_interaction.response.send_message(
                f"Je n'ai pas trouvé de message correspondant sur le salon <#{self.channel_id}>."
            )
        else:
            discord_msg = await self.initial_interaction.channel.fetch_message(
                random_msg.message_id
            )
            if discord_msg:
                self.go_to_message_button = discord.ui.Button(
                    label="Aller au message", url=discord_msg.jump_url
                )
                self.add_item(self.go_to_message_button)
                await self.initial_interaction.response.send_message(
                    embed=await get_embed(discord_msg),
                    view=self,
                )
            else:
                await self.initial_interaction.response.send_message(
                    content="Une erreur s'est produite.",
                    view=self,
                )

        self.message = await self.initial_interaction.original_response()

    @discord.ui.button(label="Encore", style=discord.ButtonStyle.primary)
    async def again(self, interaction: discord.Interaction, button: discord.ui.Button):
        allowed = interaction.user.id == self.initial_interaction.user.id
        if not allowed:
            await interaction.response.send_message(
                "Seul l'utilisateur ayant initié la commande peut toucher aux boutons. 🐝",
                ephemeral=True,
            )
            return

        random_msg = await get_random_message(
            self.db, self.channel_id, self.media, self.length, self.member
        )
        discord_msg = await interaction.channel.fetch_message(random_msg.message_id)
        if discord_msg:
            self.go_to_message_button.url = discord_msg.jump_url
            await interaction.response.edit_message(
                content=None,
                embed=await get_embed(discord_msg),
                view=self,
            )
        else:
            await interaction.response.edit_message(
                content="Une erreur s'est produite.",
                embed=None,
                view=self,
            )
