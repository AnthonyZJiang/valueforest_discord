from __future__ import annotations
from typing import TYPE_CHECKING
import logging
from datetime import datetime, timedelta
import json
import re
import asyncio
from difflib import get_close_matches

import selfcord
from discord_webhook import DiscordWebhook

from .mod.keepalive.handshake import HandshakeResponder
from .mod.llm.gpt import LLMAnalyser
from .mod.vfmessage import VFMessage

if TYPE_CHECKING:
    from .mod.vfconfig import VFConfig
    from .mod.vfmessage import WebhookConfig


MAX_WORKERS = 10

logger = logging.getLogger(__name__)
sem = asyncio.Semaphore(MAX_WORKERS)


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
        
    async def on_message(self, message: selfcord.Message, is_forward: bool = False) -> bool:
        # if not self.handshake_responder:
        #     return
        if self.forward_history_only and not is_forward:
            # when in forwarding history only mode, ignore any new messages
            return False
        if not self.forward_history_only and self.handshake_responder.is_valid_handshake_message(message):
            # handle handshake messages
            self.handshake_responder.respond(message)
            return False
        if message.channel.id not in self.config.channel_list:
            # ignore messages from channels not in the config
            return False
        sent = False
        
        for c in self.channel_configs[message.channel.id]:
            if is_forward and c.get('ignore_forward_history', False):
                # when forwarding history, ignore channels that are configured to ignore forwarding history
                continue
            is_author_valid, author_config = self.check_author(message, c)
            if not is_author_valid:
                continue
            if author_config:
                c['author'] = author_config
            sent = await self.construct_and_send_message(message, c)
        return sent
    
    def check_author(self, message: selfcord.Message, config: dict) -> tuple[bool, dict | None]:
        """ Check if the message author is valid for the channel config.
        
        Parameters:
        -----------
        message: :class:`selfcord.Message`
            The message to check.
        config: :class:`dict`
            The channel config.
            
        Returns:
        --------
        :class:`tuple[bool, dict | None]`
            A tuple containing a boolean indicating if the message author is valid and the author configuration if valid, otherwise :class:`None`.
        """
        if author_ids := config.get('author_filter', {}).keys():
            if message.author.id not in author_ids:
                return False, None
            author_id_name = config['author_filter'][message.author.id].get('display_name_filter', None)
            if author_id_name:
                if isinstance(author_id_name, list):
                    if message.author.display_name not in author_id_name:
                        return False, None
                else:
                    if message.author.display_name != author_id_name:
                        return False, None
            return True, config['author_filter'][message.author.id]
        return True, None
    
    async def construct_and_send_message(self, message: selfcord.Message, config: dict) -> bool:
        """ Construct and send a message to the webhooks.
        
        Parameters:
        -----------
        message: :class:`selfcord.Message`
            The message to construct and send.
        config: :class:`dict`
            The channel config.
        
        Returns:
        --------
        :class:`bool`
            :class:`True` if the message is sent successfully, otherwise :class:`False`.
        """
        logger.debug(f"Received message {message.id} from {message.author.display_name} in {message.channel.name}.")
        msg = VFMessage.from_dc_msg(message, config)
        for webhook_config in msg.webhook_configs:
            sent_msg_channel_id, sent_msg_webhook = await self.send_webhook_message(msg, webhook_config)
            if not sent_msg_channel_id:
                return False
            if msg.dc_jump_links and sent_msg_webhook:
                sent_msg_guild_id = self.get_guild_id_from_channel_id(sent_msg_channel_id)
                matches = await self.search_linked_message(msg.dc_jump_links, sent_msg_guild_id)
                if matches:
                    for jump_link_url, matched_channel_id, matched_message_id in matches:
                        msg.find_and_replace(jump_link_url, 
                                             f"https://discord.com/channels/{sent_msg_guild_id}/{matched_channel_id}/{matched_message_id}")
                    sent_msg_webhook.content=msg.content
                    sent_msg_webhook.edit()
        
        if self.llm_analyser and message.channel.id in self.config.llm_channel:
            self.llm_analyser.analyse(msg)
        
        return True
    
    async def search_linked_message(self, jump_links, sent_msg_guild_id: int) -> list[tuple[str, int, int]]:
        """ Search for linked messages in the master guild.
        
        Some posts contains links to previous messages, and the forward content will also contain these links.
        Since these linked messages are not visible to non-vip users, the links in the forwarded content leads
        to nowhere for these users.
        
        However, most likely, the linked messages have been reposted in the master guild already, so we can 
        search for the linked message contents in the master guild and replace the links in the forwarded content.
        
        Parameters:
        -----------
        jump_links: :class:`list[tuple[str, int, int]]`
            A list of the jump link tuples (url, channel_id, message_id).
        sent_msg_guild_id: :class:`int`
            The ID of the discord server to search for the linked message contents.
        
        Returns:
        --------
        :class:`list[tuple[str, int, int]]`
            The list of original jump link url, matched_channel ID and matched_message ID of the linked messages.
        """
        results = []
        for url, channel_id, message_id in jump_links:
            linked_channel = self.get_channel(channel_id)
            if not linked_channel:
                logger.error(f"Try to search for a linked message in a non-existent channel {channel_id}.")
                continue
            linked_message = await linked_channel.fetch_message(message_id)
            if not linked_message:
                logger.error(f"Try to search for a linked message in a non-existent message {message_id}.")
                continue
            # find the first 100 characters of the message content, cut at nearest space
            search_content = ' '.join(linked_message.content[:100].split(' ')[:-1])
            # remove any trailing numbers and \n
            search_content = re.sub(r'\d+$|\n', '', search_content)
            search_results = self.get_guild(sent_msg_guild_id).search(content=search_content, limit=5, oldest_first=True)
            try:
                similar_messages = [message async for message in search_results]
            except StopAsyncIteration:
                logger.error(f'Search returns 0 results for: "{search_content}"')
                continue          
            channel_names = [message.channel.name for message in similar_messages]
            matches = get_close_matches(linked_channel.name, channel_names, n=1)
            if matches:
                matched_message = similar_messages[channel_names.index(matches[0])]
                results.append((url, matched_message.channel.id, matched_message.id))
        return results
        
    async def send_webhook_message(self, message: VFMessage, webhook_config: WebhookConfig) -> tuple[int | None, DiscordWebhook | None]:
        """ Send a webhook message to the webhook URL.
        
        Parameters:
        -----------
        message: :class:`VFMessage`
            The message to send.
        
        Returns:
        --------
        :class:`tuple[int, DiscordWebhook]` | :class:`None`
            The channel ID and the webhook object if the message is sent successfully, otherwise :class:`None`.
        """
        webhook = DiscordWebhook(url=webhook_config.url)
        webhook.content = message.content
        if isinstance(message.raw_msg_carrier, selfcord.Message) and webhook_config.use_dynamic_avatar_name:
            webhook.username = message.webhook_author_name
            webhook.avatar_url = message.raw_msg_carrier.author.display_avatar.url
        webhook.embeds = message.embeds
        res = webhook.execute()
        logger.debug(f"Sent webhook message. Status code: {res.status_code}.")
        if res.status_code == 429:
            retry_after = json.loads(res.content).get('retry_after')
            if retry_after:
                await asyncio.sleep(retry_after)
                return await self.send_webhook_message(message, webhook_config)
        elif res.status_code != 200:
            logger.warning(f"Unknown webhook status code: {res.status_code}")

        try:
            content = json.loads(res.content)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse webhook response content: {res.content}")
            return None, None
        channel_id = content.get('channel_id')
        if not channel_id:
            logger.error(f"Webhook response content does not contain a channel ID.")
            return None, None
        return int(channel_id), webhook
    
    async def forward_history_messages_by_channel(self, from_channel_id: int, after: datetime, before: datetime = None, interval: float = 0.1):
        channel = self.get_channel(from_channel_id)
        if not channel:
            logger.error(f"Try to forward history messages from a non-existent channel {from_channel_id}.")
            return
        logger.debug(f"Forwarding history messages from {channel.name}.")
        sent, count = 0, 0
        while True:
            try:
                hist = [msg async for msg in channel.history(limit=100, after=after, before=before, oldest_first=True)]
                await asyncio.sleep(0.1) # avoid rate limit
            except selfcord.Forbidden:
                logger.error(f"Try to forward history messages from a channel {channel.name} but got a Forbidden error.")
                return
            if len(hist) == 0:
                break
            for message in hist:
                if await self.on_message(message, is_forward=True):
                    sent += 1
                    await asyncio.sleep(interval)
                count += 1
                
            after = hist[-1].created_at + timedelta(microseconds=1)

        logger.info(f"Forwarded {sent} / {count} messages from {channel.name}.")
        
    async def forward_history_messages(self, after: datetime, before: datetime = None, interval: float = 0.1):
        async def forward_with_limit(channel_id: int, after: datetime, before: datetime, interval: float):
            async with sem:
                await self.forward_history_messages_by_channel(channel_id, after, before, interval)
        
        tasks = []
        if self.forward_history_from_channels:
            for id in self.forward_history_from_channels:
                if isinstance(id, str):
                    if id.isdigit():
                        id = int(id)
                    else:
                        id = self.config.config['channels'].get(id, None)
                        if not id:
                            logger.error(f"Channel {id} not found in config.")
                            continue
                tasks.append(asyncio.create_task(forward_with_limit(id, after, before, interval)))
        else:
            for id in self.config.channel_list:
                tasks.append(asyncio.create_task(forward_with_limit(id, after, before, interval)))
        await asyncio.gather(*tasks)
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