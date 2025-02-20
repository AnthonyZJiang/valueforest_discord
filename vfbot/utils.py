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

def ocr_image_from_message(message: discord.Message, api_key: str):
    
    def ocr_space_url(url, api_key, overlay=True, language='eng'):
        payload = {'url': url,
                'isOverlayRequired': overlay,
                'apikey': api_key,
                'language': language,
                }
        r = requests.post('https://api.ocr.space/parse/image',
                        data=payload,
                        )
        return r.content.decode()
    
    def str_to_float(s: str):
        try:
            s = s.replace("$", "").replace(",", "")
            return float(s)
        except:
            return None

    def parse_ocr_result(ocr_result: str):
        ocr_result = json.loads(ocr_result)
        lines = ocr_result['ParsedResults'][0]['TextOverlay']['Lines']
        
        symbol, strike, option_type, open_price, last_price = None, None, None, None, None
        checked = 0
        
        for i, line in enumerate(lines):
            if "Call" in line['LineText'] or "Put" in line['LineText']:
                call_line = line['LineText']
                symbol, strike, option_type = call_line.split()
                strike = str_to_float(strike)
                option_type = option_type.lower()
                # Get the next line's text (if it exists and contains a price)
                if i + 1 < len(lines) and '$' in lines[i + 1]['LineText']:
                    price_line = lines[i + 1]['LineText']
                    last_price = str_to_float(price_line)
                    checked += 1
            elif "Average cost" in line['LineText']:
                if i + 1 < len(lines) and '$' in lines[i + 1]['LineText']:
                    price_line = lines[i + 1]['LineText']
                    open_price = str_to_float(price_line)
                    checked += 1
                    
            if checked == 2:
                break

        return symbol, strike, option_type, open_price, last_price
    
    loc = message.content.find("https://")
    if loc > -1:
        url = message.content[loc:]
        ocr_result = ocr_space_url(url, api_key, overlay=True, language='eng')
        if ocr_result:
            return parse_ocr_result(ocr_result)
    return None

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
