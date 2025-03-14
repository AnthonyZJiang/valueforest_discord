import asyncio
import logging

import discord

from .utils import create_author_id_to_name_mapping
from .vfmessage import VFMessage
from .optionposition import OptionPosition


logger = logging.getLogger(__name__)

class MessageSender(discord.Client):
    def __init__(self, config: dict):
        self.config = config
        
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        
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
        logger.info(f'Sender logged on as {self.user}')

    async def send_message(self, message: VFMessage):
        channel = self.get_cached_channel(message.target_channel_id)
        logger.info(f"Send message: Sending message from {message.dc_msg.channel.name} to {channel.name}")
        await channel.send(message.content)
            
    async def delete_messages(self, message: discord.Message):
        if message:
            await message.delete()
    
    def forward_message_to_delete(self, message: discord.Message):
        asyncio.run_coroutine_threadsafe(
            self.delete_messages(message),
            self.loop
        )
            
    def forward_message(self, message: VFMessage):
        asyncio.run_coroutine_threadsafe(
            self.send_message(message),
            self.loop
        )
        
    async def new_option_position(self, option_position: OptionPosition):
        self.option_positions[option_position.get_id()] = option_position
        logger.info(f"On message: New option position from {option_position.author_name} id: {option_position.get_id()}")
        await option_position.create_thread(self.get_cached_channel(self.config['option_summary_channel_id']))
                
    async def handle_option_messages(self, message: VFMessage):
        logger.info(f"On message: Handling option messages from {message.author_name}:\n{message.dc_msg.content}")
        position = None
        if message.option_position and message.option_position.valid:
            if message.option_position.get_id() not in self.option_positions.keys():
                await self.new_option_position(message.option_position)               
            position = self.option_positions[message.option_position.get_id()]

        if not message.option_update:
            return
        
        if not position:
            position = self.find_option_position(message.dc_msg.author.id, message.option_update)
            
        if position:
            logger.info(f"On message: Updating option position {position.get_id()}")
            await position.add_to_thread(message.option_update, message.last_price)
        else:
            logger.warning(f"On message: No option position found.")
            await self.get_cached_channel(self.config['option_summary_channel_id']).send(message.option_update)
            
    def find_option_position(self, author_id: int, content: str, strike: int = None, option_type: str = None):
        for pos_id, position in self.option_positions.items():
            _author_id, _symbol, _strike, _option_type = pos_id.split(':')
            if str(author_id) != _author_id or _symbol not in content:
                continue
            if strike and str(strike) != _strike:
                continue
            if option_type and option_type.lower() != _option_type.lower():
                continue
            return position
        return None
    