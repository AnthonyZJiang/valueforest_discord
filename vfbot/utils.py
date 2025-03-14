import logging
import requests
import json

import discord
from discord.utils import _ColourFormatter

ASHLEY_ID = 1313007325224898580
ANGELA_ID = 1313008328229785640
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

def create_author_id_to_name_mapping(config: dict):
    author_mapping = {}
    
    for channel_info in config["channels"].values():
        author_ids = channel_info["author_ids"]
        author_name = channel_info["author_name_override"]
        
        for author_id in author_ids:
            author_mapping[author_id] = author_name
    
    return author_mapping

def get_config_value(config: dict, key: str, default = None):
    if key in config:
        return config[key]
    return default
