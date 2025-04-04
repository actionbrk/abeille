""" Commandes de tendances """

import hashlib
import io
import logging
import os
import textwrap
from datetime import date, datetime, timedelta
from typing import Dict, List, Set

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

ROLLING_AVERAGE = 14

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
        await interaction.response.defer()

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
            await interaction.response.send_message(
                "Je ne peux pas traiter les expressions de moins de 3 caractères. 🐝",
                ephemeral=True,
            )
            return
        if len(expression) > 200:
            await interaction.response.send_message(
                "Je ne peux pas traiter une expression aussi grande. 🐝", ephemeral=True
            )
            return

        guild_id = interaction.guild_id
        if not guild_id:
            await interaction.response.send_message("Can't find guild id.")
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
    rankings_length = 10

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

        # Rank - User ID
        self.user_ranks: Dict[int, int | None] = {}

        # Rank - User message count
        self.user_counts: Dict[int, int] = {}
        self.user_counts_total = None

        self.interaction_users: Set[int] = set()
        self.embed = discord.Embed()
        self.show_premium_infos = None

    async def interaction_check(self, interaction: discord.Interaction, /):
        """Allow user to click button once"""
        return interaction.user.id not in self.interaction_users

    async def on_timeout(self) -> None:
        self.clear_items().stop()
        await self.message.edit(view=self)

    async def start(self, interaction: discord.Interaction):
        premium_role = interaction.guild.premium_subscriber_role
        self.show_premium_infos = (
            premium_role
            and premium_role.display_icon
            and interaction.user.premium_since is not None
        )
        # Send rank for initial interaction user
        self.interaction_users.add(interaction.user.id)
        if self.show_premium_infos:
            self.embed.color = (
                await self.bot.fetch_user(interaction.user.id)
            ).accent_color
            self.embed.set_footer(
                icon_url=premium_role.display_icon.url,
                text=f"Infos supplémentaires affichées grâce au rôle {premium_role.name} de {interaction.user.name}.",
            )
        interaction_author_id = hashlib.pbkdf2_hmac(
            hash_name, str(interaction.user.id).encode(), salt, iterations
        ).hex()

        with self.db:
            with self.db.bind_ctx([Message, MessageIndex, Identity]):
                logging.info("Executing database request...")
                query_messages = (
                    Message.select(
                        Message.author_id, fn.COUNT(Message.message_id).alias("count")
                    )
                    .join(MessageIndex, on=(Message.message_id == MessageIndex.rowid))
                    .where(MessageIndex.match(self.expression_fts))
                    .group_by(Message.author_id)
                    .order_by(fn.COUNT(Message.message_id).desc())
                )
                messages: List[Message] = list(query_messages)
                logging.info("Database request answered.")

                if messages:
                    self.embed.title = f"`{len(messages)}` membres ont déjà utilisé l'expression *{self.expression}*.\n"
                    for idx, message in enumerate(messages, 1):
                        user = None

                        # If user executed the command
                        if message.author_id == interaction_author_id:
                            user = interaction.user
                        else:
                            # Try to get real user ID if registered
                            try:
                                identity: Identity = Identity.get_by_id(
                                    message.author_id
                                )
                                user = self.bot.get_user(identity.real_author_id)
                            except DoesNotExist:
                                pass

                        self.user_ranks[idx] = user.id if user else None
                        self.user_counts[idx] = message.count
                        self.user_counts_total = sum(self.user_counts.values())
                else:
                    self.embed.title = f"L'expression *{self.expression}* n'a jamais été employée sur ce serveur."
                    await interaction.response.send_message(embed=self.embed)
                    return

        self._update_embed()

        await interaction.response.send_message(
            embed=self.embed,
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

    @discord.ui.button(
        label="Afficher mon classement", style=discord.ButtonStyle.primary
    )
    async def rank_me(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.interaction_users.add(interaction.user.id)

        self._update_embed()

        await interaction.response.edit_message(
            embed=self.embed,
            allowed_mentions=discord.AllowedMentions(users=False),
            view=self,
        )

        await self.warn_if_not_registered(interaction, interaction.user.id)

    def _update_embed(self):
        embed_desc = []
        for user_rank in sorted(self.user_ranks.keys()):
            user_id = self.user_ranks.get(user_rank)
            user_count = self.user_counts.get(user_rank)

            # If user interacted, show it in rankings anyway
            if (user_rank <= self.rankings_length) or (
                user_id in self.interaction_users
            ):
                # User name if found
                if user_id is None:
                    user_str = "*Utilisateur non enregistré*"
                else:
                    user_str = self.bot.get_user(user_id).mention

                # User message count if premium
                if self.show_premium_infos:
                    user_str += f" `~{(user_count/self.user_counts_total)*100:.0f}%`"

                # User rank
                if user_rank == 1:
                    embed_desc.append(f"🥇 {user_str}")
                elif user_rank == 2:
                    embed_desc.append(f"🥈 {user_str}")
                elif user_rank == 3:
                    embed_desc.append(f"🥉 {user_str}")
                else:
                    embed_desc.append(f"{user_rank}. {user_str}")

        self.embed.description = "\n".join(embed_desc)

        # Unranked interaction users
        interaction_users_unranked = self.interaction_users - set(
            self.user_ranks.values()
        )
        if interaction_users_unranked:
            field_name = "N'ont jamais utilisé cette expression"
            field_value = "\n".join(
                [
                    f"{self.bot.get_user(unranked_user_id).mention}"
                    for unranked_user_id in interaction_users_unranked
                ]
            )
            if not self.embed.fields:
                self.embed.add_field(
                    name=field_name,
                    value=field_value,
                )
            else:
                self.embed.set_field_at(
                    index=0,
                    name=field_name,
                    value=field_value,
                )


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
        self.selected_period = "0"
        self.selected_rolling = "14"

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
        # Reset default select options
        self.set_selected_period(self.selected_period)
        self.set_selected_rolling(self.selected_rolling)

        db = get_tracked_guild(self.bot, self.guild_id).database

        with db.bind_ctx([Message, MessageIndex, MessageDay]):
            # Getting first and last day
            first_day = MessageDay.select(fn.MIN(MessageDay.date)).scalar()
            last_day = MessageDay.select(fn.MAX(MessageDay.date)).scalar()

            # Trend request
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

            # Execute SQL query
            logging.info("Executing database request...")
            query_sql, query_params = query.sql()
            df = pandas.read_sql_query(query_sql, db.connection(), params=query_params)
            logging.info("Database request answered.")

        logging.info("Processing data and creating graph...")

        # Fill missing dates
        df = df.set_index("date")
        df.index = pandas.DatetimeIndex(df.index)
        df = df.reindex(pandas.date_range(first_day, last_day), fill_value=0)

        # Save this df that shows unlimited period
        self.df = df

        # Custom emote: sanitize name
        custom_emoji_str = emoji_to_str(self.terme)
        if custom_emoji_str:
            self.terme = custom_emoji_str

        await self.send_img()

    @discord.ui.select(
        placeholder="Changer la période",
        options=[
            discord.SelectOption(
                label="Depuis le début",
                value="0",
                description="Afficher la tendance sans limite de période",
            ),
            discord.SelectOption(
                label="Tendance sur 1 an",
                value="1",
                description="Afficher la tendance sur 1 an",
            ),
            discord.SelectOption(
                label="Tendance sur 2 ans",
                value="2",
                description="Afficher la tendance sur 2 ans",
            ),
            discord.SelectOption(
                label="Tendance sur 3 ans",
                value="3",
                description="Afficher la tendance sur 3 ans",
            ),
        ],
    )
    async def select_period(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ):
        """Select period"""
        # Update selected option
        self.set_selected_period(select.values[0])

        # Send image
        await self.send_img(interaction)

    def set_selected_period(self, option_value: str):
        self.selected_period = option_value
        for option in self.select_period.options:
            option.default = option_value == option.value

    @discord.ui.select(
        placeholder="Changer la durée de moyennage",
        options=[
            discord.SelectOption(
                label="Moyenne sur 14 jours",
                value="14",
                description="Moyenne glissante sur 14 jours",
            ),
            discord.SelectOption(
                label="Moyenne sur 7 jours",
                value="7",
                description="Moyenne glissante sur 7 jours",
            ),
            discord.SelectOption(
                label="Ne pas moyenner",
                value="1",
                description="Supprimer la moyenne glissante",
            ),
        ],
    )
    async def select_rolling(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ):
        """Select rolling average days"""
        # Update selected option
        self.set_selected_rolling(select.values[0])

        # Send image
        await self.send_img(interaction)

    def set_selected_rolling(self, option_value: str):
        self.selected_rolling = option_value
        for option in self.select_rolling.options:
            option.default = option_value == option.value

    async def send_img(self, interaction: discord.Interaction | None = None):
        """Generate graph image and send it"""
        df = self.df.copy(deep=True)

        # Rolling average
        df["messages"] = df.rolling(int(self.selected_rolling)).mean()

        # Remove NaN values
        df = df.dropna()

        # Period
        years = int(self.selected_period)
        if years:
            df = df.tail(365 * years)

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
        current_timestamp = datetime.now().strftime("%d/%m/%Y")
        bot_user = self.bot.user
        bot_name = f"{bot_user.name}#{bot_user.discriminator}"
        fig.update_layout(
            yaxis_tickformat=".2%",
            annotations=[
                dict(
                    text=f"Généré le {current_timestamp} par {bot_name}.",
                    xref="paper",
                    yref="paper",
                    x=1,
                    y=-0.15,
                    xanchor="right",
                    yanchor="bottom",
                    showarrow=False,
                    font=dict(size=10),
                )
            ],
        )
        logging.info("Data processed and graph created. Exporting to image...")
        img = fig.to_image(format="png", scale=2)

        logging.info("Sending image to client...")
        file = discord.File(io.BytesIO(img), "abeille.png")
        if interaction is None:
            await self.initial_interaction.followup.send(file=file, view=self)
        else:
            await interaction.response.edit_message(attachments=[file], view=self)
            
        self.message = await self.initial_interaction.original_response()

        logging.info("Image sent to client.")


async def setup(bot):
    await bot.add_cog(Activity(bot))
