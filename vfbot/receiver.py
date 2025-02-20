import logging
import asyncio
from datetime import datetime

import selfcord

from .sender import MessageSender
from .vfmessage import VFMessage
from .utils import get_config_value

logger = logging.getLogger(__name__)

class MessageReceiver(selfcord.Client):
    def __init__(self, config: dict, sender: MessageSender):
        super().__init__()
        self.ocr_api_key = get_config_value(config, 'ocr_api_key')
        self.channels = get_config_value(config, 'channels')
        if not self.ocr_api_key or not self.channels:
            raise ValueError('Missing required config values')
        self.sender = sender
        self.forward_history_since = None
        
    async def on_ready(self):
        logger.info(f'Receiver logged on as {self.user}')
        if self.forward_history_since:
            logger.info(f"Forwarding messages since {self.forward_history_since}")
            await self.forward_history_messages(after=self.forward_history_since)
            
    async def on_message(self, message: selfcord.Message):
        if message.channel.id not in self.channels:
            return
        config = self.channels[message.channel.id]
        if config['author_ids'] and message.author.id not in config['author_ids']:
            return
        logger.info(f"On message: Received message {message.id} from {message.author.display_name} in {message.channel.name}.")
        config['ocr_api_key'] = self.ocr_api_key
        msg = VFMessage(message, config)
        self.sender.forward_message(msg)
        
    async def forward_history_messages_by_channel(self, from_channel_id: int, to_channel_id: int, after: datetime, rate: int = 2):
        channel = self.get_channel(from_channel_id)
        hist = [msg async for msg in channel.history(limit=100, after=after, oldest_first=True)]
        for message in hist:
            config = self.channels[message.channel.id]
            if config['author_ids'] and message.author.id not in config['author_ids']:
                continue
            logger.info(f"History message: Forwarding message {message.id} from {message.author.display_name} in {message.channel.name} to {to_channel_id}.")
            config['target_channel_id'] = to_channel_id
            config['ocr_api_key'] = self.ocr_api_key
            msg = VFMessage(message, config)
            self.sender.forward_message(msg)
            await asyncio.sleep(rate)
        logger.info(f"Forwarded {len(hist)} messages from {from_channel_id} to {to_channel_id}.")
        
    async def forward_history_messages(self, after: datetime, rate: int = 2):
        channels = list(self.channels.keys())
        for id in channels:
            await self.forward_history_messages_by_channel(id, self.channels[id]['target_channel_id'], after, rate)
        logger.info(f"All history messages forwarded.")
        
    def set_config(self, message: selfcord.Message):
        config = self.channels[message.channel.id]
        if config['author_ids'] and message.author.id not in config['author_ids']:
            return
        logger.info(f"On message: Received message {message.id} from {message.author.display_name} in {message.channel.name}.")
        config['ocr_api_key'] = self.ocr_api_key
        return config
