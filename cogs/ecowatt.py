import logging
import os
import urllib.request
from datetime import datetime
from io import BytesIO
from typing import Dict, List
from zipfile import ZipFile

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

VIGILANCE_URL_CHECKSUM = (
    "https://vigilance2019.meteofrance.com/data/vigilance_controle.txt"
)
VIGILANCE_URL_ZIP = "https://vigilance2019.meteofrance.com/data/vigilance.zip"
VIGILANCE_FILE_NAME = "QGFR17_LFPW_.gif"


CR_TODAYS_ANOMALIES_URL = (
    "https://climatereanalyzer.org/wx/todays-weather/json/cfsr_t2_todays_anomalies.json"
)
REGIONS_NAMES = [
    "Monde",
    "Hémisphère Nord",
    "Hémisphère Sud",
    "Arctique",
    "Antarctique",
    "Tropiques",
]


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

    @app_commands.command(
        name="vigilance",
        description="Afficher le dernier bulletin vigilance Météo-France",
    )
    async def vigilance(self, interaction: discord.Interaction):
        """Vigilance Météo-France"""
        vigilance_zipfile = urllib.request.urlopen(VIGILANCE_URL_ZIP)

        # vigilance_checksum_file = urllib.request.urlopen(VIGILANCE_URL_CHECKSUM)
        # new_vigilance_checksum = vigilance_checksum_file.readlines()[1]
        # if self.vigilance_checksum != new_vigilance_checksum:
        # self.vigilance_checksum = new_vigilance_checksum

        with ZipFile(BytesIO(vigilance_zipfile.read())) as zipfile:
            with zipfile.open("QGFR17_LFPW_.gif") as imagefile:
                await interaction.response.send_message(file=discord.File(imagefile))

    @app_commands.command(
        name="climat",
        description="L'anomalie de température dans le monde.",
    )
    async def climat_slash(self, interaction: discord.Interaction):
        """Climate change"""

        todays_anomalies_response = requests.get(
            CR_TODAYS_ANOMALIES_URL,
            timeout=TIMEOUT,
        )

        todays_anomalies_values: List[float] = next(
            item
            for item in todays_anomalies_response.json()
            if item["name"] == "t2anom"
        )["data"]

        todays_anomalies = [
            (REGIONS_NAMES[index], anomaly_value)
            for index, anomaly_value in enumerate(todays_anomalies_values)
        ]

        to_send = []

        for anomaly_region, anomaly_value in todays_anomalies:
            to_send.append(
                f"{anomaly_region} : **{anomaly_value:+}°C** {'🔥' if anomaly_value>0 else '❄️'}"
            )

        embed = discord.Embed(
            title="Anomalie de température actuelle",
            description="Aujourd'hui, par rapport aux températures de la période 1979-2000.",
            color=Color.from_str("#ffb03b"),
            url="https://climatereanalyzer.org/wx/todays-weather/?var_id=t2anom&ortho=3&wt=1",
        )
        embed.set_footer(
            icon_url="https://climatereanalyzer.org/logos/favicon-cr.png",
            text="Données fournies par ClimateReanalyzer.org",
        )
        embed.set_image(
            url="https://climatereanalyzer.org/wx/todays-weather/input/gfs_world-wt_t2anom_d1.png"
        )

        embed.add_field(name="Par région", value="\n".join(to_send), inline=False)

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Ecowatt(bot))
