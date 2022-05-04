import discord
from discord import app_commands
from discord.ext import commands


class Misc(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="bzz", description="Bzz bzz (ping) ! 🐝")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message("Je fonctionne ! 🐝")


async def setup(bot):
    await bot.add_cog(Misc(bot))
