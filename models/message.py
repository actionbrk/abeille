from peewee import BigIntegerField, DateTimeField, Model, TextField, CharField


class Message(Model):
    message_id = BigIntegerField(primary_key=True)
    author_id = CharField()
    channel_id = BigIntegerField()
    timestamp = DateTimeField()
    content = TextField()
    attachment_url = TextField(null=True)
