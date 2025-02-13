import logging
import asyncio
import selfcord

from .sender import MessageSender
from .vfmessage import VFMessage

class MessageReceiver(selfcord.Client):
    def __init__(self, config: dict, sender: MessageSender):
        super().__init__()
        self.logger = logging.getLogger('vfbot.rx')
        self.ocr_api_key = config['ocr_api_key']
        self.channels = config['channels']
        self.sender = sender
        
    async def on_ready(self):
        self.logger.info(f'Receiver logged on as {self.user}')
            
    async def on_message(self, message: selfcord.Message):
        if message.channel.id not in self.channels:
            return
        config = self.channels[message.channel.id]
        if config['author_ids'] and message.author.id not in config['author_ids']:
            return
        self.logger.info(f"On message: Received message {message.id} from {message.author.name} in {message.channel.name}.")
        config['ocr_api_key'] = self.ocr_api_key
        msg = VFMessage(message, config)
        self.sender.forward_message(msg)
        
    async def forward_channel_messages(self, from_channel_id: int, to_channel_id: int, limit: int = 100, rate: int = 10):
        channel = self.get_channel(from_channel_id)
        hist = [msg async for msg in channel.history(limit=limit)]
        for message in hist[::-1]:
            config = self.channels[message.channel.id]
            config['target_channel_id'] = to_channel_id
            config['ocr_api_key'] = self.ocr_api_key
            msg = VFMessage(message, config)
            self.sender.forward_message(msg)
            await asyncio.sleep(rate)
