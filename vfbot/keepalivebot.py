from __future__ import annotations
from typing import TYPE_CHECKING
import asyncio
import logging

import discord

from .mod.keepalive import KeepAlive

if TYPE_CHECKING:
    from .mod.vfconfig import VFConfig

logger = logging.getLogger(__name__)


class KeepAliveBot(discord.Client):
    def __init__(self, config: VFConfig):
        self.config = config
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents, max_messages=100)

        self._cached_channels = {}

        self._selfbot_monitor_task = None
        self.keepalive = KeepAlive(client=self)

    def stop(self) -> None:
        self.keepalive.stop()
        self.close()

    def get_cached_channel(self, channel_id: int) -> discord.TextChannel:
        if channel_id not in self._cached_channels:
            self._cached_channels[channel_id] = self.get_channel(channel_id)
        return self._cached_channels[channel_id]

    async def on_ready(self):
        logger.info("DC bot logged on as %s", self.user)
        self._selfbot_monitor_task = asyncio.create_task(self.keepalive.run())

    async def on_message(self, message: discord.Message):
        if message.author.id == self.user.id:
            return
        await self.keepalive.check_handshake(message)

    async def send_message(self, content: str, channel_id: int) -> discord.Message:
        channel = self.get_cached_channel(channel_id)
        # logger.debug("Sending message to %s", channel.name)
        return await channel.send(content)
