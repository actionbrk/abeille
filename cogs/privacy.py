import discord
import hashlib
import os
import csv
from dotenv import load_dotenv
from discord.ext import commands
from peewee import DoesNotExist

from cogs.tracking import get_tracking_cog
from models.message import Message

# Chargement paramètres DB
load_dotenv()
salt = os.getenv("SALT").encode()  # type:ignore
iterations = int(os.getenv("ITER"))  # type:ignore
hash_name: str = os.getenv("HASHNAME")  # type:ignore


class Privacy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    @commands.guild_only()
    @commands.is_owner()
    async def purge(self, ctx: commands.Context):
        """ Vérifier les messages supprimés sur cette guild """
        author = ctx.author
        author_id = hashlib.pbkdf2_hmac(
            hash_name, str(author.id).encode(), salt, iterations
        ).hex()
        supprimes = 0
        trouves = 0

        guild = ctx.guild
        if guild is None:
            await ctx.reply("Guild inconnue")
            return

        tracking_cog = get_tracking_cog(self.bot)
        db = tracking_cog.tracked_guilds[guild.id]

        msg_bot = await ctx.author.send(
            f"Je nettoie vos données concernant la guild **{guild.name}**... 🐝"
        )

        to_delete = []

        # TODO: édition des anciens messages si nécessaire
        # Récupérer les messages de l'utilisateur enregistrés pour cette guild
        # TODO: mettre la connexion à la db dans le for
        with db:
            with db.bind_ctx([Message]):
                for message in Message.select().where(Message.author_id == author_id):
                    trouves += 1

                    # discord.Message correspondant
                    try:
                        # TODO: faire channel.fetch_message (sur le channel correspondant)
                        await author.fetch_message(message)
                    except discord.NotFound:
                        to_delete.append(message.message_id)
                        supprimes += 1
                    except discord.Forbidden:
                        to_delete.append(message.message_id)
                        supprimes += 1

        # Suppression
        with db:
            with db.bind_ctx([Message]):
                for message_id in to_delete:
                    Message.delete_by_id(message_id)

        result = (
            f"Sur les **{trouves}** messages de vous que j'avais récoltés",
            f"sur **{guild.name}**, **{supprimes}** n'ont pas été retrouvés sur",
            "Discord et ont donc été supprimés de ma ruche.",
        )
        await msg_bot.edit(content=" ".join(result))

    @commands.command()
    @commands.guild_only()
    async def export(self, ctx: commands.Context):
        """ Exporter les données de la guild """
        author = ctx.author
        author_id = hashlib.pbkdf2_hmac(
            hash_name, str(author.id).encode(), salt, iterations
        ).hex()
        guild = ctx.guild
        if guild is None:
            await ctx.reply("Guild inconnue")
            return

        tracking_cog = get_tracking_cog(self.bot)
        db = tracking_cog.tracked_guilds[guild.id]

        temp_csv_path = f"/tmp/export_{author_id[:5]}.csv"

        await ctx.author.send(
            f"Je récupère les messages vous concernant sur la guild **{guild.name}**... 🐝"
        )

        with db:
            with db.bind_ctx([Message]):
                with open(temp_csv_path, "w") as fh:
                    writer = csv.writer(fh)

                    for message in (
                        Message.select()
                        .where(Message.author_id == author_id)
                        .tuples()
                        .iterator()
                    ):
                        writer.writerow(message)

        result = (
            "Voici les messages de vous que j'ai récoltés.",
            "Si vous souhaitez supprimer définitivement",
            "un message de ma ruche, utilisez la commande",
            "`@Abeille supprime <message_id>`.",
            "L'ID du message est la première information de chaque",
            "ligne du fichier que j'ai envoyé 🐝",
        )
        await ctx.author.send(
            " ".join(result),
            file=discord.File(temp_csv_path),
        )
        os.remove(temp_csv_path)

    @commands.command(aliases=["supprime", "supprimer"])
    @commands.guild_only()
    async def delete(self, ctx: commands.Context, message_id: int):
        """ Supprimer un message oublié par Abeille """
        author = ctx.author
        author_id = hashlib.pbkdf2_hmac(
            hash_name, str(author.id).encode(), salt, iterations
        ).hex()
        guild = ctx.guild
        if guild is None:
            await ctx.reply("Guild inconnue")
            return

        tracking_cog = get_tracking_cog(self.bot)
        db = tracking_cog.tracked_guilds[guild.id]

        # TODO: Parcourir chaque db
        with db:
            with db.bind_ctx([Message]):
                try:
                    message = (
                        Message.select()
                        .where(Message.author_id == author_id)
                        .where(Message.message_id == message_id)
                        .get()
                    )
                except DoesNotExist:
                    await ctx.author.send("Je n'ai pas ce message dans ma ruche 🐝")
                    return

        # Récupérer channel du message
        channel = self.bot.get_channel(message.channel_id)
        if not isinstance(channel, discord.TextChannel):
            with db:
                with db.bind_ctx([Message]):
                    Message.delete_by_id(message_id)
            await ctx.author.send(
                "Je n'ai plus accès au channel correspondant, message supprimé 🐝"
            )
            return

        # Récupérer discord.Message pour voir s'il existe toujours
        try:
            await channel.fetch_message(message)
            await ctx.author.send("Ce message est toujours visible sur Discord 🐝")
            return
        except (discord.NotFound, discord.Forbidden):
            pass

        with db:
            with db.bind_ctx([Message]):
                Message.delete_by_id(message_id)

        await ctx.author.send("Je viens de supprimer ce message de ma ruche 🐝")


def setup(bot):
    bot.add_cog(Privacy(bot))
