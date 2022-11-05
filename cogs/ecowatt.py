import logging
import os
from datetime import date, datetime
from typing import Dict, List

import discord
import requests
from discord import Color, app_commands
from discord.ext import commands, tasks

from models.ecowatt import Signal

AUTH_URL = "https://digital.iservices.rte-france.com/token/oauth/"
ECOWATT_URL = "https://digital.iservices.rte-france.com/open_api/ecowatt/v4/signals"

VALUE_ICON: Dict[int, str] = {
    1: "🟢",
    2: "🟠",
    3: "🔴",
}

VALUE_MESSAGE: Dict[int, str] = {
    1: "Pas de coupure d'électricité prévue.",
    2: "Système électrique tendu. Les écogestes sont les bienvenus.",
    3: "Système électrique très tendu. Coupures inévitables si nous ne baissons pas notre consommation.",
}

TIMEOUT = 10.0


class Ecowatt(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.signals: List[Signal] = None
        self.task_ecowatt.start()

    def cog_unload(self):
        self.task_ecowatt.cancel()

    @commands.command()
    @commands.is_owner()
    async def ecowatt(self, ctx: commands.Context):
        """Force Ecowatt update"""
        await self._update_ecowatt()

    @tasks.loop(hours=1)
    async def task_ecowatt(self):
        await self._update_ecowatt()

    async def _update_ecowatt(self):
        logging.info("Updating Ecowatt...")

        auth_response = requests.get(
            AUTH_URL,
            headers={"Authorization": f"Basic {os.getenv('ECOWATT_BASE64_TOKEN')}"},
            timeout=TIMEOUT,
        )

        access_token = auth_response.json()["access_token"]

        request_response = requests.get(
            ECOWATT_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=TIMEOUT,
        )
        if request_response.status_code == 200:
            # Success
            self.signals: List[Signal] = request_response.json()["signals"]
            logging.info("Ecowatt updated.")
        elif request_response.status_code == 429:
            # Too many requests
            logging.warning("Ecowatt update has failed: too many requests (429).")
        else:
            # Error
            logging.warning(
                "Ecowatt update has failed: %d", request_response.status_code
            )

    @app_commands.command(
        name="ecowatt",
        description="Votre météo de l'électricité pour une consommation responsable.",
    )
    async def ecowatt_slash(self, interaction: discord.Interaction):
        """Ecowatt"""

        if self.signals is None:
            await self._update_ecowatt()
            if self.signals is None:
                await interaction.response.send_message(
                    "Impossible de récupérer la météo de l'électricité pour le moment.",
                    ephemeral=True,
                )
                return

        signal_today = self.signals[0]

        embed = discord.Embed(
            title=f"{VALUE_ICON[signal_today['dvalue']]} {signal_today['message']}",
            description=f"{VALUE_MESSAGE[signal_today['dvalue']]}",
            color=Color.from_str("#02f0c6"),
        )
        embed.set_author(
            name="Ecowatt", icon_url="https://www.monecowatt.fr/favicon.ico"
        )
        date_generation = datetime.fromisoformat(signal_today["GenerationFichier"])
        embed.set_footer(
            icon_url="https://upload.wikimedia.org/wikipedia/commons/thumb/1/1f/RTE_logo.svg/1200px-RTE_logo.svg.png",
            text="Données fournies par RTE",
        )
        embed.timestamp = date_generation

        next_days = []
        for signal in self.signals[1:]:
            date_value = datetime.fromisoformat(signal["jour"]).date()
            next_days.append(
                f"{date_value} : {VALUE_ICON[signal['dvalue']]} {VALUE_MESSAGE[signal['dvalue']]}"
            )
        embed.add_field(
            name="Prochains jours", value="\n".join(next_days), inline=False
        )

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Ecowatt(bot))
