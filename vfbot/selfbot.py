from __future__ import annotations
from typing import TYPE_CHECKING
import logging
from datetime import datetime, timedelta
import asyncio

import selfcord
from discord_webhook import DiscordWebhook

from .mod.keepalive.handshake import HandshakeResponder
from .mod.llm.gpt import LLMAnalyser
from .mod.vfmessage import VFMessage

if TYPE_CHECKING:
    from .mod.vfconfig import VFConfig


logger = logging.getLogger(__name__)

class Selfbot(selfcord.Client):

    def __init__(self, config: VFConfig):
        super().__init__(max_messages=100)
        self.config = config
        self.channels = config.repost_settings
        
        self.forward_history_since = None
        self.forward_history_before = None
        self.forward_history_only = False
        self.forward_history_from_channels = None
        self.handshake_responder = None
        
        if config.llm_config:
            self.llm_analyser = LLMAnalyser(config.llm_config)
        else:
            self.llm_analyser = None
        
    async def on_ready(self):
        logger.info(f'Selfbot ready, logged on as {self.user}{" , forward history only" if self.forward_history_only else ""}')
        print("Selfbot ready")
        self.handshake_responder = HandshakeResponder(client=self)
        if self.forward_history_since:
            if isinstance(self.forward_history_since, str):
                self.forward_history_since = datetime.fromisoformat(self.forward_history_since)
            if isinstance(self.forward_history_before, str):
                self.forward_history_before = datetime.fromisoformat(self.forward_history_before)
            logger.info(f"Forwarding messages since {self.forward_history_since}")
            await self.forward_history_messages(after=self.forward_history_since, before=self.forward_history_before)
        else:
            import asyncio
            timeout = 15
            await asyncio.sleep(timeout)
            logger.debug("--- Selfbot shutdown ---")
            await self.close()
        
    async def on_message(self, message: selfcord.Message, is_forward: bool = False):
        if not self.handshake_responder:
            return
        if self.forward_history_only and not is_forward:
            return
        if not self.forward_history_only and self.handshake_responder.is_valid_handshake_message(message):
            self.handshake_responder.respond(message)
            return
        if message.channel.id not in self.config.channel_list:
            return
        return
        for c in self.channels[message.channel.id]:
            if is_forward and c.get('ignore_forward_history', False):
                continue
            if author_ids := c.get('author_filter', {}).keys():
                if message.author.id not in author_ids:
                    continue
                author_id_name = c['author_filter'][message.author.id].get('display_name_filter', None)
                if author_id_name:
                    if isinstance(author_id_name, list):
                        if message.author.display_name not in author_id_name:
                            continue
                    else:
                        if message.author.display_name != author_id_name:
                            continue
                c['author'] = c['author_filter'][message.author.id]
                
            logger.debug(f"(Receiver On message: Received message {message.id} from {message.author.display_name} in {message.channel.name}.")
            msg = VFMessage.from_dc_msg(message, c)
            self.send_webhook_message(msg)
            
            if self.llm_analyser and message.channel.id in self.config.llm_channel:
                self.llm_analyser.analyse(msg)
        
    def send_webhook_message(self, message: VFMessage):
        for webhook_config in message.webhook_configs:
            webhook = DiscordWebhook(url=webhook_config.url)
            webhook.content = message.content
            if isinstance(message.raw_msg_carrier, selfcord.Message) and webhook_config.use_dynamic_avatar_name:
                webhook.username = message.webhook_author_name
                webhook.avatar_url = message.raw_msg_carrier.author.display_avatar.url
            webhook.embeds = message.embeds
            res = webhook.execute()
            logger.debug(f"(Receiver Sent webhook message. Status code: {res.status_code}.")
    
    async def forward_history_messages_by_channel(self, from_channel_id: int, after: datetime, before: datetime = None, rate: int = 2):
        logger.info(f"Forwarding history messages from {from_channel_id} after {after}.")
        channel = self.get_channel(from_channel_id)
        if not channel:
            logger.error(f"Try to forward history messages from a non-existent channel {from_channel_id}.")
            return
        count = 0
        while True:
            try:
                hist = [msg async for msg in channel.history(limit=100, after=after, before=before, oldest_first=True)]
            except selfcord.Forbidden:
                logger.error(f"Try to forward history messages from a channel {from_channel_id} but got a Forbidden error.")
                return
            if len(hist) == 0:
                break
            for message in hist:
                await self.on_message(message, is_forward=True)
                count += 1
            after = hist[-1].created_at + timedelta(microseconds=1)

        logger.info(f"Forwarded {count} messages from {from_channel_id}.")
        
    async def forward_history_messages(self, after: datetime, before: datetime = None, rate: int = 2):
        if self.forward_history_from_channels:
            for name in self.forward_history_from_channels:
                id = self.config.config['channels'].get(name, None)
                if not id:
                    logger.error(f"Channel {name} not found in config.")
                    continue
                await self.forward_history_messages_by_channel(id, after, before, rate)
        else:
            for id in self.config.channel_list:
                await self.forward_history_messages_by_channel(id, after, before, rate)
        logger.info(f"All history messages forwarded.")
        if self.forward_history_only:
            await self.close()
            print("Selfbot pull only completed.")
