# abeille
Abeille is a Discord bot providing statistics and insights for guilds. It maintains a database with the messages from each connected guild, in order to perform efficient and various search operations (since Discord does not provide any API to perform search operations).

There is no public Abeille bot. You should run your own Abeille bot instance by following the steps below.

It depends on [Python](https://github.com/python), [discord.py](https://github.com/Rapptz/discord.py) and [SQLite](https://github.com/sqlite/sqlite).

## Features
- Saves messages from tracked guilds while using pseudonymization
- Provides slash commands to graph trending expressions, show random messages...

## Run your own Abeille

Abeille is not (yet) a public Discord bot. You can run your own instance of Abeille by following these steps:

### Setting up
1. Create a folder.
2. Copy the [compose.yaml.template](compose.yaml.template) and [.env.template](.env.template) files into the folder.
3. Rename them to `compose.yaml` and `.env` respectively.
4. Configure `.env` file.

### Run

You can now start Abeille by running the following command:

```bash
docker compose up -d --pull always
```