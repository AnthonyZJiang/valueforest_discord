import logging
import asyncio
from datetime import datetime, timedelta
import random
import selfcord
from discord_webhook import DiscordWebhook

from .sender import MessageSender
from .vfmessage import VFMessage
from .vfconfig import VFConfig
from .utils import get_config_value

logger = logging.getLogger(__name__)

class MessageReceiver(selfcord.Client):
    def __init__(self, config: VFConfig, sender: MessageSender):
        super().__init__()
        self.config = config
        self.channels = config.repost_settings
        self.sender = sender
        self.forward_history_since = None
        
    async def on_ready(self):
        logger.info(f'Receiver logged on as {self.user}')
        if self.forward_history_since:
            logger.info(f"Forwarding messages since {self.forward_history_since}")
            await self.forward_history_messages(after=self.forward_history_since)
        
    async def delete_duplicate_messages(self, since: datetime):
        # usage: await self.delete_duplicate_messages(since=datetime(2025, 3, 10, 19, 0))
        messages = []
        for channel in self.config.channel_list:
            channel_id = self.channels[channel]['target_channel_id']
            channel = self.get_channel(channel_id)
            hist = [msg async for msg in channel.history(limit=100, after=since, oldest_first=True)]
            for message in hist:
                if message.content in messages:
                    # self.sender.forward_message_to_delete(message)
                    await message.delete()
                    logger.info(f"Deleted duplicate message from {channel.name}: {message.content}")
                    await asyncio.sleep(random.uniform(2, 5))
                else:
                    messages.append(message.content)
        logger.info(f"Duplicate messages deleted.")
            
    async def on_message(self, message: selfcord.Message):
        if message.channel.id not in self.config.channel_list:
            return
        config = None
        for c in self.channels[message.channel.id]:
            if author_ids := c.get('authors', {}).keys():
                if message.author.id not in author_ids:
                    continue
                else:
                    c['author'] = c['authors'][message.author.id]
            config = c
            break
        if not config:
            return
        logger.info(f"On message: Received message {message.id} from {message.author.display_name} in {message.channel.name}.")
        msg = VFMessage.from_dc_msg(message, config)
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
            logger.info(f"Sent webhook message. Response: {res.content}")
    
    async def forward_history_messages_by_channel(self, from_channel_id: int, after: datetime, rate: int = 2):
        logger.info(f"Forwarding history messages from {from_channel_id} after {after}.")
        channel = self.get_channel(from_channel_id)
        if not channel:
            logger.error(f"Try to forward history messages from a non-existent channel {from_channel_id}.")
            return
        count = 0
        while True:
            hist = [msg async for msg in channel.history(limit=100, after=after, oldest_first=True)]
            if len(hist) == 0:
                break
            for message in hist:
                await self.on_message(message)
                count += 1
            after = hist[-1].created_at + timedelta(microseconds=1)

        logger.info(f"Forwarded {count} messages from {from_channel_id}.")
        
    async def forward_history_messages(self, after: datetime, rate: int = 2):
        for id in self.config.channel_list:
            await self.forward_history_messages_by_channel(id, after, rate)
        logger.info(f"All history messages forwarded.")
