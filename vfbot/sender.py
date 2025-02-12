import asyncio
import logging

import discord
from .utils import ASHLEY_ID, ANGELA_ID, ocr_image_from_message, create_author_id_to_name_mapping
from .optionposition import OptionPosition


class MessageSender(discord.Client):
    def __init__(self, config: dict):
        self.config = config
        
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        
        self.logger = logging.getLogger(__name__)
        self.channels = {}  # type: dict[int, discord.TextChannel]
        self.author_names = create_author_id_to_name_mapping(config) # type: dict[int, str]
        
        self.option_positions = {} #type: dict[str, OptionPosition]
        
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
    def get_cached_channel(self, channel_id: int) -> discord.TextChannel:
        if channel_id not in self.channels:
            self.channels[channel_id] = self.get_channel(channel_id)
        return self.channels[channel_id]

    async def on_ready(self):
        self.logger.info(f'Sender logged on as {self.user}')

    async def send_message(self, message: discord.Message, channel_id: int):
        channel = self.get_cached_channel(channel_id)
        self.logger.info(f"Send message: Sending message {message.id} to {channel.name}:\n{message.content}")
        for attachment in message.attachments:
            await channel.send(attachment.url)
        if message.content:
            await channel.send(message.content)
        if message.author.id == ASHLEY_ID or message.author.id == ANGELA_ID:
            await self.handle_option_messages(message)
            
    def forward_message(self, message: discord.Message, channel_id: int):
        asyncio.run_coroutine_threadsafe(
            self.send_message(message, channel_id),
            self.loop
        )
        
    async def new_option_position(self, option_position: OptionPosition):
        self.option_positions[option_position.get_id()] = option_position
        self.logger.info(f"On message: New option position from {option_position.author_name} id: {option_position.get_id()}")
        await option_position.create_thread(self.get_cached_channel(self.config['option_summary_channel_id']))
                
    async def handle_option_messages(self, message: discord.Message):
        self.logger.info(f"On message: Handling option messages from {message.author.name}:\n{message.content}")
        loc = message.content.find(":new:")
        if loc > 8: # update message
            position = OptionPosition.from_text(message.content[loc:], message.author.id)
            pos_id = position.get_id()
            if position.valid:
                if pos_id not in self.option_positions:
                    await self.new_option_position(position)
                else:
                    position = self.option_positions[pos_id]
                message.content = message.content[:loc].split("||")[0]
                await position.add_to_thread(message)
                return
        elif loc >= 0: # new option position
            position = OptionPosition.from_text(message.content[loc:], message.author.id)
            if position.valid:
                await self.new_option_position(position)
                return
        else:
            position = self.find_option_position(message.author.id, message.content)
            if position:
                self.logger.info(f"On message: New update for {position.get_id()} from {message.author.name}")
                await position.add_to_thread(message)
                return
            
        if ".jpg" in message.content:
            ocr_result = ocr_image_from_message(message, self.config['ocr_api_key'])
            if ocr_result:
                symbol, strike, option_type, last_price = ocr_result
                position = self.find_option_position(message.author.id, symbol, strike, option_type)
                if position:
                    await position.add_to_thread(message, last_price)
                    return
                position = OptionPosition(author_id=message.author.id, 
                                          symbol=symbol, 
                                          strike=strike, 
                                          call_put=option_type, 
                                          open_price=last_price, 
                                          text=message.content)
                if position.valid:
                    await self.new_option_position(position)
                    return
        
        await self.get_cached_channel(self.config['option_summary_channel_id']).send(f'{self.author_names[message.author.id]}: {message.content}')
            
    def find_option_position(self, author_id: int, symbol: str, strike: int = None, option_type: str = None):
        for pos_id, position in self.option_positions.items():
            _author_id, _symbol, _strike, _option_type = pos_id.split(':')
            if str(author_id) != _author_id or _symbol not in symbol:
                continue
            if strike and str(strike) != _strike:
                continue
            if option_type and option_type.lower() != _option_type.lower():
                continue
            return position
        return None
    
    