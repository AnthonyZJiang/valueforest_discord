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
