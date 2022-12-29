""" Commandes de tendances """

import hashlib
import io
import logging
import os
import textwrap
from datetime import date, timedelta
from typing import Dict, List

import discord
import pandas
import plotly.express as px
import plotly.graph_objects as go
from common.checks import Maintenance
from common.utils import emoji_to_str
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands
from models.identity import Identity
from models.message import Message, MessageDay, MessageIndex
from peewee import RawQuery, Select, fn, DoesNotExist, Database

from cogs.tracking import get_tracked_guild

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
    )
    @app_commands.guild_only()
    async def trend_slash(self, interaction: discord.Interaction, terme: str):

        # FTS5 : can't tokenize expressions with less than 3 characters
        if len(terme) < 3:
            await interaction.followup.send(
                "Je ne peux pas traiter les expressions de moins de 3 caractères. 🐝"
            )
            return

        await TrendView(interaction, self.bot, terme).start()

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
        db = get_tracked_guild(self.bot, guild_id).database
        guild_name = self.bot.get_guild(guild_id)

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
            df1 = pandas.read_sql_query(query_sql, db.connection(), params=query_params)
            logging.info("Database request answered.")

            # Query 2
            logging.info("Executing database request...")
            query_sql, query_params = query2.sql()
            df2 = pandas.read_sql_query(query_sql, db.connection(), params=query_params)
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
            labels={"index": ""},
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
        expression = expression.strip()
        # FTS5 : can't tokenize expressions with less than 3 characters
        if len(expression) < 3:
            await interaction.followup.send(
                "Je ne peux pas traiter les expressions de moins de 3 caractères. 🐝"
            )
            return

        guild_id = interaction.guild_id
        if not guild_id:
            await interaction.followup.send("Can't find guild id.")
            return

        db = get_tracked_guild(self.bot, guild_id).database

        await RankView(guild_id, db, expression, self.bot).start(interaction)

    @app_commands.command(
        name="register",
        description="Autoriser Abeille à stocker votre identifiant utilisateur.",
    )
    @app_commands.guild_only()
    async def register(self, interaction: discord.Interaction):
        """Allow Abeille to display user name"""
        db = get_tracked_guild(self.bot, interaction.guild_id).database

        author_id = hashlib.pbkdf2_hmac(
            hash_name, str(interaction.user.id).encode(), salt, iterations
        ).hex()

        with db.bind_ctx([Identity]):
            try:
                Identity.get_by_id(author_id)
                await interaction.response.send_message(
                    "Vous avez déjà autorisé Abeille à stocker votre identifiant utilisateur. 🐝",
                    ephemeral=True,
                )
            except DoesNotExist:
                identity = Identity(
                    author_id=author_id, real_author_id=interaction.user.id
                )
                identity.save(force_insert=True)
                await interaction.response.send_message(
                    "Abeille stocke votre identifiant utilisateur. Utilisez /unregister pour le supprimer. 🐝",
                    ephemeral=True,
                )

    @app_commands.command(
        name="unregister",
        description="Supprimer votre identifiant utilisateur d'Abeille.",
    )
    @app_commands.guild_only()
    async def unregister(self, interaction: discord.Interaction):
        """Disallow Abeille to display user name"""
        db = get_tracked_guild(self.bot, interaction.guild_id).database

        author_id = hashlib.pbkdf2_hmac(
            hash_name, str(interaction.user.id).encode(), salt, iterations
        ).hex()

        with db.bind_ctx([Identity]):
            try:
                identity = Identity.get_by_id(author_id)
                identity.delete_instance()
                await interaction.response.send_message(
                    "Votre identifiant utilisateur est désormais inconnu d'Abeille. Utilisez /register pour réautoriser. 🐝",
                    ephemeral=True,
                )
            except DoesNotExist:
                identity = Identity(
                    author_id=author_id, real_author_id=interaction.user.id
                )
                identity.save()
                await interaction.response.send_message(
                    "Tout va bien : Abeille ne stocke pas votre identifiant utilisateur. 🐝",
                    ephemeral=True,
                )

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


class RankView(discord.ui.View):
    max_lines = 3

    def __init__(
        self,
        guild_id: int,
        db: Database,
        expression: str,
        bot: commands.Bot,
    ):
        # Timeout has to be strictly lower than 15min=900s (since interaction is dead after this time)
        super().__init__(timeout=720)
        self.guild_id = guild_id
        self.db = db
        self.expression = expression
        self.bot = bot
        self.message: discord.InteractionMessage = None

        # FTS5 : enclose in double quotes
        self.expression_fts = f'"{expression}"'

        self.interaction_user_ranks: Dict[int, int] = dict()

    async def interaction_check(self, interaction: discord.Interaction, /):
        """Allow user to click button once"""
        return interaction.user.id not in self.interaction_user_ranks

    async def on_timeout(self) -> None:
        self.rank_me.disabled = True
        self.rank_me.label = "Expiré"
        await self.message.edit(view=self)

    async def start(self, interaction: discord.Interaction):
        # Send rank for initial interaction user
        await interaction.response.send_message(
            self.get_rank_content(interaction.user),
            view=self,
            allowed_mentions=discord.AllowedMentions(users=False),
        )
        self.message = await interaction.original_response()
        await self.warn_if_not_registered(interaction, interaction.user.id)

    async def warn_if_not_registered(
        self, interaction: discord.Interaction, user_id: int
    ):
        """Sends an ephemeral message if user has not registered its user ID"""
        author_id = hashlib.pbkdf2_hmac(
            hash_name, str(user_id).encode(), salt, iterations
        ).hex()
        with self.db:
            with self.db.bind_ctx([Identity]):
                try:
                    Identity.get_by_id(author_id)
                except DoesNotExist:
                    await interaction.followup.send(
                        "Pour afficher systématiquement votre pseudo dans les classements, Abeille a besoin de stocker votre identifiant utilisateur. Utilisez la commande **/register** pour cela. Il sera toujours possible de supprimer cette donnée d'Abeille avec la commande **/unregister**. 🐝",
                        ephemeral=True,
                    )

    @discord.ui.button(label="Et moi ?", style=discord.ButtonStyle.primary)
    async def rank_me(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        result = self.get_rank_content(interaction.user)
        await interaction.response.edit_message(
            content=result, allowed_mentions=discord.AllowedMentions(users=False)
        )

        await self.warn_if_not_registered(interaction, interaction.user.id)

    def get_rank_content(self, interaction_user: discord.User):

        author = interaction_user
        author_id = hashlib.pbkdf2_hmac(
            hash_name, str(author.id).encode(), salt, iterations
        ).hex()

        with self.db:
            with self.db.bind_ctx([Message, MessageIndex, Identity]):
                rank_query = fn.rank().over(
                    order_by=[fn.COUNT(Message.message_id).desc()]
                )

                subq = (
                    Message.select(Message.author_id, rank_query.alias("rank"))
                    .join(MessageIndex, on=(Message.message_id == MessageIndex.rowid))
                    .where(MessageIndex.match(self.expression_fts))
                    .group_by(Message.author_id)
                )

                # Here we use a plain Select() to create our query.
                query = (
                    Select(columns=[subq.c.rank])
                    .from_(subq)
                    .where(subq.c.author_id == author_id)
                    .bind(self.db)
                )  # We must bind() it to the database.

                rank = query.scalar()

                # Add interaction user to interacted user dict
                self.interaction_user_ranks[interaction_user.id] = rank

                query_messages = (
                    Message.select()
                    .join(MessageIndex, on=(Message.message_id == MessageIndex.rowid))
                    .where(MessageIndex.match(self.expression_fts))
                    .group_by(Message.author_id)
                    .order_by(fn.COUNT(Message.message_id).desc())
                )
                messages: List[Message] = list(query_messages)

                if messages:
                    rankings_str_list = [
                        f"**{len(messages)}** membres ont déjà utilisé l'expression *{self.expression}*.\n"
                    ]
                    for idx, message in enumerate(messages[: self.max_lines], 1):
                        # Try to get real user ID if registered
                        user = None
                        try:
                            identity: Identity = Identity.get_by_id(message.author_id)
                            user = self.bot.get_user(identity.real_author_id)
                        except DoesNotExist:
                            pass

                        # If user is registered
                        if user is not None:
                            user_str = user.mention
                        # If user executed the command
                        # elif idx in self.interaction_user_ranks.values():
                        #     # TODO: It gets the user_id from the values of the dict....
                        #     user_str = self.bot.get_user(
                        #         list(self.interaction_user_ranks.keys())[
                        #             list(self.interaction_user_ranks.values()).index(
                        #                 idx
                        #             )
                        #         ]
                        #     ).mention
                        else:
                            user_str = "*Utilisateur non enregistré*"

                        if idx == 1:
                            rankings_str_list.append(f"🥇 {user_str}")
                        elif idx == 2:
                            rankings_str_list.append(f"🥈 {user_str}")
                        elif idx == 3:
                            rankings_str_list.append(f"🥉 {user_str}")
                        else:
                            rankings_str_list.append(f"{idx}. {user_str}")

                else:
                    rankings_str_list = [
                        "Cette expression n'a jamais été employée sur ce serveur."
                    ]

        user_ranks_str = ""
        for user_id, user_rank in self.interaction_user_ranks.items():
            user = self.bot.get_user(user_id)
            if user_rank is None:
                user_ranks_str += f"{user.mention} n'a jamais employé l'expression *{self.expression}*.\n"
            elif user_rank == 1:
                user_ranks_str += f"🥇 {user.mention} est le membre ayant le plus employé l'expression *{self.expression}*.\n"
            elif user_rank == 2:
                user_ranks_str += f"🥈 {user.mention} est le 2ème membre à avoir le plus employé l'expression *{self.expression}*.\n"
            elif user_rank == 3:
                user_ranks_str += f"🥉 {user.mention} est le 3ème membre à avoir le plus employé l'expression *{self.expression}*.\n"
            else:
                user_ranks_str += f"{user.mention} est le **{user_rank}ème** membre à avoir le plus employé l'expression *{self.expression}*.\n"

        user_ranks_str += "\n" + "\n".join(rankings_str_list)

        return user_ranks_str


class TrendView(discord.ui.View):
    def __init__(
        self,
        interaction: discord.Interaction,
        bot: commands.Bot,
        terme: str,
    ):
        # Timeout has to be strictly lower than 15min=900s (since interaction is dead after this time)
        super().__init__(timeout=720)
        self.initial_interaction = interaction
        self.message: discord.InteractionMessage = None
        self.bot = bot
        self.guild_id = interaction.guild_id
        self.terme = terme

        # FTS5 : enclose in double quotes
        self.terme_fts = f'"{terme}"'

        self.df: pandas.DataFrame = None

        guild_name = self.bot.get_guild(self.guild_id)
        title_lines = textwrap.wrap(f"Tendances de <b>'{self.terme}'</b>")
        title_lines.append(f"<i style='font-size: 10px'>Sur {guild_name}.</i>")
        self.title = "<br>".join(title_lines)

    async def interaction_check(self, interaction: discord.Interaction, /):
        allowed = interaction.user.id == self.initial_interaction.user.id
        if not allowed:
            await interaction.response.send_message(
                "Seul l'utilisateur ayant initié la commande peut toucher aux boutons. 🐝",
                ephemeral=True,
            )
        return allowed

    async def on_timeout(self) -> None:
        self.clear_items()
        await self.message.edit(view=self)

    async def start(self):
        await self.initial_interaction.response.defer(thinking=True)

        db = get_tracked_guild(self.bot, self.guild_id).database

        with db.bind_ctx([Message, MessageIndex, MessageDay]):

            # Messages de l'utilisateur dans la période
            query = RawQuery(
                """
                SELECT DATE(message.timestamp) as date, COUNT(messageindex.rowid)/CAST (messageday.count AS REAL) as messages
                FROM messageindex
                JOIN message ON messageindex.rowid = message.message_id
                JOIN messageday ON DATE(message.timestamp)=messageday.date
                WHERE messageindex MATCH ?
                GROUP BY DATE(message.timestamp)
                ORDER BY DATE(message.timestamp);""",
                params=([self.terme_fts]),
            )

            # Exécution requête SQL
            logging.info("Executing database request...")
            query_sql, query_params = query.sql()
            df = pandas.read_sql_query(query_sql, db.connection(), params=query_params)
            logging.info("Database request answered.")

        logging.info("Processing data and creating graph...")

        # Remplir les dates manquantes
        df = df.set_index("date")
        df.index = pandas.DatetimeIndex(df.index)
        df = df.reindex(pandas.date_range(df.index.min(), df.index.max()), fill_value=0)

        # Rolling average
        df["messages"] = df.rolling(ROLLING_AVERAGE).mean()

        # Remove NaN values
        df = df.dropna()

        # Save this df that shows unlimited period
        self.df = df

        # Si emote custom : simplifier le nom pour titre DW
        custom_emoji_str = emoji_to_str(self.terme)
        if custom_emoji_str:
            self.terme = custom_emoji_str

        img = self.get_img(df)

        # Envoyer image
        logging.info("Sending image to client...")
        await self.initial_interaction.followup.send(
            file=discord.File(io.BytesIO(img), "abeille.png"), view=self
        )
        logging.info("Image sent to client.")
        self.message = await self.initial_interaction.original_response()

    @discord.ui.select(
        placeholder="Changer la période",
        options=[
            discord.SelectOption(
                label="Depuis le début",
                value="0",
                description="Afficher la tendance sans limite de période",
                default=True,
            ),
            discord.SelectOption(
                label="1 an", value="1", description="Afficher la tendance sur 1 an"
            ),
            discord.SelectOption(
                label="2 ans", value="2", description="Afficher la tendance sur 2 ans"
            ),
            discord.SelectOption(
                label="3 ans", value="3", description="Afficher la tendance sur 3 ans"
            ),
        ],
    )
    async def select_period(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ):
        """Select period"""
        # Update selected option
        for option in select.options:
            option.default = select.values[0] == option.value

        years = int(select.values[0])
        if years:
            df = self.df.tail(365 * years)
        else:
            df = self.df

        # Envoyer image
        img = self.get_img(df)
        logging.info("Sending image to client...")
        await interaction.response.edit_message(
            attachments=[discord.File(io.BytesIO(img), "abeille.png")],
            view=self,
        )
        logging.info("Image sent to client.")

    def get_img(self, df: pandas.DataFrame):
        """Get figure"""
        fig = px.area(
            df,
            # x="date",
            y="messages",
            color_discrete_sequence=["yellow"],
            # line_shape="spline",
            template="plotly_dark",
            title=self.title,
            labels={"index": "", "messages": ""},
        )
        fig.update_layout(yaxis_tickformat=".2%")
        logging.info("Data processed and graph created. Exporting to image...")
        return fig.to_image(format="png", scale=2)


async def setup(bot):
    await bot.add_cog(Activity(bot))
