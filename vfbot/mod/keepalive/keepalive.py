from __future__ import annotations
from typing import TYPE_CHECKING
import logging
import asyncio

import discord

from .worker import SelfbotWorker

if TYPE_CHECKING:
    from ...keepalivebot import KeepAliveBot


logger = logging.getLogger(__name__)


class KeepAlive:
    def __init__(self, client: KeepAliveBot) -> None:
        self._client = client
        self._workers: dict[str, SelfbotWorker] = {}

        for profile_id, profile in client.config.selfbots.items():
            if not profile.keepalive.enabled:
                logger.warning(
                    "Selfbot '%s' has keepalive disabled, skipping supervision.", profile_id
                )
                continue
            self._workers[profile_id] = SelfbotWorker(
                client=self._client,
                profile=profile,
                config=client.config,
            )

        if not self._workers:
            raise ValueError("No selfbots with keepalive enabled found in config")

        self._stop_requested = False

    def stop(self) -> None:
        for worker in self._workers.values():
            worker.stop()
        self._stop_requested = True

    async def run(self) -> None:
        while not self._client.is_closed() or self._stop_requested:
            try:
                await self._spin_once()
            except Exception:
                logger.error("Error occurred in keepalive loop", exc_info=True)
            await asyncio.sleep(1)

    async def check_handshake(self, message: discord.Message) -> None:
        for worker in self._workers.values():
            if await worker.check_handshake(message):
                return

    async def _spin_once(self) -> None:
        for worker in self._workers.values():
            await worker.spin_once()
