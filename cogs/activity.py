""" Commandes de tendances """

import hashlib
import io
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
from discord.ext import commands
from dotenv import load_dotenv
from models.message import Message, MessageIndex
from peewee import SQL, Query, Select, fn

from cogs.tracking import get_tracking_cog

PERIODE = 1100
ROLLING_AVERAGE = 14

# Chargement .env
load_dotenv()
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
                            fn.SUM(
                                Message.message_id.in_(
                                    SQL(
                                        "(SELECT messageindex.rowid from messageindex where messageindex match ?)",
                                        [terme],
                                    )
                                )
                            )
                            / fn.COUNT(Message.message_id).cast("REAL")
                        ).alias("messages"),
                    )
                    .where(fn.DATE(Message.timestamp) >= jour_debut)
                    .where(fn.DATE(Message.timestamp) <= jour_fin)
                    .group_by(fn.DATE(Message.timestamp))
                )

                # Alternative SQL brut (manque filtrage date)
                # query = RawQuery(
                #     "SELECT DATE(message.timestamp) AS date, sum(message.message_id in (select messageindex.rowid from messageindex where messageindex match ?))/CAST(COUNT(message.message_id) as real) as messages from message group by DATE(message.timestamp);",
                #     params=([terme]),
                # )

                # Exécution requête SQL
                # cur = db.cursor()
                # query_sql = cur.mogrify(*query.sql())
                query_sql, query_params = query.sql()
                df = pandas.read_sql_query(
                    query_sql, db.connection(), params=query_params
                )

        # Remplir les dates manquantes
        df = df.set_index("date")
        df.index = pandas.DatetimeIndex(df.index)
        df = df.asfreq("D", fill_value=0)

        # Rolling average
        df["messages"] = df.rolling(ROLLING_AVERAGE).mean()

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
        fig.add_layout_image(
            dict(
                source="https://i.imgur.com/Eqy58rg.png",
                xref="paper",
                yref="paper",
                x=1.1,
                y=-0.22,
                sizex=0.25,
                sizey=0.25,
                xanchor="right",
                yanchor="bottom",
                opacity=0.8,
            )
        )

        return fig.to_image(format="png", scale=2)

    # @cog_ext.cog_slash(
    #     name="trend",
    #     description="Dessiner la tendance d'une expression.",
    #     guild_ids=TRACKED_GUILD_IDS,
    #     options=[
    #         create_option(
    #             name="terme",
    #             description="Saisissez un mot ou une phrase.",
    #             option_type=3,
    #             required=True,
    #         ),
    #         create_option(
    #             name="periode",
    #             description="Période de temps max sur laquelle dessiner la tendance.",
    #             option_type=4,
    #             required=True,
    #             choices=[
    #                 create_choice(name="6 mois", value=182),
    #                 create_choice(name="1 an", value=365),
    #                 create_choice(name="2 ans", value=730),
    #                 create_choice(name="3 ans", value=1096),
    #             ],
    #         ),
    #     ],
    # )
    @app_commands.command(name="trend", description="test")
    @app_commands.describe(
        terme="The first value you want to add something to",
        periode="The value you want to add to the first value",
    )
    async def trend_slash(
        self, interaction: discord.Interaction, terme: str, periode: int
    ):
        await interaction.response.defer()
        guild_id = interaction.guild_id

        if not guild_id:
            await interaction.response.send_message("Can't find guild id.")
            return

        img = await self._get_trend_img(guild_id, terme, periode)

        # Envoyer image
        await interaction.response.send_message(
            file=discord.File(io.BytesIO(img), "abeille.png")
        )

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

    # @cog_ext.cog_slash(
    #     name="compare",
    #     description="Comparer la tendance de deux expressions.",
    #     guild_ids=TRACKED_GUILD_IDS,
    #     options=[
    #         create_option(
    #             name="expression1",
    #             description="Saisissez un mot ou une phrase.",
    #             option_type=3,
    #             required=True,
    #         ),
    #         create_option(
    #             name="expression2",
    #             description="Saisissez un mot ou une phrase.",
    #             option_type=3,
    #             required=True,
    #         ),
    #         create_option(
    #             name="periode",
    #             description="Période de temps max sur laquelle dessiner la tendance.",
    #             option_type=4,
    #             required=True,
    #             choices=[
    #                 create_choice(name="6 mois", value=182),
    #                 create_choice(name="1 an", value=365),
    #                 create_choice(name="2 ans", value=730),
    #                 create_choice(name="3 ans", value=1096),
    #             ],
    #         ),
    #     ],
    # )
    @app_commands.command(name="compare", description="test")
    @app_commands.describe(
        expression1="The first value you want to add something to",
        expression2="The value you want to add to the first value",
        periode="Période",
    )
    async def compare_slash(
        self,
        interaction: discord.Interaction,
        expression1: str,
        expression2: str,
        periode: int,
    ):
        await interaction.response.defer()
        guild_id = interaction.guild_id

        if not guild_id:
            await interaction.response.send_message("Can't find guild id.")
            return

        img = await self._get_compare_img(guild_id, expression1, expression2, periode)

        # Envoyer image
        await interaction.response.send_message(
            file=discord.File(io.BytesIO(img), "abeille.png")
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
                            / fn.COUNT(Message.message_id)
                        ).alias("expression1"),
                        (
                            fn.SUM(Message.content.contains(expression2))
                            / fn.COUNT(Message.message_id)
                        ).alias("expression2"),
                    )
                    .where(fn.DATE(Message.timestamp) >= jour_debut)
                    .where(fn.DATE(Message.timestamp) <= jour_fin)
                    .group_by(fn.DATE(Message.timestamp))
                )

                cur = db.cursor()
                query_sql = cur.mogrify(*query.sql())
                df = pandas.read_sql(query_sql, db.connection())

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
        df.reset_index(level=0, inplace=True)
        df = df.rename(columns={"index": "date"})

        # Rolling average
        df[expression1] = df.get(expression1).rolling(ROLLING_AVERAGE).mean()
        df[expression2] = df.get(expression2).rolling(ROLLING_AVERAGE).mean()

        title_lines = textwrap.wrap(f"<b>'{expression1}'</b> vs <b>'{expression2}'</b>")
        title_lines.append(f"<i style='font-size: 10px'>Sur {guild_name}.</i>")
        title = "<br>".join(title_lines)
        fig: go.Figure = px.line(
            df,
            x="date",
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

        fig.add_layout_image(
            dict(
                source="https://i.imgur.com/Eqy58rg.png",
                xref="paper",
                yref="paper",
                x=1.1,
                y=-0.22,
                sizex=0.25,
                sizey=0.25,
                xanchor="right",
                yanchor="bottom",
                opacity=0.8,
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

    # @commands.max_concurrency(1, wait=True)
    # @cog_ext.cog_slash(
    #     name="rank",
    #     description="Votre classement dans l'utilisation d'une expression.",
    #     guild_ids=TRACKED_GUILD_IDS,
    #     options=[
    #         create_option(
    #             name="expression",
    #             description="Saisissez un mot ou une phrase.",
    #             option_type=3,
    #             required=True,
    #         ),
    #     ],
    # )
    @app_commands.command(name="rank", description="test")
    @app_commands.describe(
        expression="The first value you want to add something to",
    )
    async def rank_slash(self, interaction: discord.Interaction, expression: str):
        await interaction.response.defer()
        expression = expression.strip()
        author = interaction.user
        author_id = hashlib.pbkdf2_hmac(
            hash_name, str(author.id).encode(), salt, iterations
        ).hex()
        guild_id = interaction.guild_id
        if not guild_id:
            await interaction.response.send_message("Can't find guild id.")
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

        await interaction.response.send_message(result)


async def setup(bot):
    await bot.add_cog(Activity(bot))
