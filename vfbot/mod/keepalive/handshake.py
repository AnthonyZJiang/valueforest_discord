from __future__ import annotations
from typing import TYPE_CHECKING
import logging
from datetime import datetime, timedelta, timezone

import discord
from discord_webhook import DiscordWebhook

if TYPE_CHECKING:
    from ...keepalivebot import KeepAliveBot
    from ...selfbot import Selfbot


logger = logging.getLogger(__name__)


class HandshakeInitiator:

    def __init__(self, client: KeepAliveBot):
        self._client = client
        self.name = client.config.keepalive.handshake_name
        self.responder_name = self.name + " Responder"
        self.channel_id = client.config.keepalive.handshake_channel_id
        self.interval = client.config.keepalive.handshake_interval

        self._ts = None
        self._sent = False
        self._response_ok = False

    @property
    def ok(self) -> bool:
        return self._response_ok

    def is_valid_handshake_message(self, message: discord.Message) -> bool:
        return message.channel.id == self.channel_id and message.content.startswith(
            self.responder_name
        )

    async def send(self) -> None:
        ts = int(datetime.now().timestamp())
        if not self._ts or ts - self._ts >= self.interval:
            self._ts = ts
        else:
            return
        message = await self._client.send_message(
            f"{self.name} Initiator 🤝: <t:{ts}> TS {ts}", self.channel_id
        )
        if message:
            self._response_ok = False

    def check_response(self, message: discord.Message) -> bool:
        if not self.is_valid_handshake_message(message):
            return False
        parts = message.content.split("TS ")
        if len(parts) != 2:
            logger.error("Invalid handshake message: %s", message.content)
            return False
        handshake_timestamp = int(parts[1].strip())
        if handshake_timestamp != self._ts:
            logger.error("Handshake timestamp mismatch: %s != %s", handshake_timestamp, self._ts)
            return False
        logger.debug("Handshake OK with %s", message.author.display_name)
        self._response_ok = True

        return True


class HandshakeResponder:

    def __init__(self, client: Selfbot):
        self._client = client
        self.name = client.config.keepalive.handshake_name
        self.initiator_name = self.name + " Initiator"
        self.channel_id = client.config.keepalive.handshake_channel_id
        self.interval = (
            client.config.keepalive.handshake_interval * 0.99
        )  # allow a small buffer to avoid timestamp mismatch
        self.webhook_url = client.config.keepalive.handshake_response_webhook
        if not self.webhook_url:
            raise ValueError("No webhook URL provided")
        self.webhook = DiscordWebhook(url=self.webhook_url)
        self.webhook.username = client.user.display_name
        self.webhook.avatar_url = client.user.display_avatar.url

    def is_valid_handshake_message(self, message: discord.Message) -> bool:
        return message.channel.id == self.channel_id and message.content.startswith(
            self.initiator_name
        )

    def respond(self, message: discord.Message) -> None:
        if message.created_at - datetime.now(timezone.utc) > timedelta(seconds=self.interval):
            return
        ts = message.content.split("TS ")[1].strip()
        content = f"{self.name} Responder 🤝: <t:{ts}> TS {ts}"
        # logger.debug("Handshake response sent")
        if self.webhook:
            self.webhook.content = content
            self.webhook.execute()
        else:
            pass  # Not implemented.
        return
