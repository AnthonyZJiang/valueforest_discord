import asyncio
import logging

import discord
from .utils import ASHLEY_ID, ANGELA_ID
from .optionposition import OptionPosition


class MessageSender(discord.Client):
    def __init__(self, config: dict):
        self.config = config
        
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        
        self.logger = logging.getLogger(__name__)
        self.channels = {}  # type: dict[int, discord.TextChannel]
        self.option_positions = {} #type: dict[str, OptionPosition]
        
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
    def get_cached_channel(self, channel_id: int) -> discord.TextChannel:
        if channel_id not in self.channels:
            self.channels[channel_id] = self.get_channel(channel_id)
        return self.channels[channel_id]

    async def on_ready(self):
        self.logger.info(f'Sender logged on as {self.user}')

    async def send_message(self, message: discord.Message, channel_id: int):
        if channel_id == -1:
            await self.handle_option_messages(message)
            return
        channel = self.get_cached_channel(channel_id)
        self.logger.info(f"Send message: Sending message {message.id} to {channel.name}")
        for attachment in message.attachments:
            await channel.send(attachment.url)
        if message.content:
            await channel.send(message.content)
        if message.author.id == ASHLEY_ID or message.author.id == ANGELA_ID:
            await self.handle_option_messages(message)
            
    def forward_message(self, message: discord.Message, channel_id: int):
        asyncio.run_coroutine_threadsafe(
            self.send_message(message, channel_id),
            self.loop
        )
            
    async def send_new_option_summary(self, position: OptionPosition):
        channel = self.get_cached_channel(self.config['option_summary_channel_id'])
        self.logger.info(f"Sending new option summary to {channel.name}")
        message = await channel.send(str(position))
        position.dc_message = message
        
    async def update_option_summary(self, position: OptionPosition):
        self.logger.info(f"Updating option summary for {position.get_id()}")
        await position.dc_message.edit(content=str(position))
        
    async def send_option_summary_message(self, message: discord.Message):
        channel = self.get_cached_channel(self.config['option_summary_channel_id'])
        await channel.send(f':hourglass:{message.created_at.strftime("%H:%M")}:hourglass:{message.content}')
                
    async def handle_option_messages(self, message: discord.Message):
        loc = message.content.find(":new:")
        if loc > 5: # update message
            position = OptionPosition(message.content[loc:], message.author.id, None)
            pos_id = position.get_id()
            if position.valid:
                if pos_id not in self.option_positions:
                    self.option_positions[pos_id] = position
                    self.logger.info(f"On message: New option position from {message.author.name} id: {pos_id}")
                    await self.send_new_option_summary(position)
                else:
                    position = self.option_positions[pos_id]
                message.content = message.content[:loc].split("||")[0]
                position.add_update(message)
                await self.update_option_summary(position)
                return
        elif loc >= 0: # new option position
            position = OptionPosition(message.content[loc:], message.author.id, message.created_at)
            if position.valid:
                self.option_positions[position.get_id()] = position
                self.logger.info(f"On message: New option position from {message.author.name} id: {position.get_id()}")
                await self.send_new_option_summary(position)
            return
        else:
            for pos_id, position in self.option_positions.items():
                author_id, symbol, _, _ = pos_id.split(':')
                if author_id != str(message.author.id):
                    continue
                if symbol not in message.content:
                    continue
                position.add_update(message)
                self.logger.info(f"On message: New update for {pos_id} from {message.author.name}")
                await self.update_option_summary(position)
                return
        if "https:" in message.content:
            # send attachments to option summary channel anyways.
            await self.send_option_summary_message(message)