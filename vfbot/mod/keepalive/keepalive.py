from __future__ import annotations
from typing import TYPE_CHECKING
import logging
import asyncio
from datetime import datetime, timedelta

from .actionlayer import ActionLayer, PullOnlyActionLayer
from .monitorlayer import MonitorLayer

if TYPE_CHECKING:
    from ...keepalivebot import KeepAliveBot
    import discord


logger = logging.getLogger(__name__)

class KeepAlive:
    def __init__(self, client: KeepAliveBot) -> None:
        self._client = client
        self._action_layer = ActionLayer(client=self._client)
        self._monitor_layer = MonitorLayer(client=self._client)
        self._pull_only_action_layer = PullOnlyActionLayer(client=self._client)
        
        self._action_layer.start_bot()
        self._stop_requested = False
        
    def stop(self) -> None:
        self._action_layer.kill_bot()
        self._pull_only_action_layer.kill_bot()
        self._stop_requested = True

    async def run(self) -> None:
        while not self._client.is_closed() or self._stop_requested:
            try:
                await self._spin_once()
            except Exception as e:
                logger.error(f'Error occurred in keepalive loop: {e}', exc_info=True)
            await asyncio.sleep(1)
            
    async def check_handshake(self, message: discord.Message) -> None:
        await self._monitor_layer.receive_handshake_response(message)
    
    async def _spin_once(self) -> None:
        if self._pull_only_action_layer.selfbot_ready or self._pull_only_action_layer.selfbot_start_timeout:
            logger.warning("Pull only bot completed or timeout, killing...")
            self._pull_only_action_layer.kill_bot()
        if self._action_layer.selfbot_start_timeout:
            logger.warning("Selfbot start timeout, restarting bot...")
            self._action_layer.restart_bot()
            return
        if not self._action_layer.selfbot_ready:
            return
        if self._monitor_layer.handshake_timeout:
            logger.warning("Handshake timeout, restarting bot...")
            self._monitor_layer.reset_handshake_timeout()
            self._action_layer.restart_bot()
            if datetime.now() - self._monitor_layer.last_ok_datetime > timedelta(seconds=self._client.config.keepalive.down_time_require_pull_only_seconds):
                logger.warning("Down time require pull only, starting pull only bot...")
                self._pull_only_action_layer.start_bot(self._monitor_layer.last_ok_datetime)
            return
        await self._monitor_layer.send_handshake()
        
    
    