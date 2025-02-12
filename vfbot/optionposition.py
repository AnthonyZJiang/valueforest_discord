import re
from datetime import datetime
from typing import Union

import discord

from .utils import ASHLEY_ID, ANGELA_ID

class OptionPosition:
    def __init__(self, author_id: int, symbol: str, strike: int, call_put: str, open_price: float = None, text: str = None):
        self.symbol = symbol
        self.strike = strike
        self.call_put = call_put
        self.author_id = author_id
        self.author_name = "Ashley" if self.author_id == ASHLEY_ID else "Angela"
        self.id = None
        self.valid = symbol is not None and strike is not None and call_put is not None
        self.text = text
        
        self.open_price = None
        self.last_price = None
        self.pnl = 0
        
        self.dc_thread = None #type: discord.Thread
        
    @staticmethod
    def from_text(text: str, author_id: int):
        option_position = OptionPosition(author_id, symbol=None, strike=None, call_put=None, open_price=None, text=text)
        option_position.valid = option_position._parse_text()
        return option_position
        
    def by_symbol_strike_call_put(self, symbol: str, strike: int, call_put: str):
        return OptionPosition(f"{symbol} {strike} {call_put}", self.author_id)
    
    def get_id(self) -> int:
        if self.id:
            return self.id
        if self.valid:
            self.id = f'{self.author_id}:{self.symbol}:{self.strike}:{self.call_put}'
        return self.id
    
    async def create_thread(self, channel: discord.TextChannel):
        self.dc_thread = await channel.create_thread(name=self.get_title(), auto_archive_duration=1440, type=discord.ChannelType.public_thread)
        await self.dc_thread.send(self.text)
        
    async def add_to_thread(self, message: discord.Message, last_price: float = None):
        await self.dc_thread.send(f'{message.content}')
        if last_price:
            self.last_price = last_price
            self.pnl = (last_price - self.open_price) / self.open_price * 100
            self.dc_thread.edit(name=self.get_title())
            
    def get_title(self) -> str:
        return f'{self.author_name}: {self.symbol} ${self.strike} {self.call_put} @ ${self.open_price if self.open_price else "N/A"} | ${self.last_price if self.last_price else "N/A"} | {self.pnl:.2f}%'
    
    def _parse_text(self) -> bool:
        ticker_pattern = r':[^:]+:(?:\d+>)?\s*(\w+)(?:\s*-)?'
        dollar_pattern = r'(?:\$(\d+(?:\.\d{2})?)|(?:^|\s)\.(\d+))'  # Matches both $X.XX and .XX formats
        option_pattern = r'(calls|puts)'
        
        ticker_match = re.search(ticker_pattern, self.text)
        self.symbol = ticker_match.group(1) if ticker_match else None
        
        dollar_matches = re.findall(dollar_pattern, self.text)
        dollar_amounts = [float(x[0] or f"0.{x[1]}") for x in dollar_matches]
        dollar_amounts.sort()
        
        self.strike = max(dollar_amounts) if dollar_amounts else None
        self.open_price = dollar_amounts[1] if len(dollar_amounts) >= 2 else None
        
        option_match = re.search(option_pattern, self.text, re.IGNORECASE)
        self.call_put = option_match.group(1) if option_match else None

        return self.symbol is not None and self.strike is not None and self.call_put is not None