import logging
import re
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

def retouch_ashley(content: str):
    content = re.sub(r':RedAlert:|<a:RedAlert:\d+>', ":new:", content)
    return content
        
def retouch_angela(content: str):
    content = re.sub(r':8375_siren_blue:|<a:8375_siren_blue:\d+>', ":new:", content)
    content = re.sub(r':RedAlert:|<a:RedAlert:\d+>', ":red_sqare:", content)
    content = re.sub(r':greensiren:|<a:greensiren:\d+>', ":green_square:", content)
    return content    
    
def message_retouch(message: discord.Message):
    content = message.content
    content = content.replace("@c2.ini", "")
    content = re.sub(r':9655_eyesshaking_new:|<a:9655_eyesshaking_new:\d+>', ":eyes:", content)
    content = content.replace(":pngwing:", ":red_circle:")
    content = content.replace(":verifyblue:", ":white_check_mark:")
    
    if message.author.id == ASHLEY_ID: # ashley
        content =retouch_ashley(content)
    elif message.author.id == ANGELA_ID: # angela
        content = retouch_angela(content)
    message.content = content
    

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

    def parse_ocr_result(ocr_result: str):
        ocr_result = json.loads(ocr_result)
        lines = ocr_result['ParsedResults'][0]['TextOverlay']['Lines']
        
        symbol, strike, option_type, last_price = None, None, None, None
        
        for i, line in enumerate(lines):
            if "Call" in line['LineText'] or "Put" in line['LineText']:
                call_line = line['LineText']
                symbol, strike, option_type = call_line.split()
                strike = strike.replace("$", "").replace(",", "")
                if strike.isdigit():
                    strike = float(strike)
                else:
                    strike = None
                option_type = option_type.lower()
                # Get the next line's text (if it exists and contains a price)
                if i + 1 < len(lines) and '$' in lines[i + 1]['LineText']:
                    price_line = lines[i + 1]['LineText']
                    last_price = price_line.replace("$", "").replace(",", "")
                    if last_price.isdigit():
                        last_price = float(last_price)
                    else:
                        last_price = None
                break
        
        return symbol, strike, option_type, last_price
    
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
        author_name = channel_info["author_name"]
        
        for author_id in author_ids:
            author_mapping[author_id] = author_name
    
    return author_mapping