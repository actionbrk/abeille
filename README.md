# abeille
Abeille is a Discord bot providing statistics and insights for guilds. It maintains a database with the messages from each connected guild, in order to perform efficient and various search operations (since Discord does not provide any API to perform search operations).

There is no public Abeille bot. You should run your own Abeille bot instance using this library.

It depends on [Python](https://github.com/python), [discord.py](https://github.com/Rapptz/discord.py) and [SQLite](https://github.com/sqlite/sqlite).

## Features
- Saves messages from tracked guilds while using pseudonymization
- Provides slash commands to graph trending expressions, show random messages...
