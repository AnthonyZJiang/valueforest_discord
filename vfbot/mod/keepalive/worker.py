from __future__ import annotations
from typing import TYPE_CHECKING
import logging
from datetime import datetime, timedelta

import discord

from .actionlayer import ActionLayer, PullOnlyActionLayer
from .monitorlayer import MonitorLayer

if TYPE_CHECKING:
    from ...keepalivebot import KeepAliveBot
    from ..vfconfig import KeepAliveConfig, SelfbotProfile, VFConfig


logger = logging.getLogger(__name__)


class SelfbotWorker:
    def __init__(
        self,
        client: KeepAliveBot,
        profile: SelfbotProfile,
        config: VFConfig,
    ):
        self.id = profile.id
        self.keepalive: KeepAliveConfig = profile.keepalive
        self.monitor = MonitorLayer(
            client=client,
            selfbot_id=profile.id,
            keepalive=profile.keepalive,
            config=config,
        )
        self.action = ActionLayer(client=client, selfbot_id=profile.id)
        self.pull_only = PullOnlyActionLayer(client=client, selfbot_id=profile.id)

        self.action.start_bot()

    def stop(self) -> None:
        self.action.kill_bot()
        self.pull_only.kill_bot()

    async def spin_once(self) -> None:
        if self.pull_only.selfbot_ready or self.pull_only.selfbot_start_timeout:
            logger.warning(
                "Pull only bot for '%s' completed or timeout, killing...", self.id
            )
            self.pull_only.kill_bot()
        if self.action.selfbot_start_timeout:
            logger.warning("Selfbot start timeout for '%s', restarting bot...", self.id)
            self.action.restart_bot()
            return
        if not self.action.selfbot_ready:
            return
        if self.monitor.handshake_timeout:
            logger.warning("Handshake timeout for '%s', restarting bot...", self.id)
            self.monitor.reset_handshake_timeout()
            self.action.restart_bot()
            if self.monitor.last_ok_datetime and datetime.now() - self.monitor.last_ok_datetime > timedelta(
                seconds=self.keepalive.down_time_require_pull_only_seconds
            ):
                logger.warning(
                    "Down time require pull only for '%s', starting pull only bot...", self.id
                )
                self.pull_only.start_bot(self.monitor.last_ok_datetime)
            return
        await self.monitor.send_handshake()

    async def check_handshake(self, message: discord.Message) -> bool:
        if not self.monitor.hs_initiator.is_valid_handshake_message(message):
            return False
        await self.monitor.receive_handshake_response(message)
        return True
