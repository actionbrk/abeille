from discord.ext import commands


class CogManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="load", hidden=True)
    @commands.is_owner()
    async def load(self, ctx, *, cog: str):
        """Command which Loads a Module.
        Remember to use dot path. e.g: cogs.owner"""

        try:
            self.bot.load_extension(cog)
        except Exception as e:
            await ctx.send(f"**`ERROR:`** {type(e).__name__} - {e}")
        else:
            await ctx.send("**`SUCCESS`**")

    @commands.command(name="unload", hidden=True)
    @commands.is_owner()
    async def unload(self, ctx, *, cog: str):
        """Command which Unloads a Module.
        Remember to use dot path. e.g: cogs.owner"""

        try:
            self.bot.unload_extension(cog)
        except Exception as e:
            await ctx.send(f"**`ERROR:`** {type(e).__name__} - {e}")
        else:
            await ctx.send("**`SUCCESS`**")

    @commands.command(name="reload", hidden=True)
    @commands.is_owner()
    async def reload(self, ctx, *, cog: str):
        """Command which Reloads a Module.
        Remember to use dot path. e.g: cogs.owner"""

        try:
            self.bot.reload_extension(cog)
        except Exception as e:
            await ctx.send(f"**`ERROR:`** {type(e).__name__} - {e}")
        else:
            await ctx.send("**`SUCCESS`**")

    @commands.command(name="extensions", hidden=True)
    @commands.is_owner()
    async def extensions(self, ctx):
        for ext_name, _ext in self.bot.extensions.items():
            await ctx.send(ext_name)

    @commands.command(name="cogs", hidden=True)
    @commands.is_owner()
    async def cogs(self, ctx):
        for cog_name, _cog in self.bot.cogs.items():
            await ctx.send(cog_name)


def setup(bot):
    bot.add_cog(CogManager(bot))
