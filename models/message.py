from peewee import BigIntegerField, DateTimeField, Model, TextField, CharField
from playhouse.sqlite_ext import FTS5Model, FTSModel, SearchField, RowIDField
from playhouse.shortcuts import ThreadSafeDatabaseMetadata


class Message(Model):
    """Message"""

    message_id = BigIntegerField(primary_key=True)
    author_id = CharField()
    channel_id = BigIntegerField()
    timestamp = DateTimeField()
    content = TextField()
    attachment_url = TextField(null=True)

    # class Meta:
    # model_metadata_class = ThreadSafeDatabaseMetadata


class MessageIndex(FTS5Model):
    """Message Index"""

    content = SearchField()

    class Meta:
        """MessageIndex Meta"""

        # model_metadata_class = ThreadSafeDatabaseMetadata

        options = {
            "content_rowid": Message.message_id,
            "content": Message,
        }
