from peewee import Model, BigIntegerField, CharField


class Identity(Model):
    """Hashed to real user ID"""

    author_id = CharField(primary_key=True)
    real_author_id = BigIntegerField()
