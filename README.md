# abeille

![Docker build](https://github.com/actionbrk/abeille/actions/workflows/docker-image.yml/badge.svg)

Abeille is a Discord bot providing statistics and insights for guilds. It maintains a database with the messages from each connected guild, in order to perform efficient and various search operations (since Discord does not provide any API to perform search operations).

There is no public Abeille bot. You should run your own Abeille bot instance by following the steps below.

It depends on :

- [discord.js](https://github.com/discordjs/discord.js)
- [Chart.js](https://github.com/chartjs/Chart.js)
- [ChartjsNodeCanvas](https://github.com/SeanSobey/ChartjsNodeCanvas)
- [winston](https://github.com/winstonjs/winston)
- [date-fns](https://github.com/date-fns/date-fns)
- [chartjs-adapter-date-fns](https://github.com/chartjs/chartjs-adapter-date-fns)

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

### Environment variables

| Variable        | Description                                                                                                                                                                                                                               | Example Value        | Default Value      |
| --------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------- | ------------------ |
| `DISCORD_TOKEN` | The token for your Discord bot. You can obtain this from the Discord Developer Portal after creating a bot application.                                                                                                                   | `your-bot-token`     | _None_             |
| `GUILD_ID`      | _(Optional, recommended for development)_ The ID of the Discord guild (server) you want the bot to operate in. You can find this by enabling Developer Mode in Discord and right-clicking on the server name.                             | `123456789012345678` | _None_             |
| `HASHNAME`      | A unique identifier used for pseudonymizing user data. Choose a random string.                                                                                                                                                            | `sha256`             | `sha512`           |
| `ITER`          | The number of iterations for hashing operations. A higher value increases security but may impact performance.                                                                                                                            | `10000`              | `100000`           |
| `SALT`          | A random string used to add additional security to the hashing process. Generate a secure random string. Recommended length is 16 (cf. [NIST SP 800-132](https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-132.pdf) ) | `random-salt-string` | `bee-default-salt` |

### Run

You can now start Abeille by running the following command:

```bash
docker compose up -d --pull always
```

> By default, the `compose.yaml` file will pull the `latest` tag, which is pushed to Docker Hub whenever the `master` branch is updated.
> So you may have to run `docker compose down/up` from time to time in order to get the latest features (and run `docker image prune -a` to make some space).

Check logs by running:

```bash
docker logs abeille
```

## Develop

1. Clone project
2. Install bun from [Bun website](https://bun.sh/)
3. Copy and rename `.env.template` to `.env.local` and complete variables (cf. Environnement variables configuration)
4. Run `bun install` to install dependencies
5. Run `bun dev` to start your bot
