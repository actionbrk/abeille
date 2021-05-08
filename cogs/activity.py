""" Commandes de tendances """

import io
import os
import textwrap
from datetime import date, timedelta
from typing import Any, Dict

import discord
import pandas
import plotly.express as px
import plotly.graph_objects as go
from datawrapper import Datawrapper
from discord.ext import commands
from dotenv import load_dotenv
from peewee import fn

from cogs.tracking import get_tracking_cog
from common.checks import Maintenance
from common.utils import emoji_to_str, str_input_ok
from models.message import Message
from discord_slash import cog_ext, SlashContext
from discord_slash.utils.manage_commands import create_option, create_choice
from cogs.misc import guild_ids

PERIODE = 1100
ROLLING_AVERAGE = 14

# Chargement .env
load_dotenv()
token = os.getenv("DW_TOKEN")
salt = os.getenv("SALT").encode()  # type:ignore
iterations = int(os.getenv("ITER"))  # type:ignore
hash_name: str = os.getenv("HASHNAME")  # type:ignore


class Activity(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.dw = Datawrapper(access_token=token)  # pylint: disable=invalid-name

    @commands.command(name="vsdw", aliases=["comparedw"])
    @commands.max_concurrency(1, wait=True)
    @commands.guild_only()
    async def comparedw(self, ctx: commands.Context, terme1: str, terme2: str):
        """Compare trends with Datawrapper"""
        assert ctx.guild is not None, "Impossible de récupérer la guild"
        await self._comparedw(ctx, ctx.guild.id, terme1, terme2)

    @commands.command(name="vsdwid", aliases=["comparedwid"])
    @commands.max_concurrency(1, wait=True)
    @commands.guild_only()
    @commands.is_owner()
    async def comparedw_id(
        self, ctx: commands.Context, guild_id: int, terme1: str, terme2: str
    ):
        """Compare deux tendances"""
        await self._compare(ctx, guild_id, terme1, terme2)

    async def _comparedw(
        self, ctx: commands.Context, guild_id: int, terme1: str, terme2: str
    ):
        """Compare deux tendances"""
        if False in (str_input_ok(terme1), str_input_ok(terme2)):
            await ctx.send("Je ne peux pas faire de tendance avec une expression vide.")
            return

        # Si les deux mêmes, faire un _trend
        if terme1 == terme2:
            return await self._trenddw(ctx, guild_id, terme1)

        temp_msg: discord.Message = await ctx.send(
            f"Je génère les tendances comparées de **{terme1}** et **{terme2}**... 🐝"
        )

        jour_debut = date.today() - timedelta(days=PERIODE)
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
                            fn.SUM(Message.content.contains(terme1))
                            / fn.COUNT(Message.message_id)
                        ).alias("terme1"),
                        (
                            fn.SUM(Message.content.contains(terme2))
                            / fn.COUNT(Message.message_id)
                        ).alias("terme2"),
                    )
                    .where(fn.DATE(Message.timestamp) >= jour_debut)
                    .where(fn.DATE(Message.timestamp) <= jour_fin)
                    .group_by(fn.DATE(Message.timestamp))
                )

                cur = db.cursor()
                query_sql = cur.mogrify(*query.sql())
                msg_par_jour = pandas.read_sql(query_sql, db.connection())

        # Si emote custom : simplifier le nom pour titre DW
        custom_emoji_str = emoji_to_str(terme1)
        if custom_emoji_str:
            terme1 = custom_emoji_str
        custom_emoji_str = emoji_to_str(terme2)
        if custom_emoji_str:
            terme2 = custom_emoji_str

        # Renommage des colonnes
        msg_par_jour = msg_par_jour.rename(columns={"terme1": terme1, "terme2": terme2})

        # Remplir les dates manquantes
        msg_par_jour = msg_par_jour.set_index("date")
        msg_par_jour.index = pandas.DatetimeIndex(msg_par_jour.index)
        msg_par_jour.reset_index(level=0, inplace=True)
        msg_par_jour = msg_par_jour.rename(columns={"index": "date"})

        # Rolling average
        msg_par_jour[terme1] = msg_par_jour.get(terme1).rolling(ROLLING_AVERAGE).mean()
        msg_par_jour[terme2] = msg_par_jour.get(terme2).rolling(ROLLING_AVERAGE).mean()

        properties = {
            "annotate": {
                "notes": f"Moyenne mobile sur les {ROLLING_AVERAGE} derniers jours. Insensible à la casse et aux accents."
            },
            "visualize": {
                "labeling": "top",
                "base-color": "#DFC833",
                "line-widths": {terme1: 1, terme2: 1},
                "custom-colors": {terme1: "#DFC833", terme2: 0},
                "y-grid": "off",
            },
        }

        # Send chart
        await self.__send_chart(
            ctx,
            f"'{terme1}' vs '{terme2}'",
            f"Tendances dans les messages postés sur {guild_name}",
            "d3-lines",
            msg_par_jour,
            properties,
        )

        await temp_msg.delete()

    @commands.command(name="trenddw")
    @commands.max_concurrency(1, wait=True)
    @commands.guild_only()
    async def trenddw(self, ctx: commands.Context, *, terme: str):
        assert ctx.guild is not None, "Impossible de récupérer la guild"
        await self._trenddw(ctx, ctx.guild.id, terme)

    @commands.command(name="trenddwid")
    @commands.max_concurrency(1, wait=True)
    @commands.guild_only()
    @commands.is_owner()
    async def trenddw_debug(self, ctx: commands.Context, guild_id: int, *, terme: str):
        await self._trenddw(ctx, guild_id, terme)

    async def _trenddw(self, ctx: commands.Context, guild_id: int, terme: str):
        """Trend using Datawrapper"""
        if not str_input_ok(terme):
            await ctx.send("Je ne peux pas faire de tendance avec une expression vide.")
            return

        temp_msg: discord.Message = await ctx.send(
            f"Je génère les tendances de **{terme}**... 🐝"
        )

        jour_debut = date.today() - timedelta(days=PERIODE)
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
                            fn.SUM(Message.content.contains(terme))
                            / fn.COUNT(Message.message_id)
                        ).alias("messages"),
                    )
                    .where(fn.DATE(Message.timestamp) >= jour_debut)
                    .where(fn.DATE(Message.timestamp) <= jour_fin)
                    .group_by(fn.DATE(Message.timestamp))
                )

                # Exécution requête SQL
                cur = db.cursor()
                query_sql = cur.mogrify(*query.sql())
                msg_par_jour = pandas.read_sql(query_sql, db.connection())

        # Remplir les dates manquantes
        msg_par_jour = msg_par_jour.set_index("date")
        msg_par_jour.index = pandas.DatetimeIndex(msg_par_jour.index)
        msg_par_jour.reset_index(level=0, inplace=True)
        msg_par_jour = msg_par_jour.rename(columns={"index": "date"})

        # Rolling average
        msg_par_jour["messages"] = msg_par_jour.rolling(ROLLING_AVERAGE).mean()

        properties = {
            "annotate": {
                "notes": f"Moyenne mobile sur les {ROLLING_AVERAGE} derniers jours. Insensible à la casse et aux accents."
            },
            "visualize": {
                "base-color": "#DFC833",
                "fill-below": True,
                "labeling": "off",
                "line-widths": {"messages": 1},
                "y-grid": "off",
            },
        }

        # Si emote custom : simplifier le nom pour titre DW
        custom_emoji_str = emoji_to_str(terme)
        if custom_emoji_str:
            terme = custom_emoji_str

        # Send chart
        await self.__send_chart(
            ctx,
            f"Tendances pour '{terme}'",
            f"Dans les messages postés sur {guild_name}",
            "d3-lines",
            msg_par_jour,
            properties,
        )

        await temp_msg.delete()

    async def __send_chart(
        self,
        ctx,
        title: str,
        intro: str,
        chart_type: str,
        data: Any,
        properties: Dict[str, Any],
    ) -> None:
        """Create, send and delete chart"""
        chart_id = await self._generate_chart(
            title, intro, chart_type, data, properties
        )

        # Envoyer image
        filepath = f"/tmp/{chart_id}.png"
        self.dw.export_chart(chart_id, filepath=filepath)

        await ctx.send(file=discord.File(filepath, "abeille.png"))

        # Suppression de DW et du disque
        self.dw.delete_chart(chart_id=chart_id)
        os.remove(filepath)

    async def _generate_chart(
        self,
        title: str,
        intro: str,
        chart_type: str,
        data: Any,
        properties: Dict[str, Any],
    ) -> str:
        new_chart_info = self.dw.create_chart(
            title=title, chart_type=chart_type, data=data
        )
        chart_id = new_chart_info["id"]
        # Update
        self.dw.update_chart(chart_id, language="fr-FR", theme="pageflow")
        self.dw.update_description(
            chart_id,
            byline="Abeille, plus d'informations sur kutt.it/Abeille",
            intro=intro,
        )
        self.dw.update_metadata(chart_id, properties)

        return chart_id

    @cog_ext.cog_slash(
        name="trend",
        description="Dessiner la tendance d'une expression.",
        guild_ids=guild_ids,
        options=[
            create_option(
                name="terme",
                description="Saisissez un mot ou une phrase.",
                option_type=3,
                required=True,
            ),
            create_option(
                name="periode",
                description="Période de temps max sur laquelle dessiner la tendance.",
                option_type=3,
                required=True,
                choices=[
                    create_choice(name="6 mois", value="182"),
                    create_choice(name="1 an", value="365"),
                    create_choice(name="2 ans", value="730"),
                    create_choice(name="3 ans", value="1096"),
                ],
            ),
        ],
    )
    async def trend_slash(self, ctx: SlashContext, terme: str, periode: str):
        await ctx.defer()
        guild_id = ctx.guild.id
        jour_debut = date.today() - timedelta(days=int(periode))
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
                            fn.SUM(Message.content.contains(terme))
                            / fn.COUNT(Message.message_id)
                        ).alias("messages"),
                    )
                    .where(fn.DATE(Message.timestamp) >= jour_debut)
                    .where(fn.DATE(Message.timestamp) <= jour_fin)
                    .group_by(fn.DATE(Message.timestamp))
                )

                # Exécution requête SQL
                cur = db.cursor()
                query_sql = cur.mogrify(*query.sql())
                df = pandas.read_sql(query_sql, db.connection())

        # Remplir les dates manquantes
        df = df.set_index("date")
        df.index = pandas.DatetimeIndex(df.index)
        df.reset_index(level=0, inplace=True)
        df = df.rename(columns={"index": "date"})

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
            x="date",
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

        img = fig.to_image(format="png", scale=2)

        # Envoyer image
        await ctx.send(file=discord.File(io.BytesIO(img), "abeille.png"))

    @commands.command(name="trend", aliases=["trendbeta"])
    @commands.max_concurrency(1, wait=True)
    @commands.guild_only()
    async def trend(self, ctx: commands.Context, *, terme: str):
        assert ctx.guild is not None, "Impossible de récupérer la guild"
        await ctx.reply("Utilisez la nouvelle commande slash ! `/trend` 🐝")

    @commands.command(name="trendid")
    @commands.max_concurrency(1, wait=True)
    @commands.guild_only()
    @commands.is_owner()
    async def trend_id(self, ctx: commands.Context, guild_id: int, *, terme: str):
        await self._trend(ctx, guild_id, terme)

    async def _trend(self, ctx: commands.Context, guild_id: int, terme: str):
        """Trending last X days"""
        assert isinstance(
            ctx.author, discord.Member
        ), "Avez-vous exécuté la commande depuis un salon ?"

        if not str_input_ok(terme):
            await ctx.reply(
                "Je ne peux pas faire de tendance avec une expression vide."
            )
            return

        temp_msg: discord.Message = await ctx.reply(
            f"Je génère les tendances de **{terme}**... 🐝"
        )

        async with ctx.typing():
            jour_debut = date.today() - timedelta(days=PERIODE)
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
                                fn.SUM(Message.content.contains(terme))
                                / fn.COUNT(Message.message_id)
                            ).alias("messages"),
                        )
                        .where(fn.DATE(Message.timestamp) >= jour_debut)
                        .where(fn.DATE(Message.timestamp) <= jour_fin)
                        .group_by(fn.DATE(Message.timestamp))
                    )

                    # Exécution requête SQL
                    cur = db.cursor()
                    query_sql = cur.mogrify(*query.sql())
                    df = pandas.read_sql(query_sql, db.connection())

            # Remplir les dates manquantes
            df = df.set_index("date")
            df.index = pandas.DatetimeIndex(df.index)
            df.reset_index(level=0, inplace=True)
            df = df.rename(columns={"index": "date"})

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
                x="date",
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

            img = fig.to_image(format="png", scale=2)

            # Envoyer image
            await temp_msg.delete()
            await ctx.reply(file=discord.File(io.BytesIO(img), "abeille.png"))

    @commands.command(name="vs")
    @commands.max_concurrency(1, wait=True)
    @commands.guild_only()
    async def compare(self, ctx: commands.Context, terme1: str, terme2: str):
        """Compare deux tendances"""
        assert ctx.guild is not None, "Impossible de récupérer la guild"
        await self._compare(ctx, ctx.guild.id, terme1, terme2)

    @commands.command(name="vsid")
    @commands.max_concurrency(1, wait=True)
    @commands.guild_only()
    @commands.is_owner()
    async def compare_id(
        self, ctx: commands.Context, guild_id: int, terme1: str, terme2: str
    ):
        """Compare deux tendances"""
        await self._compare(ctx, guild_id, terme1, terme2)

    async def _compare(
        self, ctx: commands.Context, guild_id: int, terme1: str, terme2: str
    ):
        """Trend comparison"""
        assert isinstance(
            ctx.author, discord.Member
        ), "Avez-vous exécuté la commande depuis un salon ?"

        if False in (str_input_ok(terme1), str_input_ok(terme2)):
            await ctx.send("Je ne peux pas faire de tendance avec une expression vide.")
            return

        # Si les deux mêmes, faire un _trend
        if terme1 == terme2:
            return await self._trend(ctx, guild_id, terme1)

        temp_msg: discord.Message = await ctx.send(
            f"Je génère les tendances comparées de **{terme1}** et **{terme2}**... 🐝"
        )

        async with ctx.typing():
            jour_debut = date.today() - timedelta(days=PERIODE)
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
                                fn.SUM(Message.content.contains(terme1))
                                / fn.COUNT(Message.message_id)
                            ).alias("terme1"),
                            (
                                fn.SUM(Message.content.contains(terme2))
                                / fn.COUNT(Message.message_id)
                            ).alias("terme2"),
                        )
                        .where(fn.DATE(Message.timestamp) >= jour_debut)
                        .where(fn.DATE(Message.timestamp) <= jour_fin)
                        .group_by(fn.DATE(Message.timestamp))
                    )

                    cur = db.cursor()
                    query_sql = cur.mogrify(*query.sql())
                    df = pandas.read_sql(query_sql, db.connection())

            # Si emote custom : simplifier le nom pour titre DW
            custom_emoji_str = emoji_to_str(terme1)
            if custom_emoji_str:
                terme1 = custom_emoji_str
            custom_emoji_str = emoji_to_str(terme2)
            if custom_emoji_str:
                terme2 = custom_emoji_str

            # Renommage des colonnes
            df = df.rename(columns={"terme1": terme1, "terme2": terme2})

            # Remplir les dates manquantes
            df = df.set_index("date")
            df.index = pandas.DatetimeIndex(df.index)
            df.reset_index(level=0, inplace=True)
            df = df.rename(columns={"index": "date"})

            # Rolling average
            df[terme1] = df.get(terme1).rolling(ROLLING_AVERAGE).mean()
            df[terme2] = df.get(terme2).rolling(ROLLING_AVERAGE).mean()

            title_lines = textwrap.wrap(f"<b>'{terme1}'</b> vs <b>'{terme2}'</b>")
            title_lines.append(f"<i style='font-size: 10px'>Sur {guild_name}.</i>")
            title = "<br>".join(title_lines)
            fig: go.Figure = px.line(
                df,
                x="date",
                y=[terme1, terme2],
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

            img = fig.to_image(format="png", scale=2)

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


def setup(bot):
    bot.add_cog(Activity(bot))
