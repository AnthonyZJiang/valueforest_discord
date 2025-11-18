import asyncio
import logging
import discord

from .monitor_layer import MonitorLayer
from .keepaliveconfig import keep_alive_config

logger = logging.getLogger(__name__)

class KeepAliveBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents, max_messages=100)

        self._cached_channels = {}
        
        self._selfbot_monitor_task = None
        self._monitor_layer = MonitorLayer(client=self)
        
    def get_cached_channel(self, channel_id: int) -> discord.TextChannel:
        if channel_id not in self._cached_channels:
            self._cached_channels[channel_id] = self.get_channel(channel_id)
        return self._cached_channels[channel_id]

    async def on_ready(self):
        logger.info(f'DC bot logged on as {self.user}')
        # Start periodic message task if configured
        self._selfbot_monitor_task = asyncio.create_task(self._selfbot_monitor_loop())
    
    async def on_message(self, message: discord.Message):
        logger.debug(f"Received message: {message.content} from {message.author.display_name} in {message.channel.id}; {message.channel.id == self._monitor_layer.hs_initiator.channel_id}")
        if message.author.id == self.user.id:
            return
        if message.channel.id == self._monitor_layer.hs_initiator.channel_id:
            logger.info(f"Handshake response received from {message.author.display_name}")
            self._monitor_layer.receive_handshake_response(message)
    
    async def send_message(self, content: str, channel_id: int) -> discord.Message:
        channel = self.get_cached_channel(channel_id)
        logger.debug(f"Send plain message: Sending message to {channel.name}")
        return await channel.send(content)
    
    async def _selfbot_monitor_loop(self):
        """Background task that sends a message every configured interval."""
        await self.wait_until_ready()
        while not self.is_closed():
            try:
                await self._monitor_layer.spin_once()
            except Exception as e:
                logger.error(f'Error occurred in selfbot monitor loop: {e}', exc_info=True)
            await asyncio.sleep(keep_alive_config.monitor_interval)
