from common.utils import GUILD_IDS
from discord.ext import commands
from discord_slash import cog_ext, SlashContext


class Misc(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @cog_ext.cog_slash(
        name="bzz", description="Bzz bzz (ping) ! 🐝", guild_ids=GUILD_IDS
    )
    async def ping(self, ctx: SlashContext):
        await ctx.send(
            f"Je fonctionne (avec une latence de {self.bot.latency*1000:.0f}ms) ! 🐝"
        )


def setup(bot):
    bot.add_cog(Misc(bot))
