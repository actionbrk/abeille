import discord
from discord.ext import commands
from discord_slash import cog_ext, SlashContext


class Misc(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @cog_ext.cog_slash(name="ping")
    async def ping(self, ctx: SlashContext):
        await ctx.reply("🐝")

    async def cog_command_error(self, ctx: commands.Context, error):
        await ctx.reply(f"Quelque chose s'est mal passée ({error}). 🐝")


def setup(bot):
    bot.add_cog(Misc(bot))
