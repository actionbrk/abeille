""" Checks additionnels pour les commandes """

from discord.ext import commands


class Maintenance(commands.CheckFailure):
    """Erreur levée lorsqu'une commande est marquée en maintenance"""


def maintenance():
    """Check refusant la commande pour cause de maintenance"""

    async def predicate(ctx):
        if not await ctx.bot.is_owner(ctx.author):
            raise Maintenance()

    return commands.check(predicate)
