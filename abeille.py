"""Abeille"""

import asyncio
import logging
import os
import pathlib
import sys

import discord
from discord.ext import commands
from cogs.tracking import load_tracked_guilds


logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s (%(name)s %(module)s) %(message)s",
)

# TODO: LOGGING PEEWEE
# logger = logging.getLogger("peewee")
# logger.addHandler(logging.StreamHandler())
# logger.setLevel(logging.DEBUG)

discord_token = os.getenv("DISCORD_TOKEN")

if discord_token is None:
    sys.exit("DISCORD_TOKEN introuvable")

COGS_DIR = "cogs"
DESCRIPTION = "Abeille"
intents = discord.Intents.default()
intents.message_content = True
intents.members = True


class AbeilleBot(commands.Bot):
    """Abeille Bot"""

    async def on_ready(self):
        await load_tracked_guilds(self)
        logging.info("Ready!")


async def main():
    """Main"""

    bot = AbeilleBot(
        command_prefix=commands.when_mentioned,
        description=DESCRIPTION,
        help_command=None,
        intents=intents,
    )

    async with bot:
        p = pathlib.Path(__file__).parent / COGS_DIR
        for extension in [
            f.name.replace(".py", "") for f in p.iterdir() if f.is_file()
        ]:
            if extension != "__init__":
                try:
                    await bot.load_extension(COGS_DIR + "." + extension)
                    logging.info("'%s' extension loaded", extension)
                except commands.ExtensionFailed as err:
                    logging.error(
                        "'%s' extension loading failed: %s %s",
                        extension,
                        err.name,
                        err.original,
                    )
                    raise
                except (discord.ClientException, ModuleNotFoundError):
                    logging.error("Failed to load extension '%s'.", extension)
                    raise

        await bot.start(discord_token)


if __name__ == "__main__":
    asyncio.run(main())
