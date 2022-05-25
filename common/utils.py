""" Fonctions transverses """

import os
import re
from typing import Optional

import discord
from dotenv import load_dotenv

load_dotenv()

DEV_GUILD = discord.Object(id=int(os.getenv("DEV_GUILD_ID")))
CUSTOM_EMOJI = r"<a{0,1}:(\S+):(\d+)>"


def emoji_to_str(emoji_str) -> Optional[str]:
    """Transforme un emoji custom <:abc:12345> en une chaine :abc:"""
    match = re.fullmatch(CUSTOM_EMOJI, emoji_str)
    if match is not None:
        return f":{match.group(1)}:"
    return None


def str_input_ok(text: str) -> bool:
    """Retourne False si text vide ou juste des espaces"""
    return bool(text.strip())
