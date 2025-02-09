import logging

import selfcord

from .sender import MessageSender


class MessageReceiver(selfcord.Client):
    def __init__(self, config: dict, sender: MessageSender):
        self.logger = logging.getLogger('vfbot.rx')
        super().__init__()
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
        target_channel = config.get('target_channel_id')
        if target_channel:
            self.sender.forward_message(message, target_channel)
