"""
Monitor Layer Module
~~~~~~~~~~~~~~~~~~~~

The monitor layer is responsible for:
- Sending a handshake message to the keepalive bot
- Receiving a handshake response from the keepalive bot
- Updating the status message when a handshake is received
- Restarting the bot if the handshake is not received within 4 times of the monitor interval
"""

from __future__ import annotations
from typing import TYPE_CHECKING
import logging
from datetime import datetime
import os
import time

import discord

from .handshake import HandshakeInitiator

if TYPE_CHECKING:
    from ...keepalivebot import KeepAliveBot

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KEEPALIVE_CONFIG_FILE = os.path.join(ROOT_DIR, "keepalive.config.json")

logger = logging.getLogger(__name__)


class MonitorLayer:

    def __init__(
            self, 
            client: KeepAliveBot,
        ):
        self._client = client

        self.hs_initiator = HandshakeInitiator(client=self._client)

        self.status_message_channel_id = self._client.config.keepalive.status_message_channel_id
        if not self.status_message_channel_id:
            logger.error(f'Status message channel ID is not set')
            raise ValueError(f'Status message channel ID is not set')

        self.status_message_id = self._client.config.keepalive.status_message_id # allow message id to be None as it may not have been created yet
        self._status_message: discord.Message = None
        self._handshake_timeout_timestamp = None
        self._next_handshake_timestamp = None
        self.last_ok_datetime = None
        
    @property
    def handshake_timeout(self) -> bool:
        # logger.debug(f"{time.perf_counter():.2f} Next handshake time: {self._next_handshake_timestamp}, handshake timeout timestamp: {self._handshake_timeout_timestamp}")
        if self._next_handshake_timestamp is None or self._handshake_timeout_timestamp is None:
            return False # not yet sent handshake so not timeout
        if time.perf_counter() > self._handshake_timeout_timestamp:
            return True
        return False

    def reset_handshake_timeout(self):
        self._next_handshake_timestamp = None
        self._handshake_timeout_timestamp = None
        logger.debug(f"Handshake timeout reset")

    async def send_handshake(self):
        if self._next_handshake_timestamp and time.perf_counter() < self._next_handshake_timestamp:
            return
        await self.hs_initiator.send()
        self._next_handshake_timestamp = time.perf_counter() + self._client.config.keepalive.handshake_interval
        # logger.debug(f"{time.perf_counter():.2f} Next handshake timestamp set to {self._next_handshake_timestamp:.2f}")
        if self._handshake_timeout_timestamp is None:
            self._handshake_timeout_timestamp = time.perf_counter() + self._client.config.keepalive.handshake_timeout
            # logger.debug(f"{time.perf_counter():.2f} Handshake timeout timestamp set to {self._handshake_timeout_timestamp:.2f}")
            
    async def receive_handshake_response(self, message: discord.Message):
        ok = self.hs_initiator.check_response(message)
        if ok:
            await self._update_status_message()
            self.last_ok_datetime = datetime.now()
            self._handshake_timeout_timestamp = time.perf_counter() + self._client.config.keepalive.handshake_timeout
            # logger.debug(f"{time.perf_counter():.2f} Handshake timeout timestamp set to {self._handshake_timeout_timestamp:.2f}")

    async def _update_status_message(self):
        if not self._status_message:
            await self._initialise_status_message()
            if not self._status_message:
                logger.error(f"Fail to fetch status message")
                return
        current_time = int(datetime.now().timestamp())
        new_content = f"机器人上次握手成功: <t:{current_time}>, <t:{current_time}:R>"
        try:
            await self._status_message.edit(content=new_content)
        except Exception as e:
            logger.error(f"Error updating status message: {str(e)}", exc_info=True)

    async def _initialise_status_message(self) -> discord.Message:
        channel = self._client.get_cached_channel(self.status_message_channel_id)
        if self.status_message_id:
            self._status_message = await channel.fetch_message(self.status_message_id)
        else:
            self._status_message = await self._create_status_message(channel)
    
    async def _create_status_message(self, channel: discord.TextChannel):
        self._status_message = await channel.send(
            "机器人上次握手成功: 等待机器人第一次握手..."
        )
        if self._status_message:
            logger.debug(f"Status message created.")
            self._status_message_id = self._status_message.id
            self._client.config.update(status_message_id=self._status_message.id)
            self._client.config.save()
