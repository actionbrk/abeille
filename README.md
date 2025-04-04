# abeille
![Docker build](https://github.com/actionbrk/abeille/actions/workflows/docker-image.yml/badge.svg)

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
2. Copy [compose.yaml.template](compose.yaml.template) into the folder.
3. Rename it to `compose.yaml`.
4. Configure `.compose.yaml` file.

### Run

You can now start Abeille by running the following command:

```bash
docker compose up -d --pull always
```

> By default, the `compose.yaml` file will pull the `latest` tag, which is pushed to Docker Hub whenever the `master` branch is updated.
So you may have to run `docker compose down/up` from time to time in order to get the latest features (and run `docker image prune -a` to make some space).

Check logs by running:
```bash
docker logs abeille
```

## Develop

1. Clone project.
2. Copy [compose.yaml.dev.template](compose.yaml.dev.template) into the folder.
3. Rename it to `compose.yaml`.
4. Run `docker compose up --watch --build`.
