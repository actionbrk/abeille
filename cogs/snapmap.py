import logging
import os
from datetime import date, datetime
from typing import Dict, List, Optional

import discord
import requests
from discord import Color, app_commands
from discord.ext import commands

from models.snapmap import LocationInfo, Snap


GET_PLAYLIST_URL = "https://ms.sc-jpl.com/web/getPlaylist"
GET_LATEST_TILE_SET_URL = "https://ms.sc-jpl.com/web/getLatestTileSet"
GEOCODING_URL = "https://nominatim.openstreetmap.org/search"
TIMEOUT = 10.0


class Snapmap(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="snapmap", description="Obtenir des snaps d'un endroit spécifié."
    )
    @app_commands.describe(
        location="Saisissez l'endroit où chercher des snaps.",
        radius="Rayon en km autour du point recherché (10km par défaut).",
    )
    async def snapmap(
        self,
        interaction: discord.Interaction,
        location: str,
        radius: app_commands.Range[int, 1] = 10,
    ):
        """Snap from a specified location"""
        location = location.strip()
        await SnapmapView(interaction, location, radius).start()


class SnapmapView(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, location: str, radius: int):
        # Timeout has to be strictly lower than 15min=900s (since interaction is dead after this time)
        super().__init__(timeout=720)
        self.initial_interaction = interaction
        self.location = location
        self.geocoded_location_name = ""
        self.radius = radius
        self.snap_index = 0
        self.snap_playlist: List[Snap]
        self.message: discord.InteractionMessage = None

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
        """Send snap playlist to user"""
        location_info = self.get_location_info(self.location)

        if location_info:
            self.geocoded_location_name = location_info["display_name"]

            # Get snaps
            tile_set_response = requests.post(
                GET_LATEST_TILE_SET_URL, json={}, timeout=TIMEOUT
            )
            epoch1: str = tile_set_response.json()["tileSetInfos"][0]["id"]["epoch"]
            epoch2: str = tile_set_response.json()["tileSetInfos"][1]["id"]["epoch"]
            if epoch1.endswith("000"):
                epoch = epoch1
            else:
                epoch = epoch2

            snap_request_data = {
                "requestGeoPoint": {
                    "lat": float(location_info["lat"]),
                    "lon": float(location_info["lon"]),
                },
                "tileSetId": {"flavor": "default", "epoch": epoch, "type": 1},
                "radiusMeters": self.radius * 1000,
            }
            snap_response = requests.post(
                GET_PLAYLIST_URL, json=snap_request_data, timeout=TIMEOUT
            )

            self.snap_playlist = snap_response.json()["manifest"]["elements"]

            await self.initial_interaction.response.send_message(
                self.get_content(),
                view=self,
            )
        else:
            await self.initial_interaction.response.send_message(
                f"Impossible de trouver la localisation *{self.location}*.",
                ephemeral=True,
            )
        self.message = await self.initial_interaction.original_response()

    def get_location_info(self, location: str) -> Optional[LocationInfo]:
        headers = {"User-Agent": "Abeille"}
        params = {"q": location, "format": "json", "adressdetails": "1"}
        response = requests.get(
            GEOCODING_URL, headers=headers, params=params, timeout=TIMEOUT
        )
        location_list: List[LocationInfo] = response.json()
        if location_list:
            return location_list[0]
        return None

    def get_current_snap(self) -> Snap:
        return self.snap_playlist[self.snap_index]

    def get_content(self) -> str:
        """Get content to send"""
        current_snap = self.get_current_snap()
        content = [
            f"{current_snap['snapInfo']['title']['fallback']} <t:{current_snap['timestamp'][:-3]}:R>\n"
        ]

        # TODO: content.append(current_snap["snapInfo"].get("overlayText"))

        if current_snap["snapInfo"]["streamingMediaInfo"].get("mediaUrl"):
            media_url = (
                current_snap["snapInfo"]["streamingMediaInfo"]["prefixUrl"]
                + current_snap["snapInfo"]["streamingMediaInfo"]["mediaUrl"]
            )
        else:
            media_url = current_snap["snapInfo"]["publicMediaInfo"][
                "publicImageMediaInfo"
            ]["mediaUrl"]

        # content.append(
        #     f"> Snaps pour la localisation `{self.geocoded_location_name}` sur un rayon de `{self.radius} km`\n"
        # )
        content.append(media_url)

        return "".join(content)

    @discord.ui.button(label="Précédent", style=discord.ButtonStyle.primary)
    async def previous(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Next button"""
        self.snap_index -= 1
        await interaction.response.edit_message(content=self.get_content())

    @discord.ui.button(label="Suivant", style=discord.ButtonStyle.primary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Next button"""
        self.snap_index += 1
        await interaction.response.edit_message(content=self.get_content())

    @discord.ui.button(emoji="ℹ️", style=discord.ButtonStyle.secondary)
    async def info(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Information"""
        to_send = [
            f"`{len(self.snap_playlist)}` snaps trouvés pour la localisation `{self.geocoded_location_name}` sur un rayon de `{self.radius} km`.",
            "Géocodage réalisé par OpenStreetMap.",
        ]
        await interaction.response.send_message("\n\n".join(to_send), ephemeral=True)

    @discord.ui.button(label="Fermer", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Close"""
        self.stop()
        await self.message.delete()


async def setup(bot):
    await bot.add_cog(Snapmap(bot))
