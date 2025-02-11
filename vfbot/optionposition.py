import re
from datetime import datetime
from typing import Union

import discord

from .utils import ASHLEY_ID, ANGELA_ID

class OptionPosition:
    def __init__(self, text: str, author_id: int, datetime: Union[datetime, None]):
        self.text = text
        self.author_id = author_id
        self.id = None
        self.valid = False
        self.symbol = None
        self.strike = None
        self.call_put = None
        self.updates = [] #type: list[str]
        self.dc_message = None #type: discord.Message
        self.datetime = datetime
        self.parse()
        
    def parse(self) -> bool:
        if self.author_id == ASHLEY_ID:
            self.valid = self._parse_ashley()
        elif self.author_id == ANGELA_ID:
            self.valid = self._parse_angela()
    
    def get_id(self) -> int:
        if self.id:
            return self.id
        if self.valid:
            self.id = f'{self.author_id}:{self.symbol}:{self.strike}:{self.call_put}'
        return self.id
    
    def add_update(self, message: discord.Message):
        self.updates.append(f':hourglass:{message.created_at.strftime("%m-%d %H:%M:%S") if message.created_at else "unknown"}::hourglass: {message.content}')
        
    def get_updates(self) -> str:
        return '\n'.join(self.updates)
    
    def __str__(self) -> str:
        author_name = "Ashley" if self.author_id == ASHLEY_ID else "Angela"
        return f'{'-'*10}\n{self.symbol}:{self.strike}:{self.call_put} - {author_name}\n:hourglass:{self.datetime.strftime("%m-%d %H:%M:%S") if self.datetime else "unknown"}::hourglass: {self.text}\n{self.get_updates()}'
            
    def _parse_ashley(self) -> bool:
        ticker_pattern = r':[^:]+:\s+(\w+)(?:\s*-)?'
        dollar_pattern = r'\$(\d+(?:\.\d{2})?)'
        option_pattern = r'(calls|puts)'
        
        ticker_match = re.search(ticker_pattern, self.text)
        self.symbol = ticker_match.group(1) if ticker_match else None
        
        dollar_matches = re.findall(dollar_pattern, self.text)
        dollar_amounts = [float(x) for x in dollar_matches]
        self.strike = max(dollar_amounts) if dollar_amounts else None

        option_match = re.search(option_pattern, self.text, re.IGNORECASE)
        self.call_put = option_match.group(1) if option_match else None

        return self.symbol is not None and self.strike is not None and self.call_put is not None
    
    def _parse_angela(self) -> bool:
        ticker_pattern = r':[^:]+:\s+(\w+)(?:\s*-)?'
        dollar_pattern = r'\$(\d+(?:\.\d{2})?)'
        option_pattern = r'(calls|puts)'
        
        ticker_match = re.search(ticker_pattern, self.text)
        self.symbol = ticker_match.group(1) if ticker_match else None
        
        dollar_matches = re.findall(dollar_pattern, self.text)
        dollar_amounts = [float(x) for x in dollar_matches]
        self.strike = max(dollar_amounts) if dollar_amounts else None

        option_match = re.search(option_pattern, self.text, re.IGNORECASE)
        self.call_put = option_match.group(1) if option_match else None

        return self.symbol is not None and self.strike is not None and self.call_put is not None
