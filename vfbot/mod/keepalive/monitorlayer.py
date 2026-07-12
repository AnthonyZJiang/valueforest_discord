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
import asyncio
import logging
from datetime import datetime
import time

import discord
from discord_webhook import DiscordWebhook

from .handshake import HandshakeInitiator

if TYPE_CHECKING:
    from ...keepalivebot import KeepAliveBot
    from ..vfconfig import KeepAliveConfig, VFConfig


logger = logging.getLogger(__name__)


class MonitorLayer:

    def __init__(
        self,
        client: KeepAliveBot,
        selfbot_id: str,
        keepalive: KeepAliveConfig,
        config: VFConfig,
    ):
        self._client = client
        self._selfbot_id = selfbot_id
        self._config = config
        self._keepalive = keepalive

        self.hs_initiator = HandshakeInitiator(client=self._client, keepalive=keepalive)

        self.status_message_channel_id = keepalive.status_message_channel_id
        self.status_message_webhook = keepalive.status_message_webhook
        if not self._has_status_target():
            logger.warning(
                "Status message channel ID or webhook is not set for selfbot '%s'.",
                selfbot_id,
            )

        self.status_message_id = keepalive.status_message_id
        self._status_message: discord.Message = None
        self._handshake_timeout_timestamp = None
        self._next_handshake_timestamp = None
        self.last_ok_datetime = None

    def _has_status_target(self) -> bool:
        return bool(self.status_message_webhook or self.status_message_channel_id)

    def _use_webhook_status(self) -> bool:
        return bool(self.status_message_webhook)

    def _waiting_status_content(self) -> str:
        return f"[{self._selfbot_id}] 机器人上次握手成功: 等待机器人第一次握手..."

    def _ok_status_content(self, current_time: int) -> str:
        return (
            f"[{self._selfbot_id}] 机器人上次握手成功: "
            f"<t:{current_time}>, <t:{current_time}:R>"
        )

    @property
    def handshake_timeout(self) -> bool:
        if self._next_handshake_timestamp is None or self._handshake_timeout_timestamp is None:
            return False
        if time.perf_counter() > self._handshake_timeout_timestamp:
            return True
        return False

    def reset_handshake_timeout(self):
        self._next_handshake_timestamp = None
        self._handshake_timeout_timestamp = None
        logger.debug("Handshake timeout reset for selfbot '%s'", self._selfbot_id)

    async def send_handshake(self):
        if self._next_handshake_timestamp and time.perf_counter() < self._next_handshake_timestamp:
            return
        await self.hs_initiator.send()
        self._next_handshake_timestamp = (
            time.perf_counter() + self._keepalive.handshake_interval
        )
        if self._handshake_timeout_timestamp is None:
            self._handshake_timeout_timestamp = (
                time.perf_counter() + self._keepalive.handshake_timeout
            )

    async def receive_handshake_response(self, message: discord.Message):
        ok = self.hs_initiator.check_response(message)
        if ok:
            await self._update_status_message()
            self.last_ok_datetime = datetime.now()
            self._handshake_timeout_timestamp = (
                time.perf_counter() + self._keepalive.handshake_timeout
            )

    async def _update_status_message(self):
        if not self._has_status_target():
            return

        current_time = int(datetime.now().timestamp())
        new_content = self._ok_status_content(current_time)

        if self._use_webhook_status():
            await self._update_status_message_webhook(new_content)
            return

        if not self._status_message:
            await self._initialise_status_message()
            if not self._status_message:
                logger.error("Fail to fetch status message for selfbot '%s'", self._selfbot_id)
                return
        try:
            await self._status_message.edit(content=new_content)
        except Exception:
            logger.error(
                "Error updating status message for selfbot '%s':", self._selfbot_id, exc_info=True
            )

    async def _update_status_message_webhook(self, content: str) -> None:
        if not self.status_message_id:
            await self._create_status_message_webhook(content)
            return
        try:
            await asyncio.to_thread(self._edit_status_message_webhook, content)
        except Exception:
            logger.warning(
                "Failed to edit webhook status message for selfbot '%s', recreating...",
                self._selfbot_id,
                exc_info=True,
            )
            self.status_message_id = None
            await self._create_status_message_webhook(content)

    def _edit_status_message_webhook(self, content: str) -> None:
        webhook = DiscordWebhook(
            url=self.status_message_webhook,
            id=self.status_message_id,
            content=content,
        )
        webhook.edit()

    async def _create_status_message_webhook(self, content: str) -> None:
        message_id = await asyncio.to_thread(self._send_status_message_webhook, content)
        if not message_id:
            logger.error(
                "Failed to create webhook status message for selfbot '%s'", self._selfbot_id
            )
            return
        logger.debug("Webhook status message created for selfbot '%s'.", self._selfbot_id)
        self.status_message_id = message_id
        self._config.update(
            self._selfbot_id,
            keepalive={"status_message_id": message_id},
        )

    def _send_status_message_webhook(self, content: str) -> int | None:
        webhook = DiscordWebhook(url=self.status_message_webhook, content=content)
        response = webhook.execute()
        if response is None:
            return None
        if webhook.id:
            return webhook.id
        try:
            return int(response.json()["id"])
        except (AttributeError, KeyError, TypeError, ValueError):
            return None

    async def _initialise_status_message(self) -> discord.Message:
        channel = self._client.get_cached_channel(self.status_message_channel_id)
        if self.status_message_id:
            self._status_message = await channel.fetch_message(self.status_message_id)
        else:
            self._status_message = await self._create_status_message(channel)

    async def _create_status_message(self, channel: discord.TextChannel):
        self._status_message = await channel.send(self._waiting_status_content())
        if self._status_message:
            logger.debug("Status message created for selfbot '%s'.", self._selfbot_id)
            self.status_message_id = self._status_message.id
            self._config.update(
                self._selfbot_id,
                keepalive={"status_message_id": self._status_message.id},
            )
