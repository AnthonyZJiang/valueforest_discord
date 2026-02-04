from __future__ import annotations
from typing import TYPE_CHECKING
import asyncio
import logging

import discord

from .keepalivebot import KeepAliveBot
from .telegrambot import TeleCordBot

if TYPE_CHECKING:
    from .mod.vfconfig import VFConfig

logger = logging.getLogger(__name__)


class DiscordBot(discord.Client, KeepAliveBot, TeleCordBot):
    def __init__(self, config: VFConfig):
        intents = discord.Intents.default()
        intents.message_content = True
        discord.Client.__init__(self, intents=intents, max_messages=100)
        KeepAliveBot.__init__(self, config)
        TeleCordBot.__init__(self, config)

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
        await self.on_message_keepalive(message)
        await self.on_message_telegram(message)
