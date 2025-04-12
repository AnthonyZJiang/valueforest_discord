import logging
import socket
import os
import dotenv

from discord.utils import _ColourFormatter

ASHLEY_ID = 1313007325224898580
ANGELA_ID = 1313008328229785640
TESTER_ID = 185020620310839296

dotenv.load_dotenv()

TRANSLATE_HOST = os.getenv('TRANSLATE_HOST')
TRANSLATE_PORT = int(os.getenv('TRANSLATE_PORT'))


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

def translate(message: str) -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(10)
        s.connect((TRANSLATE_HOST, TRANSLATE_PORT))
        s.sendall(message.encode())
        response = s.recv(1024)
        return response.decode()
