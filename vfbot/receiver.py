import logging
import selfcord
import asyncio

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
            
    async def on_message(self, message: selfcord.Message):
        if message.channel.id not in self.channels:
            return
        config = self.channels[message.channel.id]
        if config['author_ids'] and message.author.id not in config['author_ids']:
            return
        self.logger.info(f"On message: Received message {message.id} from {message.author.display_name} in {message.channel.name}.")
        target_channel = config.get('target_channel_id')
        if target_channel:
            if config['show_name']:
                name = config['author_name_override'] if config['author_name_override'] else message.author.name
                message.content = f"【{name}】{message.content}"
            message_retouch(message)
            self.sender.forward_message(message, target_channel)
 