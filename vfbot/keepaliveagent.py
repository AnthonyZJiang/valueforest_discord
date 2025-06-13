import os
import json
import logging
import asyncio
import datetime
import time

from .sender import MessageSender
from .receiver import MessageReceiver


KEEP_ALIVE_CONFIG_FILE = "keepalive.config.json"
HANDSHAKE_TIMEOUT = 5

logger = logging.getLogger(__name__)

class KeepAliveAgent:
    id = 0
    def __init__(self, sender: MessageSender, receiver: MessageReceiver):
        self._id = KeepAliveAgent.id
        KeepAliveAgent.id += 1
        self.sender = sender
        self.receiver = receiver
        
        self.status_report_enabled = False
        self.handshake_enabled = False
        
        self.config = None # type: dict[str, ]
        self.status_message = None
        self.handshake_channel_id = None
        self.handshake_message_prefix = None
        self.handshake_interval = None
        
    @property
    def receiver_ok(self):
        if not self.receiver or self.receiver.is_closed() or self.receiver.ws._keep_alive is None:
            return False
        if self.handshake_interval:
            return time.time() - self.receiver.last_message_time < self.handshake_interval + HANDSHAKE_TIMEOUT
        return True
    
    @property
    def bot_ready(self):
        return self.receiver and self.receiver.is_ready() and self.sender and self.sender.is_ready()
    
    async def start(self):
        logger.info(f"Starting keep alive agent #{self._id}...")
        await self.load_config()
        self.status_report_task = asyncio.create_task(self.update_status_message())
        self.handshake_task = asyncio.create_task(self.send_handshake())
        
    async def close(self):
        logger.info(f"Closing keep alive agent #{self._id}...")
        self.status_report_enabled = False
        self.handshake_enabled = False
        self.status_message = None
        
        self.status_report_task.cancel()
        self.handshake_task.cancel()
        
        try:
            await asyncio.wait_for(self.status_report_task, timeout=5.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
        
        try:
            await asyncio.wait_for(self.handshake_task, timeout=5.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
    
    async def update_status_message(self):
        if not self.status_report_enabled:
            return
        logger.info(f"Status reporting is enabled, sending status updates to {self.status_message.channel.name}...")
        while self.status_report_enabled:
            if not self.status_message or not self.receiver_ok:
                await asyncio.sleep(1)
                continue
            current_time = int(datetime.datetime.now().timestamp())
            new_content = f"机器人上次心跳报告: <t:{current_time}>, <t:{current_time}:R>"
            
            try:
                await self.sender.modify_message(self.status_message, new_content)
            except Exception as e:
                logger.error(f"Error updating status message: {str(e)}")
            
            await asyncio.sleep(59)  # Wait for 1 minute
            
    async def send_handshake(self):
        if not self.handshake_enabled:
            return
        logger.info(f"Handshake is enabled, sending handshake to {self.handshake_channel_id} every {self.handshake_interval} seconds...")
        while self.handshake_enabled:
            current_time = int(datetime.datetime.now().timestamp())
            await self.sender.send_plain_message(
                f"{self.handshake_message_prefix} #{self._id} 🤝: <t:{current_time}>",
                self.handshake_channel_id
            )
            await asyncio.sleep(self.handshake_interval)
            
    async def load_config(self):
        while not self.bot_ready:
            await asyncio.sleep(1)
            
        if not os.path.exists(KEEP_ALIVE_CONFIG_FILE):
            logger.warning("Status message config file not found, keep alive agent is disabled...")
            return
        
        with open(KEEP_ALIVE_CONFIG_FILE, "r") as f:
            self.config = json.load(f) # type: dict[str, ]
            if not self.config.get('status_message_id') and self.config.get('status_message_channel_id'):
                await self.create_status_message(self.config['status_message_channel_id'])
            else:
                self.status_message = await self.sender.get_cached_channel(self.config["status_message_channel_id"]).fetch_message(self.config["status_message_id"])
            if self.status_message:
                self.status_report_enabled = True
            else:
                logger.warning("Status message config not found, status reporting is disabled...")
                return
                
            handshake = self.config.get('handshake', {})
            if not handshake:
                logger.warning("Handshake config not found, handshake check is disabled...")
                return
            self.handshake_channel_id = handshake.get('channel_id')
            self.handshake_message_prefix = handshake.get('message_prefix', 'VF')
            self.handshake_interval = handshake.get('interval', 30)
            if self.handshake_channel_id:
                self.handshake_enabled = True

    async def create_status_message(self, channel_id: int):
        self.status_message = await self.sender.send_plain_message(
            "机器人上次心跳报告: ...",
            channel_id
        )
        logger.debug(f"Status message created.")
        if self.status_message:
            self.save_status_message_to_cached_file()
            
    def save_status_message_to_cached_file(self):
        if not self.status_message:
            return
        self.config['status_message_id'] = self.status_message.id
        self.config['status_message_channel_id'] = self.status_message.channel.id
        with open(KEEP_ALIVE_CONFIG_FILE, "w") as f:
            json.dump(self.config, f, indent=4)
        logger.debug(f"Status message saved to {KEEP_ALIVE_CONFIG_FILE}")