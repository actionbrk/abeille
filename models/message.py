from peewee import (
    BigIntegerField,
    CharField,
    DateField,
    DateTimeField,
    Model,
    TextField,
)
from playhouse.sqlite_ext import FTS5Model, SearchField


class Message(Model):
    """Message"""

    message_id = BigIntegerField(primary_key=True)
    author_id = CharField()
    channel_id = BigIntegerField()
    timestamp = DateTimeField()
    content = TextField()
    attachment_url = TextField(null=True)


class MessageDay(Model):
    """Messages count per day"""

    date = DateField(primary_key=True)
    count = BigIntegerField()


class MessageIndex(FTS5Model):
    """Message Index"""

    content = SearchField()

    class Meta:
        """MessageIndex Meta"""

        options = {
            "content_rowid": Message.message_id,
            "content": Message,
            "tokenize": "trigram",
        }
