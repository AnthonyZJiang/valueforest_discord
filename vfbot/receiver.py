import logging
import asyncio
from datetime import datetime, timedelta
import selfcord
from discord_webhook import DiscordWebhook
import time

from .sender import MessageSender
from .vfmessage import VFMessage
from .vfconfig import VFConfig

logger = logging.getLogger(__name__)

class MessageReceiver(selfcord.Client):
    def __init__(self, config: VFConfig, sender: MessageSender):
        super().__init__()
        self.config = config
        self.channels = config.repost_settings
        self.sender = sender
        self.forward_history_since = None
        self.last_message_time = None
        
    async def on_ready(self):
        logger.info(f'Receiver logged on as {self.user}')
        if self.forward_history_since:
            logger.info(f"Forwarding messages since {self.forward_history_since}")
            await self.forward_history_messages(after=self.forward_history_since)
            
    async def on_message(self, message: selfcord.Message):
        self.last_message_time = time.time()
        if message.channel.id not in self.config.channel_list:
            return
        for c in self.channels[message.channel.id]:
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
                
            logger.debug(f"On message: Received message {message.id} from {message.author.display_name} in {message.channel.name}.")
            msg = VFMessage.from_dc_msg(message, c)
            if msg.is_webhook:
                self.send_webhook_message(msg)
            else:
                self.sender.forward_message(msg)
            
            await asyncio.sleep(2)
        
    def send_webhook_message(self, message: VFMessage):
        for webhook_config in message.webhook_configs:
            webhook = DiscordWebhook(url=webhook_config.url)
            webhook.content = message.content
            if isinstance(message.raw_msg_carrier, selfcord.Message) and webhook_config.use_dynamic_avatar_name:
                webhook.username = message.raw_msg_carrier.author.display_name
                webhook.avatar_url = message.raw_msg_carrier.author.display_avatar.url
            webhook.embeds = message.embeds
            res = webhook.execute()
            logger.debug(f"Sent webhook message. Status code: {res.status_code}.")
    
    async def forward_history_messages_by_channel(self, from_channel_id: int, after: datetime, rate: int = 2):
        logger.info(f"Forwarding history messages from {from_channel_id} after {after}.")
        channel = self.get_channel(from_channel_id)
        if not channel:
            logger.error(f"Try to forward history messages from a non-existent channel {from_channel_id}.")
            return
        count = 0
        while True:
            try:
                hist = [msg async for msg in channel.history(limit=100, after=after, oldest_first=True)]
            except selfcord.Forbidden:
                logger.error(f"Try to forward history messages from a channel {from_channel_id} but got a Forbidden error.")
                return
            if len(hist) == 0:
                break
            for message in hist:
                await self.on_message(message)
                count += 1
            after = hist[-1].created_at + timedelta(microseconds=1)

        logger.info(f"Forwarded {count} messages from {from_channel_id}.")
        
    async def forward_history_messages(self, after: datetime, rate: int = 2):
        for id in self.config.channel_list:
            if self.channels[id].get('ignore_forward_history', False):
                logger.debug(f"Ignoring forward history messages from {id}.")
                continue
            await self.forward_history_messages_by_channel(id, after, rate)
        logger.info(f"All history messages forwarded.")
