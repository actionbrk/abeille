from typing import List
from peewee import Database


class TrackedGuild:
    def __init__(
        self, database: Database, ignored_channels_ids: List[int] = []
    ) -> None:
        self.database = database
        self.ignored_channels_ids = ignored_channels_ids
