import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging

import discord
import selfcord

VERSION: str = 'SMK-0.0.0'

discord.utils.setup_logging(root=False)
class MessageSender(discord.Client):
    def __init__(self):
        self.logger = logging.getLogger('vfbot.tx')
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.channels = {}  # type: dict[int, discord.TextChannel]
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    async def on_ready(self):
        self.logger.info(f'Sender logged on as {self.user}')

    async def send_message(self, message: discord.Message, channel_id: int):
        if channel_id not in self.channels:
            self.channels[channel_id] = self.get_channel(channel_id)
        channel = self.channels[channel_id]
        self.logger.info(f"Send message: Sending message {message.id} to {channel.name}")
        await channel.send(message.content)
        for attachment in message.attachments:
            await channel.send(attachment.url)

    def forward_message(self, message: discord.Message, channel_id: int):
        asyncio.run_coroutine_threadsafe(
            self.send_message(message, channel_id),
            self.loop
        )


class MessageReceiver(selfcord.Client):
    def __init__(self, config: dict, sender: MessageSender):
        self.logger = logging.getLogger('vfbot.rx')
        super().__init__()
        self.channels = config['channels']
        self.sender = sender
        
    async def on_ready(self):
        self.logger.info(f'Receiver logged on as {self.user}')

    async def on_message(self, message: discord.Message):
        if message.channel.id not in self.channels:
            return
        config = self.channels[message.channel.id]
        if config['author_ids'] and message.author.id not in config['author_ids']:
            return
        self.logger.info(f"On message: Received message {message.id} from {message.author.name} in {message.channel.name}.")
        target_channel = config.get('target_channel_id')
        if target_channel:
            self.sender.forward_message(message, target_channel)


if __name__ == '__main__':
    config = json.load(open('config.json'))
    config['channels'] = {int(k): v for k, v in config['channels'].items()}
    
    sender = MessageSender()
    receiver = MessageReceiver(config=config, sender=sender)
    executor = ThreadPoolExecutor(max_workers=2)
    
    sender_future = executor.submit(sender.run, config['bot_token'])
    receiver_future = executor.submit(receiver.run, config['self_token'])

    try:
        # Wait for both futures to complete (or raise an exception)
        sender_future.result()
        receiver_future.result()
    except KeyboardInterrupt:
        print("Shutting down...")
