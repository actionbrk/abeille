""" Commandes de tendances """

import hashlib
import io
import logging
import os
import textwrap
from datetime import date, timedelta

import discord
import pandas
import plotly.express as px
import plotly.graph_objects as go
from common.checks import Maintenance
from common.utils import emoji_to_str
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands
from models.message import Message, MessageDay, MessageIndex
from peewee import RawQuery, Select, fn

from cogs.tracking import get_tracking_cog

PERIODE = 1100
ROLLING_AVERAGE = 14

token = os.getenv("DW_TOKEN")
salt = os.getenv("SALT").encode()  # type:ignore
iterations = int(os.getenv("ITER"))  # type:ignore
hash_name: str = os.getenv("HASHNAME")  # type:ignore


class Activity(commands.Cog):
    """Commands to graph guild's activity"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="trend", description="Dessiner la tendance d'une expression."
    )
    @app_commands.describe(
        terme="Le mot ou l'expression à rechercher.",
        periode="Période de temps max sur laquelle dessiner la tendance.",
    )
    @app_commands.choices(
        periode=[
            Choice(name="6 mois", value=182),
            Choice(name="1 an", value=365),
            Choice(name="2 ans", value=730),
            Choice(name="3 ans", value=1096),
            Choice(name="Depuis le début", value=9999),
        ]
    )
    @app_commands.guild_only()
    async def trend_slash(
        self, interaction: discord.Interaction, terme: str, periode: Choice[int]
    ):
        await interaction.response.defer(thinking=True)
        guild_id = interaction.guild_id

        if not guild_id:
            await interaction.followup.send("Can't find guild id.")
            return

        # FTS5 : can't tokenize expressions with less than 3 characters
        if len(terme) < 3:
            await interaction.followup.send(
                "Je ne peux pas traiter les expressions de moins de 3 caractères. 🐝"
            )
            return

        # FTS5 : enclose in double quotes
        terme_fts = f'"{terme}"'

        jour_debut = date.today() - timedelta(days=periode.value)
        jour_fin = None
        tracking_cog = get_tracking_cog(self.bot)
        db = tracking_cog.tracked_guilds[guild_id]
        guild_name = self.bot.get_guild(guild_id)

        with db:
            with db.bind_ctx([Message, MessageIndex, MessageDay]):

                if periode.value == 9999:
                    oldest_date: MessageDay = (
                        MessageDay.select().order_by(MessageDay.date.asc()).get()
                    )
                    jour_debut = oldest_date.date

                jour_fin = MessageDay.select(fn.MAX(MessageDay.date)).scalar()

                # Messages de l'utilisateur dans la période
                query = RawQuery(
                    """
                    SELECT DATE(message.timestamp) as date, COUNT(messageindex.rowid)/CAST (messageday.count AS REAL) as messages
                    FROM messageindex
                    JOIN message ON messageindex.rowid = message.message_id
                    JOIN messageday ON DATE(message.timestamp)=messageday.date
                    WHERE messageindex MATCH ?
                    AND DATE(message.timestamp) >= ?
                    AND DATE(message.timestamp) <= ?
                    GROUP BY DATE(message.timestamp)
                    ORDER BY DATE(message.timestamp);""",
                    params=([terme_fts, jour_debut, jour_fin]),
                )

                # Exécution requête SQL
                logging.info("Executing database request...")
                query_sql, query_params = query.sql()
                df = pandas.read_sql_query(
                    query_sql, db.connection(), params=query_params
                )
                logging.info("Database request answered.")

        logging.info("Processing data and creating graph...")

        # Remplir les dates manquantes
        idx = pandas.date_range(jour_debut, jour_fin)
        df = df.set_index("date")
        df.index = pandas.DatetimeIndex(df.index)
        df = df.reindex(idx, fill_value=0)

        # Rolling average
        df["messages"] = df.rolling(ROLLING_AVERAGE).mean()

        # Remove NaN values
        df = df.dropna()

        # Si emote custom : simplifier le nom pour titre DW
        custom_emoji_str = emoji_to_str(terme)
        if custom_emoji_str:
            terme = custom_emoji_str

        title_lines = textwrap.wrap(f"Tendances de <b>'{terme}'</b>")
        title_lines.append(f"<i style='font-size: 10px'>Sur {guild_name}.</i>")
        title = "<br>".join(title_lines)
        fig: go.Figure = px.area(
            df,
            # x="date",
            y="messages",
            color_discrete_sequence=["yellow"],
            # line_shape="spline",
            template="plotly_dark",
            title=title,
            labels={"index": "", "messages": ""},
        )
        logging.info("Data processed and graph created. Exporting to image...")

        img = fig.to_image(format="png", scale=2)

        # Envoyer image
        logging.info("Sending image to client...")
        await interaction.followup.send(
            file=discord.File(io.BytesIO(img), "abeille.png"),
        )
        logging.info("Image sent to client.")

    @app_commands.command(
        name="compare", description="Comparer la tendance de deux expressions."
    )
    @app_commands.describe(
        expression1="Saisissez un mot ou une phrase.",
        expression2="Saisissez un mot ou une phrase.",
        periode="Période de temps max sur laquelle dessiner la tendance.",
    )
    @app_commands.choices(
        periode=[
            Choice(name="6 mois", value=182),
            Choice(name="1 an", value=365),
            Choice(name="2 ans", value=730),
            Choice(name="3 ans", value=1096),
            Choice(name="Depuis le début", value=9999),
        ]
    )
    @app_commands.guild_only()
    async def compare_slash(
        self,
        interaction: discord.Interaction,
        expression1: str,
        expression2: str,
        periode: Choice[int],
    ):
        await interaction.response.defer(thinking=True)
        guild_id = interaction.guild_id

        if not guild_id:
            await interaction.followup.send("Can't find guild id.")
            return

        # FTS5 : can't tokenize expressions with less than 3 characters
        if (len(expression1) < 3) or (len(expression2) < 3):
            await interaction.followup.send(
                "Je ne peux pas traiter les expressions de moins de 3 caractères. 🐝"
            )
            return

        # FTS5 : enclose in double quotes
        expression1_fts = f'"{expression1}"'
        expression2_fts = f'"{expression2}"'

        jour_debut = date.today() - timedelta(days=periode.value)
        jour_fin = None
        tracking_cog = get_tracking_cog(self.bot)
        db = tracking_cog.tracked_guilds[guild_id]
        guild_name = self.bot.get_guild(guild_id)

        with db:
            with db.bind_ctx([Message, MessageIndex, MessageDay]):

                if periode.value == 9999:
                    oldest_date: MessageDay = (
                        MessageDay.select().order_by(MessageDay.date.asc()).get()
                    )
                    jour_debut = oldest_date.date

                jour_fin = MessageDay.select(fn.MAX(MessageDay.date)).scalar()

                # Messages de l'utilisateur dans la période
                query1_str = """
                    SELECT DATE(message.timestamp) as date, COUNT(messageindex.rowid)/CAST (messageday.count AS REAL) as expression1
                    FROM messageindex
                    JOIN message ON messageindex.rowid = message.message_id
                    JOIN messageday ON DATE(message.timestamp)=messageday.date
                    WHERE messageindex MATCH ?
                    AND DATE(message.timestamp) >= ?
                    AND DATE(message.timestamp) <= ?
                    GROUP BY DATE(message.timestamp)
                    ORDER BY DATE(message.timestamp);"""
                query1 = RawQuery(
                    query1_str,
                    params=([expression1_fts, jour_debut, jour_fin]),
                )
                query2_str = """
                    SELECT DATE(message.timestamp) as date, COUNT(messageindex.rowid)/CAST (messageday.count AS REAL) as expression2
                    FROM messageindex
                    JOIN message ON messageindex.rowid = message.message_id
                    JOIN messageday ON DATE(message.timestamp)=messageday.date
                    WHERE messageindex MATCH ?
                    AND DATE(message.timestamp) >= ?
                    AND DATE(message.timestamp) <= ?
                    GROUP BY DATE(message.timestamp)
                    ORDER BY DATE(message.timestamp);"""
                query2 = RawQuery(
                    query2_str,
                    params=([expression2_fts, jour_debut, jour_fin]),
                )

                # Query 1
                logging.info("Executing database request...")
                query_sql, query_params = query1.sql()
                df1 = pandas.read_sql_query(
                    query_sql, db.connection(), params=query_params
                )
                logging.info("Database request answered.")

                # Query 2
                logging.info("Executing database request...")
                query_sql, query_params = query2.sql()
                df2 = pandas.read_sql_query(
                    query_sql, db.connection(), params=query_params
                )
                logging.info("Database request answered.")

        # Si emote custom : simplifier le nom pour titre DW
        custom_emoji_str = emoji_to_str(expression1)
        if custom_emoji_str:
            expression1 = custom_emoji_str
        custom_emoji_str = emoji_to_str(expression2)
        if custom_emoji_str:
            expression2 = custom_emoji_str

        # Remplir les dates manquantes
        idx = pandas.date_range(jour_debut, jour_fin)
        df1 = df1.set_index("date")
        df1.index = pandas.DatetimeIndex(df1.index)
        df1 = df1.reindex(idx, fill_value=0)
        df2 = df2.set_index("date")
        df2.index = pandas.DatetimeIndex(df2.index)
        df2 = df2.reindex(idx, fill_value=0)

        df = pandas.concat([df1, df2], axis=1)

        # Rolling average
        df["expression1"] = df.get("expression1").rolling(ROLLING_AVERAGE).mean()
        df["expression2"] = df.get("expression2").rolling(ROLLING_AVERAGE).mean()

        # Remove NaN values
        df = df.dropna()

        # Rename columns
        df = df.rename(columns={"expression1": expression1, "expression2": expression2})

        title_lines = textwrap.wrap(f"<b>'{expression1}'</b> vs <b>'{expression2}'</b>")
        title_lines.append(f"<i style='font-size: 10px'>Sur {guild_name}.</i>")
        title = "<br>".join(title_lines)
        fig: go.Figure = px.line(
            df,
            y=[expression1, expression2],
            color_discrete_sequence=["yellow", "#4585e6"],
            template="plotly_dark",
            title=title,
            render_mode="svg",
            labels={"date": "", "variable": ""},
        )

        # Hide y-axis
        fig.update_yaxes(visible=False, fixedrange=True)

        # Legend position
        fig.update_layout(
            legend=dict(
                title=None,
                orientation="h",
                y=1,
                yanchor="bottom",
                x=0.5,
                xanchor="center",
            )
        )

        img = fig.to_image(format="png", scale=2)

        # Envoyer image
        await interaction.followup.send(
            file=discord.File(io.BytesIO(img), "abeille.png"),
        )

    @app_commands.command(
        name="rank", description="Votre classement dans l'utilisation d'une expression."
    )
    @app_commands.describe(
        expression="Saisissez un mot ou une phrase.",
    )
    @app_commands.guild_only()
    async def rank_slash(self, interaction: discord.Interaction, expression: str):
        await interaction.response.defer(thinking=True)
        expression = expression.strip()

        # FTS5 : can't tokenize expressions with less than 3 characters
        if len(expression) < 3:
            await interaction.followup.send(
                "Je ne peux pas traiter les expressions de moins de 3 caractères. 🐝"
            )
            return

        # FTS5 : enclose in double quotes
        expression_fts = f'"{expression}"'

        author = interaction.user
        author_id = hashlib.pbkdf2_hmac(
            hash_name, str(author.id).encode(), salt, iterations
        ).hex()
        guild_id = interaction.guild_id
        if not guild_id:
            await interaction.followup.send("Can't find guild id.")
            return

        tracking_cog = get_tracking_cog(self.bot)
        db = tracking_cog.tracked_guilds[guild_id]

        with db:
            with db.bind_ctx([Message, MessageIndex]):
                rank_query = fn.rank().over(
                    order_by=[fn.COUNT(Message.message_id).desc()]
                )

                subq = (
                    Message.select(Message.author_id, rank_query.alias("rank"))
                    .join(MessageIndex, on=(Message.message_id == MessageIndex.rowid))
                    .where(MessageIndex.match(expression_fts))
                    .group_by(Message.author_id)
                )

                # Here we use a plain Select() to create our query.
                query = (
                    Select(columns=[subq.c.rank])
                    .from_(subq)
                    .where(subq.c.author_id == author_id)
                    .bind(db)
                )  # We must bind() it to the database.

                rank = query.scalar()

        if rank is None:
            result = f"Vous n'avez jamais employé l'expression *{expression}*."
        elif rank == 1:
            result = f"🥇 Vous êtes le membre ayant le plus employé l'expression *{expression}*."
        elif rank == 2:
            result = f"🥈 Vous êtes le 2ème membre à avoir le plus employé l'expression *{expression}*."
        elif rank == 3:
            result = f"🥉 Vous êtes le 3ème membre à avoir le plus employé l'expression *{expression}*."
        else:
            result = f"Vous êtes le **{rank}ème** membre à avoir le plus employé l'expression *{expression}*."

        await interaction.followup.send(result)

    async def cog_command_error(self, ctx: commands.Context, error):
        if isinstance(error, Maintenance):
            await ctx.send(
                "Cette fonctionnalité est en maintenance et sera de retour très bientôt ! 🐝"
            )
        elif isinstance(
            error, (commands.BadArgument, commands.MissingRequiredArgument)
        ):
            await ctx.send("Vous avez mal utilisé la commande ! 🐝")
        else:
            await ctx.send(f"Quelque chose s'est mal passée ({error}). 🐝")


async def setup(bot):
    await bot.add_cog(Activity(bot))
