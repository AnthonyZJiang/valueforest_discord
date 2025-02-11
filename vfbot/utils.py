import logging

import discord
from discord.utils import _ColourFormatter

ASHLEY_ID = 1313007325224898580
ANGELA_ID = 1292300055625203763
TESTER_ID = 185020620310839296

def setup_logging() -> None:
    level = logging.INFO

    handler = logging.StreamHandler()
    formatter = _ColourFormatter()
    
    library, _, _ = __name__.partition('.')
    logger = logging.getLogger(library)

    handler.setFormatter(formatter)
    logger.setLevel(level)
    logger.addHandler(handler)

def retouch_ashley(content: str):
    content = content.replace(":RedAlert:", ":new:")
    return content
        
def retouch_angela(content: str):
    content = content.replace(":8375_siren_blue:", ":new:")
    content = content.replace(":RedAlert", ":red_square:")
    content = content.replace(":5264greensiren:", ":green_square:")
    return content    
    
def message_retouch(message: discord.Message):
    content = message.content
    content = content.replace("@c2.ini", "")
    content = content.replace(":9655_eyesshaking_new:", ":eyes:")
    content = content.replace(":pngwing:", ":red_circle:")
    content = content.replace(":verifyblue:", ":white_check_mark:")
    
    if message.author.id == ASHLEY_ID: # ashley
        content =retouch_ashley(content)
    if message.author.id == ANGELA_ID: # angela
        content = retouch_angela(content)
    return content