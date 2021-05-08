import discord
from discord.ext import commands
from discord_slash import cog_ext, SlashContext
import configparser
import pathlib

guild_ids = []
config = configparser.ConfigParser(allow_no_value=True)
p = pathlib.Path(__file__).parent.parent
config.read(p / "config.ini")
for guild_id_str in config["Tracked"]:
    guild_ids.append(int(guild_id_str))


class Misc(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @cog_ext.cog_slash(name="bzz", description="Bzz bzz ! 🐝", guild_ids=guild_ids)
    async def ping(self, ctx: SlashContext):
        await ctx.send(
            f"Je fonctionne (avec une latence de {self.bot.latency*1000:.0f}ms) ! 🐝"
        )


def setup(bot):
    bot.add_cog(Misc(bot))
