import asyncio
import logging

import discord


class MessageSender(discord.Client):
    def __init__(self):
        self.logger = logging.getLogger(__name__)
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
