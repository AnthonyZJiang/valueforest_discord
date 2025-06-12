import asyncio
import logging
import datetime
import json
import os

import discord
from .vfmessage import VFMessage


STATUS_MESSAGE_CONFIG_FILE = "status_message.config.json"

logger = logging.getLogger(__name__)

class MessageSender(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        
        self.channels = {}  # type: dict[int, discord.TextChannel]
        
        self.status_message = None  # type: discord.Message | None
        self.status_update_task = None  # type: asyncio.Task | None
        
        self.cross_check_heartbeat_interval = None  # type: int | None
        self.cross_check_heartbeat_message_prefix = None  # type: str | None
        self.cross_check_heartbeat_channel_id = None  # type: int | None
        self.cross_check_update_task = None  # type: asyncio.Task | None
        
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
    def get_cached_channel(self, channel_id: int) -> discord.TextChannel:
        if channel_id not in self.channels:
            self.channels[channel_id] = self.get_channel(channel_id)
        return self.channels[channel_id]

    async def on_ready(self):
        logger.info(f'Sender logged on as {self.user}')

    async def send_message(self, message: VFMessage) -> discord.Message:
        for channel_id in message.target_channel_ids:
            channel = self.get_cached_channel(channel_id)
            logger.debug(f"Send message: Sending message to {channel.name}")
            return await channel.send(message.content, embeds=message.embeds)
    
    async def send_plain_message(self, content: str, channel_id: int) -> discord.Message:
        channel = self.get_cached_channel(channel_id)
        logger.debug(f"Send plain message: Sending message to {channel.name}")
        return await channel.send(content)
            
    async def delete_messages(self, message: discord.Message):
        if message:
            await message.delete()
            
    async def modify_message(self, message: discord.Message, new_content: str):
        if message:
            await message.edit(content=new_content)
    
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
