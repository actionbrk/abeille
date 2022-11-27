from typing import List
from peewee import Database

from models.message import Message


class TrackedGuild:
    def __init__(
        self,
        database: Database,
        guild_id: int,
    ) -> None:
        self.database = database
        self.guild_id = guild_id
        self.ignored_channels_ids: List[int] = []
        self.last_saved_msg: Message | None = None
