from __future__ import annotations
from typing import TYPE_CHECKING
import logging
from datetime import datetime, timedelta
import json
import re

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
        self.channel_configs = config.repost_settings
        
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
        
    async def on_message(self, message: selfcord.Message, config: dict = None,is_forward: bool = False) -> list[tuple[int, int]] | None:
        if not self.handshake_responder:
            return
        if self.forward_history_only and not is_forward:
            return
        if not self.forward_history_only and self.handshake_responder.is_valid_handshake_message(message):
            self.handshake_responder.respond(message)
            return
        if message.channel.id not in self.config.channel_list:
            return
        
        for c in self.channel_configs[message.channel.id]:
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
                
                await self.construct_and_send_message(message, c)
    
    async def construct_and_send_message(self, message: selfcord.Message, config: dict) -> tuple[int, int] | None:
        logger.debug(f"(Receiver On message: Received message {message.id} from {message.author.display_name} in {message.channel.name}.")
        msg = VFMessage.from_dc_msg(message, config)
        master_webhook_result = self.send_webhook_message(msg)
        
        if msg.dc_jump_links and master_webhook_result:
            master_channel_id, _, master_webhook = master_webhook_result
            master_guild_id = self.get_guild_id_from_channel_id(master_channel_id)
            linked_messages = await self.search_linked_message(msg.dc_jump_links, master_guild_id)
            if linked_messages:
                for i, (channel_id, message_id) in enumerate(linked_messages):
                    msg.search_and_replace_content(msg.dc_jump_links[i][0], f"https://discord.com/channels/{master_guild_id}/{channel_id}/{message_id}")
                master_webhook.content=msg.content
                master_webhook.edit()
        
        if self.llm_analyser and message.channel.id in self.config.llm_channel:
            self.llm_analyser.analyse(msg)
            
        return master_webhook_result
    
    async def search_linked_message(self, jump_links, master_guild_id: int):
        results = []
        for _, channel_id, message_id in jump_links:
            linked_message = await self.get_channel(channel_id).fetch_message(message_id)
            # find the first 100 characters of the message content, cut at nearest space
            search_content = ' '.join(linked_message.content[:100].split(' ')[:-1])
            # remove any trailing numbers and \n
            search_content = re.sub(r'\d+$|\n', '', search_content)
            search_results = self.get_guild(master_guild_id).search(content=search_content, limit=1, most_relevant=True)
            try:
                message = await anext(search_results)
            except StopAsyncIteration:
                logger.error(f"Try to search linked message {search_content} but got a StopAsyncIteration error.")
                continue
            results.append((message.channel.id, message.id))
        return results
    
    async def send_relay_message(self, message: VFMessage, master_guild_id: int) -> tuple[int, int] | None:
        relay_webhook_url = self.config.message_relay_webhook.get(str(master_guild_id), None)
        if not relay_webhook_url:
            logger.error(f"Try to forward message to a non-existent guild {master_guild_id}.")
            return
        
        relay_config = {
            'webhook': [relay_webhook_url]
        }
        results = []
        for _, channel_id, message_id in message.dc_jump_links:
            channel = self.get_channel(channel_id)
            if not channel:
                logger.error(f"Try to forward message to a non-existent channel {channel_id}.")
                continue
            linked_message = await self.get_channel(channel_id).fetch_message(message_id)
            results.append(await self.on_message(linked_message, config=relay_config, relay_message=True))
        return results
        
    def send_webhook_message(self, message: VFMessage) -> tuple[int, int, DiscordWebhook] | None:
        for webhook_config in message.webhook_configs:
            webhook = DiscordWebhook(url=webhook_config.url)
            webhook.content = message.content
            if isinstance(message.raw_msg_carrier, selfcord.Message) and webhook_config.use_dynamic_avatar_name:
                webhook.username = message.webhook_author_name
                webhook.avatar_url = message.raw_msg_carrier.author.display_avatar.url
            webhook.embeds = message.embeds
            res = webhook.execute()
            logger.debug(f"(Receiver Sent webhook message. Status code: {res.status_code}.")
            if res.content:
                content = json.loads(res.content)
                return content.get('channel_id'), content.get('id'), webhook
    
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

    def get_guild_id_from_channel_id(self, channel_id: int | str) -> int | None:
        channel = self.get_channel(int(channel_id))
        if not channel:
            logger.error(f"Try to get guild id from a non-existent channel {channel_id}.")
            return None
        return channel.guild.id