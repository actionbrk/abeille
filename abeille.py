import asyncio
import logging
import os
import pathlib
import sys
import traceback

import discord
from discord.ext import commands
from dotenv import load_dotenv

from common.utils import DEV_GUILD

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s (%(name)s %(module)s) %(message)s",
)

# TODO: LOGGING PEEWEE
# logger = logging.getLogger("peewee")
# Inutile? (double log) : logger.addHandler(logging.StreamHandler())
# logger.setLevel(logging.DEBUG)

load_dotenv()

discord_token = os.getenv("DISCORD_TOKEN")

if discord_token is None:
    sys.exit("DISCORD_TOKEN introuvable")

COGS_DIR = "cogs"
DESCRIPTION = "Abeille"
intents = discord.Intents.default()
intents.message_content = True


class AbeilleBot(commands.Bot):
    """Abeille Bot"""

    async def on_ready(self):
        logging.info("Syncing commands...")
        # for command in self.tree.walk_commands(guild=DEV_GUILD):
        #     print("command:", command.name)
        # TODO: sync_commands function in common/utils.py
        self.tree.copy_global_to(guild=DEV_GUILD)
        await self.tree.sync(guild=DEV_GUILD)
        await self.tree.sync()
        logging.info("Commands synced.")


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
