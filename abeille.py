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

logging.basicConfig(level=logging.WARNING)

# TODO: LOGGING PEEWEE
# logger = logging.getLogger("peewee")
# Inutile? (double log) : logger.addHandler(logging.StreamHandler())
# logger.setLevel(logging.DEBUG)

load_dotenv()

discord_token = os.getenv("DISCORD_TOKEN")

if discord_token is None:
    sys.exit("DISCORD_TOKEN introuvable")

application_id = os.getenv("APPLICATION_ID")

if application_id is None:
    sys.exit("DISCORD_TOKEN introuvable")

COGS_DIR = "cogs"
DESCRIPTION = "Abeille"
intents = discord.Intents.default()


class AbeilleBot(commands.Bot):
    """Abeille Bot"""

    async def setup_hook(self):
        print("setup hook")

    async def on_ready(self):
        print("A")
        # for command in self.tree.walk_commands(guild=DEV_GUILD):
        #     print("command:", command.name)
        # TODO: sync_commands function in common/utils.py
        self.tree.copy_global_to(guild=DEV_GUILD)
        await self.tree.sync(guild=DEV_GUILD)
        await self.tree.sync()
        print("B")


async def main():
    """Main"""

    bot = AbeilleBot(
        command_prefix=commands.when_mentioned,
        description=DESCRIPTION,
        help_command=None,
        intents=intents,
        application_id=int(application_id),
    )

    async with bot:
        p = pathlib.Path(__file__).parent / COGS_DIR
        for extension in [
            f.name.replace(".py", "") for f in p.iterdir() if f.is_file()
        ]:
            try:
                if extension != "__init__":
                    try:
                        await bot.load_extension(COGS_DIR + "." + extension)
                    except commands.ExtensionFailed as err:
                        print("Extension loading failed", err.name, err.original)
                        raise
                    print(extension, " loaded")
            except (discord.ClientException, ModuleNotFoundError):
                print(f"Failed to load extension {extension}.")
                traceback.print_exc()

        await bot.start(discord_token)


if __name__ == "__main__":
    asyncio.run(main())
