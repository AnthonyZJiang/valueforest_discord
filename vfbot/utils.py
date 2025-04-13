import logging
import socket
import os
import dotenv
import json
import requests
import uuid
from discord.utils import _ColourFormatter

ASHLEY_ID = 1313007325224898580
ANGELA_ID = 1313008328229785640
TESTER_ID = 185020620310839296

dotenv.load_dotenv()

TRANSLATE_HOST = os.getenv('TRANSLATE_HOST')
TRANSLATE_PORT = int(os.getenv('TRANSLATE_PORT'))
TRANSLATE_BUFFER_SIZE = 8192
AZURE_TRANSLATOR_KEY = os.getenv('AZURE_TRANSLATOR_KEY')
AZURE_TRANSLATOR_LOCATION = os.getenv('AZURE_TRANSLATOR_LOCATION')


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

def translate(payload: dict[str, str]) -> str:
    json_data = json.dumps(payload)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((TRANSLATE_HOST, TRANSLATE_PORT))
        s.sendall(json_data.encode('utf-8'))
        response = s.recv(TRANSLATE_BUFFER_SIZE)
        return json.loads(response.decode('utf-8'))

def azure_translate(payload: list[dict[str, str]]) -> str:
    api_url = 'https://api.cognitive.microsofttranslator.com/translate'

    params = {
        'api-version': '3.0',
        'from': 'en',
        'to': ['en', 'zh']
    }

    headers = {
        'Ocp-Apim-Subscription-Key': AZURE_TRANSLATOR_KEY,
        'Ocp-Apim-Subscription-Region': AZURE_TRANSLATOR_LOCATION,
        'Content-type': 'application/json',
        'X-ClientTraceId': str(uuid.uuid4())
    }

    request = requests.post(api_url, params=params, headers=headers, json=payload)
    response = request.json()
    # with open('translate_result.json', 'r') as f:
    #     responses = json.load(f)
    # for response in responses:
    #     if response[3] == payload:
    #         del response[3]
    #         break
    if not response:
        return {
            'error': 'No response from Azure Translator'
        }
    if isinstance(response, dict):
        if response.get('error', None):
            return {
                'error': f'{response["error"]["code"]}: {response["error"]["message"]}'
            }
    if len(response) != 3:
        return {
            'error': f'Invalid response length: {len(response)}'
        }
    # response.append(payload)
    # with open('translate_result.json', 'a+') as f:
    #     json.dump(response, f, indent=4)
    return {
        'main_text': response[0]['translations'][1]['text'],
        'reblog_text': response[1]['translations'][1]['text'],
        'quoted_text': response[2]['translations'][1]['text']
    }