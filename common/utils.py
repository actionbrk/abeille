""" Fonctions transverses """

import re
from typing import Optional
from configparser import ConfigParser
from pathlib import Path

CUSTOM_EMOJI = r"<a{0,1}:(\S+):(\d+)>"
TRACKED_GUILD_IDS = []
config = ConfigParser(allow_no_value=True)
p = Path(__file__).parent.parent
config.read(p / "config.ini")
for guild_id_str in config["Tracked"]:
    TRACKED_GUILD_IDS.append(int(guild_id_str))


def emoji_to_str(emoji_str) -> Optional[str]:
    """Transforme un emoji custom <:abc:12345> en une chaine :abc:"""
    match = re.fullmatch(CUSTOM_EMOJI, emoji_str)
    if match is not None:
        return f":{match.group(1)}:"
    return None


def str_input_ok(text: str) -> bool:
    """Retourne False si text vide ou juste des espaces"""
    return bool(text.strip())
