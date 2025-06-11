import asyncio
import logging
import datetime
import json
import os

import discord
from .vfmessage import VFMessage


STATUS_MESSAGE_CONFIG_FILE = "status_message.config.json"

logger = logging.getLogger(__name__)

class MessageSender(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        
        self.channels = {}  # type: dict[int, discord.TextChannel]
        self.status_message = None  # type: discord.Message | None
        self.status_update_task = None  # type: asyncio.Task | None
        
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
    def get_cached_channel(self, channel_id: int) -> discord.TextChannel:
        if channel_id not in self.channels:
            self.channels[channel_id] = self.get_channel(channel_id)
        return self.channels[channel_id]

    async def on_ready(self):
        logger.info(f'Sender logged on as {self.user}')
        
        await self.load_status_message_from_cached_file()
        if self.status_message:
            asyncio.run_coroutine_threadsafe(self.start_status_updates(), self.loop)

    async def send_message(self, message: VFMessage) -> discord.Message:
        for channel_id in message.target_channel_ids:
            channel = self.get_cached_channel(channel_id)
            logger.debug(f"Send message: Sending message to {channel.name}")
            return await channel.send(message.content, embeds=message.embeds)
    
    async def send_plain_message(self, content: str, channel_id: int) -> discord.Message:
        channel = self.get_cached_channel(channel_id)
        logger.debug(f"Send plain message: Sending message to {channel.name}")
        return await channel.send(content)
            
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
            if not self.status_message:
                await asyncio.sleep(5)
                continue
            current_time = int(datetime.datetime.now().timestamp())
            new_content = f"机器人上次心跳报告: <t:{current_time}>, <t:{current_time}:R>"
            
            try:
                await self.status_message.edit(content=new_content)
            except Exception as e:
                logger.error(f"Error updating status message: {str(e)}")
            
            await asyncio.sleep(59)  # Wait for 1 minute

    async def start_status_updates(self):
        """Start periodic updates for the status message."""
        if self.status_update_task is None:
            self.status_update_task = asyncio.run_coroutine_threadsafe(
                self.update_status_message(),
                self.loop
            )
            logger.info("Started status message updates")
    
    async def create_status_message(self, channel_id: int):
        self.status_message = await self.send_plain_message(
            "机器人上次心跳报告: ...",
            channel_id
        )
        if self.status_message:
            self.save_status_message_to_cached_file()
        
    def save_status_message_to_cached_file(self):
        with open(STATUS_MESSAGE_CONFIG_FILE, "w") as f:
            json.dump({
                "message_id": self.status_message.id,
                "channel_id": self.status_message.channel.id,
            }, f)
            
    async def load_status_message_from_cached_file(self):
        if not os.path.exists(STATUS_MESSAGE_CONFIG_FILE):
            return
        with open(STATUS_MESSAGE_CONFIG_FILE, "r") as f:
            data = json.load(f)
            if not data['message_id'] and data['channel_id']:
                await self.create_status_message(data['channel_id'])
            else:
                self.status_message = await self.get_cached_channel(data["channel_id"]).fetch_message(data["message_id"])
