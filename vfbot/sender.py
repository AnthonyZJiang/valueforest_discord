import asyncio
import logging
import datetime

import discord
from .vfmessage import VFMessage


logger = logging.getLogger(__name__)

class MessageSender(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        
        self.channels = {}  # type: dict[int, discord.TextChannel]
        self.status_message = None  # Store the status message
        self.status_update_task = None  # Store the background task
        
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
    def get_cached_channel(self, channel_id: int) -> discord.TextChannel:
        if channel_id not in self.channels:
            self.channels[channel_id] = self.get_channel(channel_id)
        return self.channels[channel_id]

    async def on_ready(self):
        logger.info(f'Sender logged on as {self.user}')

    async def send_message(self, message: VFMessage):
        for channel_id in message.target_channel_ids:
            channel = self.get_cached_channel(channel_id)
            logger.info(f"Send message: Sending message to {channel.name}")
            await channel.send(message.content, embeds=message.embeds)
            
    async def delete_messages(self, message: discord.Message):
        if message:
            await message.delete()
    
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

    async def edit_message(self, message_id: int, channel_id: int, new_content: str):
        """Edit an existing message with new content."""
        channel = self.get_cached_channel(channel_id)
        try:
            message = await channel.fetch_message(message_id)
            await message.edit(content=new_content)
            logger.info(f"Successfully edited message {message_id}")
        except discord.NotFound:
            logger.error(f"Message {message_id} not found")
        except discord.Forbidden:
            logger.error(f"Not allowed to edit message {message_id}")
        except Exception as e:
            logger.error(f"Error editing message: {str(e)}")

    async def update_status_message(self):
        """Background task to update the status message every minute."""
        while True:
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            new_content = f"Bot is alive! Last update: {current_time}"
            
            try:
                await self.edit_message(1370721723241992215, self.status_message.channel.id, new_content)
            except Exception as e:
                logger.error(f"Error updating status message: {str(e)}")
            
            await asyncio.sleep(60)  # Wait for 1 minute

    def start_status_updates(self, message: discord.Message):
        """Start periodic updates for the status message."""
        self.status_message = message
        if self.status_update_task is None:
            self.status_update_task = asyncio.run_coroutine_threadsafe(
                self.update_status_message(),
                self.loop
            )
            logger.info("Started status message updates")
