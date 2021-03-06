""" Commandes de tendances """

import hashlib
import io
import logging
import os
import textwrap
from datetime import date, timedelta
from typing import Any

import discord
import pandas
import plotly.express as px
import plotly.graph_objects as go
from common.checks import Maintenance
from common.utils import emoji_to_str
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands
from dotenv import load_dotenv
from models.message import Message, MessageIndex
from peewee import SQL, Query, Select, fn

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

    async def _get_trend_img(self, guild_id: int, terme: str, periode: int) -> Any:
        jour_debut = date.today() - timedelta(days=periode)
        jour_fin = date.today() - timedelta(days=1)
        tracking_cog = get_tracking_cog(self.bot)
        db = tracking_cog.tracked_guilds[guild_id]
        guild_name = self.bot.get_guild(guild_id)

        with db:
            with db.bind_ctx([Message, MessageIndex]):
                # subq: Query = MessageIndex.select(MessageIndex.rowid).where(
                #     MessageIndex.match(terme)
                # )

                # Messages de l'utilisateur dans la période
                query: Query = (
                    Message.select(
                        fn.DATE(Message.timestamp).alias("date"),
                        (
                            fn.SUM(Message.content.contains(terme))
                            / fn.COUNT(Message.message_id).cast("REAL")
                        ).alias("messages"),
                    )
                    .where(fn.DATE(Message.timestamp) >= jour_debut)
                    .where(fn.DATE(Message.timestamp) <= jour_fin)
                    .group_by(fn.DATE(Message.timestamp))
                )

                # TODO: MATCH -> another slash command
                # query: Query = (
                #     Message.select(
                #         fn.DATE(Message.timestamp).alias("date"),
                #         (
                #             fn.SUM(
                #                 Message.message_id.in_(
                #                     SQL(
                #                         "(SELECT messageindex.rowid from messageindex where messageindex match ?)",
                #                         [terme],
                #                     )
                #                 )
                #             )
                #             / fn.COUNT(Message.message_id).cast("REAL")
                #         ).alias("messages"),
                #     )
                #     .where(fn.DATE(Message.timestamp) >= jour_debut)
                #     .where(fn.DATE(Message.timestamp) <= jour_fin)
                #     .group_by(fn.DATE(Message.timestamp))
                # )

                # Alternative SQL brut (manque filtrage date)
                # query = RawQuery(
                #     "SELECT DATE(message.timestamp) AS date, sum(message.message_id in (select messageindex.rowid from messageindex where messageindex match ?))/CAST(COUNT(message.message_id) as real) as messages from message group by DATE(message.timestamp);",
                #     params=([terme]),
                # )

                # Exécution requête SQL
                # cur = db.cursor()
                # query_sql = cur.mogrify(*query.sql())

                logging.info("Executing database request...")
                query_sql, query_params = query.sql()
                df = pandas.read_sql_query(
                    query_sql, db.connection(), params=query_params
                )
                logging.info("Database request answered.")

        logging.info("Processing data and creating graph...")
        # Remplir les dates manquantes
        df = df.set_index("date")
        df.index = pandas.DatetimeIndex(df.index)
        # df = df.asfreq("D", fill_value=0)

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
            labels={"date": "", "messages": ""},
        )
        logging.info("Data processed and graph created. Exporting to image...")

        return fig.to_image(format="png", scale=2)

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

        img = await self._get_trend_img(guild_id, terme, periode.value)

        # Envoyer image
        logging.info("Sending image to client...")
        await interaction.followup.send(
            file=discord.File(io.BytesIO(img), "abeille.png"),
        )
        logging.info("Image sent to client.")

    @commands.command(name="trendid")
    @commands.max_concurrency(1, wait=True)
    @commands.guild_only()
    @commands.is_owner()
    async def trend_id(self, ctx: commands.Context, guild_id: int, *, terme: str):
        temp_msg: discord.Message = await ctx.reply(
            f"Je génère les tendances de **{terme}**... 🐝"
        )

        async with ctx.typing():
            img = await self._get_trend_img(guild_id, terme, PERIODE)

            # Envoyer image
            await temp_msg.delete()
            await ctx.reply(file=discord.File(io.BytesIO(img), "abeille.png"))

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

        img = await self._get_compare_img(
            guild_id, expression1, expression2, periode.value
        )

        # Envoyer image
        await interaction.followup.send(
            file=discord.File(io.BytesIO(img), "abeille.png"),
        )

    async def _get_compare_img(
        self, guild_id: int, expression1: str, expression2: str, periode: int
    ) -> Any:
        jour_debut = date.today() - timedelta(days=periode)
        jour_fin = date.today() - timedelta(days=1)
        tracking_cog = get_tracking_cog(self.bot)
        db = tracking_cog.tracked_guilds[guild_id]
        guild_name = self.bot.get_guild(guild_id)

        with db:
            with db.bind_ctx([Message]):
                # Messages de l'utilisateur dans la période
                query = (
                    Message.select(
                        fn.DATE(Message.timestamp).alias("date"),
                        (
                            fn.SUM(Message.content.contains(expression1))
                            / fn.COUNT(Message.message_id).cast("REAL")
                        ).alias("expression1"),
                        (
                            fn.SUM(Message.content.contains(expression2))
                            / fn.COUNT(Message.message_id).cast("REAL")
                        ).alias("expression2"),
                    )
                    .where(fn.DATE(Message.timestamp) >= jour_debut)
                    .where(fn.DATE(Message.timestamp) <= jour_fin)
                    .group_by(fn.DATE(Message.timestamp))
                )

                logging.info("Executing database request...")
                query_sql, query_params = query.sql()
                df = pandas.read_sql_query(
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

        # Renommage des colonnes
        df = df.rename(columns={"expression1": expression1, "expression2": expression2})

        # Remplir les dates manquantes
        df = df.set_index("date")
        df.index = pandas.DatetimeIndex(df.index)

        # Rolling average
        df[expression1] = df.get(expression1).rolling(ROLLING_AVERAGE).mean()
        df[expression2] = df.get(expression2).rolling(ROLLING_AVERAGE).mean()

        # Remove NaN values
        df = df.dropna()

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

        return fig.to_image(format="png", scale=2)

    @commands.command(name="vsid")
    @commands.max_concurrency(1, wait=True)
    @commands.guild_only()
    @commands.is_owner()
    async def compare_id(
        self, ctx: commands.Context, guild_id: int, terme1: str, terme2: str
    ):
        temp_msg: discord.Message = await ctx.send(
            f"Je génère les tendances comparées de **{terme1}** et **{terme2}**... 🐝"
        )

        async with ctx.typing():
            img = await self._get_compare_img(guild_id, terme1, terme2, PERIODE)

            # Envoyer image
            await temp_msg.delete()
            await ctx.reply(file=discord.File(io.BytesIO(img), "abeille.png"))

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
            with db.bind_ctx([Message]):
                rank_query = fn.rank().over(
                    order_by=[fn.COUNT(Message.message_id).desc()]
                )

                subq = (
                    Message.select(Message.author_id, rank_query.alias("rank"))
                    .where(Message.content.contains(expression))
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


async def setup(bot):
    await bot.add_cog(Activity(bot))
