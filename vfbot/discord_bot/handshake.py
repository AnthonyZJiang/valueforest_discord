from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone
from discord_webhook import DiscordWebhook

from typing import TYPE_CHECKING

import discord

from .keepaliveconfig import keep_alive_config

if TYPE_CHECKING:
    from .keepalivebot import KeepAliveBot

logger = logging.getLogger(__name__)


class HandshakeInitiator:

    def __init__(self, client: KeepAliveBot):
        self.name = keep_alive_config.handshake_name
        self.channel_id = keep_alive_config.handshake_channel_id
        self.interval = keep_alive_config.handshake_interval
        self._client = client

        self._ts = None
        self._sent = False
        self._response_ok = False

    @property
    def ok(self) -> bool:
        return self._response_ok and self._sent

    async def send(self) -> None:
        ts = int(datetime.now().timestamp())
        if not self._ts or ts - self._ts >= self.interval:
            self._ts = ts
        else:
            return
        self._sent = False
        message = await self._client.send_message(f"{self.name} Initiator 🤝: <t:{ts}> TS {ts}", self.channel_id)
        if message:
            self._sent = True
            self._response_ok = False

    def receive_response(self, message: discord.Message) -> None:
        if message.channel.id != self.channel_id or not message.content.startswith(f"{self.name} Responder"):
            return
        parts = message.content.split("TS ")
        if len(parts) != 2:
            logger.error(f'Invalid handshake message: {message.content}')
            return
        handshake_timestamp = int(parts[1].strip())
        if handshake_timestamp != self._ts:
            logger.error(f'Handshake timestamp mismatch: {handshake_timestamp} != {self._ts}')
            return
        logger.info(f"Handshake response received from {message.author.display_name}")
        self._response_ok = True


class HandshakeResponder:

    def __init__(self, client: KeepAliveBot = None):
        self.name = keep_alive_config.handshake_name
        self.channel_id = keep_alive_config.handshake_channel_id
        self.interval = keep_alive_config.handshake_interval * 0.99 # allow a small buffer to avoid timestamp mismatch
        self.webhook_url = keep_alive_config.handshake_response_webhook
        if not self.webhook_url:
            self.webhook = None
        else:
            self.webhook = DiscordWebhook(url=self.webhook_url)
            self.webhook.username = client.user.display_name
            self.webhook.avatar_url = client.user.display_avatar.url
        self._client = client

        if not self.webhook and not self._client:
            raise ValueError("Either a webhook or a client is required")

    async def respond(self, message: discord.Message) -> bool:
        if message.channel.id != self.channel_id or not message.content.startswith(self.name):
            return False
        if message.created_at - datetime.now(timezone.utc) > timedelta(seconds=self.interval):
            return True
        ts = message.content.split("TS ")[1].strip()
        content = f"{self.name} Responder 🤝: <t:{ts}> TS {ts}"
        logger.debug("Handshake received.")
        if self.webhook:
            self.webhook.content = content
            self.webhook.execute()
        else:
            await self._client.send_message(content, self.channel_id)
        return True