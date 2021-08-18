import os
import pathlib
import sys
import traceback
import logging
import discord
from discord.ext import commands
from discord_slash import SlashCommand
from dotenv import load_dotenv
from configparser import ConfigParser

logging.basicConfig(level=logging.INFO)

load_dotenv()

discord_token = os.getenv("DISCORD_TOKEN")

if discord_token is None:
    sys.exit("DISCORD_TOKEN introuvable")

# Get tracked guilds
guild_ids = []
config = ConfigParser(allow_no_value=True)
p = pathlib.Path(__file__).parent.parent
config.read(p / "config.ini")
for guild_id_str in config["Tracked"]:
    guild_ids.append(int(guild_id_str))

COGS_DIR = "cogs"
DESCRIPTION = "Abeille"
bot = commands.Bot(
    command_prefix=commands.when_mentioned, description=DESCRIPTION, help_command=None
)

slash = SlashCommand(bot, sync_commands=True, sync_on_cog_reload=True)

if __name__ == "__main__":
    p = pathlib.Path(__file__).parent / COGS_DIR
    for extension in [f.name.replace(".py", "") for f in p.iterdir() if f.is_file()]:
        try:
            if extension != "__init__":
                bot.load_extension(COGS_DIR + "." + extension)
                print(extension, " loaded")
        except (discord.ClientException, ModuleNotFoundError):
            print(f"Failed to load extension {extension}.")
            traceback.print_exc()


bot.run(discord_token)
