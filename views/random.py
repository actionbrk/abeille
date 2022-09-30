import hashlib
from typing import Any, List, Optional

import discord
import os
from peewee import SQL, Database

from models.message import Message

salt = os.getenv("SALT").encode()  # type:ignore
iterations = int(os.getenv("ITER"))  # type:ignore
hash_name: str = os.getenv("HASHNAME")  # type:ignore


class RandomView(discord.ui.View):
    def __init__(
        self,
        channel_id: int,
        media: Optional[bool],
        length: Optional[int],
        member: Optional[discord.Member],
        db: Database,
    ):
        super().__init__(timeout=180)
        self.channel_id = channel_id
        self.media = media
        self.length = length
        self.member = member
        self.db = db

    @discord.ui.button(label="Encore", style=discord.ButtonStyle.primary)
    async def again(self, interaction: discord.Interaction, button: discord.ui.Button):
        # number = int(button.label) if button.label else 0
        # if number + 1 >= 5:
        #     button.style = discord.ButtonStyle.green
        #     button.disabled = True
        # button.label = str(number + 1)

        channel_id = self.channel_id

        with self.db:
            with self.db.bind_ctx([Message]):
                params_list: List[Any] = [channel_id]
                query_str = [
                    """
                    message_id > ((SELECT min(message_id) FROM message) + (
                    ABS(RANDOM()) % ((SELECT max(message_id) FROM message)-(SELECT min(message_id) FROM message))
                    ))
                    AND channel_id=?"""
                ]

                if self.media:
                    query_str.append("AND attachment_url is not null")

                if self.length and self.length > 0:
                    query_str.append("AND length(content) > ?")
                    params_list.append(self.length)

                if self.member:
                    query_str.append("AND author_id=?")
                    author_id = hashlib.pbkdf2_hmac(
                        hash_name, str(self.member.id).encode(), salt, iterations
                    ).hex()
                    params_list.append(author_id)

                sql: SQL = SQL(
                    " ".join(query_str),
                    params_list,
                )
                message: Message = Message.select().where(sql).get_or_none()

        text_to_send = []
        if message.content:
            text_to_send.append(message.content)
        if message.attachment_url:
            text_to_send.append(message.attachment_url)

        # Make sure to update the message with our updated selves
        await interaction.response.edit_message(
            content="\n".join(text_to_send), view=self
        )
