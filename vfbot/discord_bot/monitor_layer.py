from __future__ import annotations
import logging
from datetime import datetime
import json
import os
from typing import TYPE_CHECKING
import discord

from .handshake import HandshakeInitiator
from .keepaliveconfig import keep_alive_config

if TYPE_CHECKING:
    from .keepalivebot import KeepAliveBot

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

        self.status_message_channel_id = keep_alive_config.status_message_channel_id
        if not self.status_message_channel_id:
            logger.error(f'Status message channel ID is not set')
            raise ValueError(f'Status message channel ID is not set')

        self.status_message_id = keep_alive_config.status_message_id # allow message id to be None as it may not have been created yet
        self._status_message: discord.Message = None

    async def spin_once(self):
        if self.hs_initiator.ok:
            logger.info(f"Handshake OK, updating status message")
            await self._update_status_message()
        await self.hs_initiator.send()

    def receive_handshake_response(self, message: discord.Message):
        self.hs_initiator.receive_response(message)

    async def _update_status_message(self):
        if not self._status_message:
            await self._initialise_status_message()
            if not self._status_message:
                logger.error(f"Fail to fetch status message")
                return
        current_time = int(datetime.now().timestamp())
        new_content = f"机器人上次心跳报告: <t:{current_time}>, <t:{current_time}:R>"
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
        return self._status_message
    
    async def _create_status_message(self, channel: discord.TextChannel):
        self._status_message = await channel.send(
            "机器人上次心跳报告: ..."
        )
        if self._status_message:
            logger.debug(f"Status message created.")
            self._status_message_id = self._status_message.id
            keep_alive_config.update(status_message_id=self._status_message.id)
