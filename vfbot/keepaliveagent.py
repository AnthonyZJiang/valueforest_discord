import os
import json
import logging
import asyncio
import datetime
import time

from .sender import MessageSender
from .receiver import MessageReceiver


KEEP_ALIVE_CONFIG_FILE = "keepalive.config.json"
CROSS_CHECK_HEARTBEAT_TIMEOUT = 5

logger = logging.getLogger(__name__)

class KeepAliveAgent:
    def __init__(self, sender: MessageSender, receiver: MessageReceiver):
        self.sender = sender
        self.receiver = receiver
        
        self.status_report_enabled = False
        self.cross_check_heartbeat_enabled = False
        
        self.config = None # type: dict[str, ]
        self.status_message = None
        self.cross_check_heartbeat_channel_id = None
        self.cross_check_heartbeat_message_prefix = None
        self.cross_check_heartbeat_interval = None
        
    @property
    def receiver_ok(self):
        if not self.receiver or self.receiver.is_closed() or self.receiver.ws._keep_alive is None:
            return False
        if self.cross_check_heartbeat_interval:
            return time.time() - self.receiver.last_message_time < self.cross_check_heartbeat_interval + CROSS_CHECK_HEARTBEAT_TIMEOUT
        return True
    
    @property
    def bot_ready(self):
        return self.receiver and self.receiver.is_ready() and self.sender and self.sender.is_ready()
    
    async def start(self):
        logger.info(f"Starting keep alive agent...")
        await self.load_config()
        asyncio.create_task(self.update_status_message())
        asyncio.create_task(self.send_cross_check_heartbeat())
    
    async def update_status_message(self):
        if not self.status_report_enabled:
            return
        logger.info(f"Status reporting is enabled, sending status updates to {self.status_message.channel.name}...")
        while True:
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
            
    async def send_cross_check_heartbeat(self):
        if not self.cross_check_heartbeat_enabled:
            return
        logger.info(f"Cross check heartbeat is enabled, sending heartbeat to {self.cross_check_heartbeat_channel_id} every {self.cross_check_heartbeat_interval} seconds...")
        while True:
            current_time = int(datetime.datetime.now().timestamp())
            await self.sender.send_plain_message(
                f"{self.cross_check_heartbeat_message_prefix} 心跳: <t:{current_time}>",
                self.cross_check_heartbeat_channel_id
            )
            await asyncio.sleep(self.cross_check_heartbeat_interval)
            
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
                
            cross_check_heartbeat = self.config.get('cross_check_heartbeat', {})
            if not cross_check_heartbeat:
                logger.warning("Cross check heartbeat config not found, heartbeat check is disabled...")
                return
            self.cross_check_heartbeat_channel_id = cross_check_heartbeat.get('channel_id')
            self.cross_check_heartbeat_message_prefix = cross_check_heartbeat.get('message_prefix', 'VF')
            self.cross_check_heartbeat_interval = cross_check_heartbeat.get('interval', 30)
            if self.cross_check_heartbeat_channel_id:
                self.cross_check_heartbeat_enabled = True

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
        with open(STATUS_MESSAGE_CONFIG_FILE, "w") as f:
            json.dump(self.config, f, indent=4)
        logger.debug(f"Status message saved to {STATUS_MESSAGE_CONFIG_FILE}")