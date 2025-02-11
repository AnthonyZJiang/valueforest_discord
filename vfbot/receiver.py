import asyncio
import logging
import selfcord

from .sender import MessageSender
from .utils import message_retouch

class MessageReceiver(selfcord.Client):
    def __init__(self, config: dict, sender: MessageSender):
        super().__init__()
        self.logger = logging.getLogger('vfbot.rx')
        self.channels = config['channels']
        self.sender = sender
        
    async def on_ready(self):
        self.logger.info(f'Receiver logged on as {self.user}')
        self.channel = self.get_channel(1337816741052547145)
        hist = [a async for a in self.channel.history(limit=100)]
        for message in hist[::-1]:
            message.content = message_retouch(message)
            self.logger.info(f"got message {message.content}")
            self.sender.forward_message(message, -1)
            await asyncio.sleep(1)

    async def on_message(self, message: selfcord.Message):
        if message.channel.id not in self.channels:
            return
        config = self.channels[message.channel.id]
        if config['author_ids'] and message.author.id not in config['author_ids']:
            return
        self.logger.info(f"On message: Received message {message.id} from {message.author.name} in {message.channel.name}.")
        target_channel = config.get('target_channel_id')
        if target_channel:
            message.content = message_retouch(message)
            self.sender.forward_message(message, target_channel)
