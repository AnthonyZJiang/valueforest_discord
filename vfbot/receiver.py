import logging
import asyncio
from datetime import datetime
import random
import selfcord

from .sender import MessageSender
from .vfmessage import VFMessage
from .utils import get_config_value

logger = logging.getLogger(__name__)

class MessageReceiver(selfcord.Client):
    def __init__(self, config: dict, sender: MessageSender):
        super().__init__()
        self.channels = get_config_value(config, 'channels')
        if not self.channels:
            logger.warning('No channels to monitor.')
            return
        
        logger.info("Config loaded. %d channels to monitor.", len(self.channels))
        self.sender = sender
        self.pull_since = None
        
    async def on_ready(self):
        if not self.channels:
            logger.warning('No channels to monitor.')
            await self.close()
            return
        logger.info(f'Receiver logged on as {self.user}')
        if self.pull_since:
            logger.info(f"Forwarding messages since {self.pull_since}")
            await self.forward_history_messages(after=self.pull_since)
        
    async def delete_duplicate_messages(self, since: datetime):
        # usage: await self.delete_duplicate_messages(since=datetime(2025, 3, 10, 19, 0))
        messages = []
        for channel in self.channels:
            channel_id = self.channels[channel]['target_channel_id']
            channel = self.get_channel(channel_id)
            hist = [msg async for msg in channel.history(limit=100, after=since, oldest_first=True)]
            for message in hist:
                if message.content in messages:
                    self.sender.forward_message_to_delete(message)
                    await message.delete()
                    logger.info(f"Deleted duplicate message from {channel.name}: {message.content}")
                    await asyncio.sleep(random.uniform(2, 5))
                else:
                    messages.append(message.content)
        logger.info(f"Duplicate messages deleted.")
            
    async def on_message(self, message: selfcord.Message):
        if not self.channels:
            return
        if str(message.channel.id) not in self.channels:
            return
        config = self.channels[str(message.channel.id)]
        if config['author_ids'] and message.author.id not in config['author_ids']:
            return
        logger.info(f"On message: Received message {message.id} from {message.author.display_name} in {message.channel.name}.")
        msg = VFMessage.from_dc_msg(message, config)
        self.sender.forward_message(msg)
        
    async def forward_history_messages_by_channel(self, from_channel_id: int, after: datetime, rate: int = 2):
        logger.info(f"Forwarding history messages from {from_channel_id} after {after}.")
        channel = self.get_channel(from_channel_id)
        hist = [msg async for msg in channel.history(limit=100, after=after, oldest_first=True)]
        for message in hist:
            await self.on_message(message)
            await asyncio.sleep(rate)
        logger.info(f"Forwarded {len(hist)} messages from {from_channel_id}.")
        
    async def forward_history_messages(self, after: datetime, rate: int = 2):
        channels = list(self.channels.keys())
        for id in channels:
            await self.forward_history_messages_by_channel(int(id), after, rate)
        logger.info(f"All history messages forwarded.")
        