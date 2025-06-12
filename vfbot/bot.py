from concurrent.futures import ThreadPoolExecutor
import logging
import re
import time
from datetime import datetime, timezone, timedelta
from threading import Thread
import asyncio

from .utils import setup_logging
from .sender import MessageSender
from .receiver import MessageReceiver
from .vfconfig import VFConfig
from .keepaliveagent import KeepAliveAgent


VERSION: str = 'SMK-2.2.0'
AUTO_RESUME_TIMEOUT = 5

stream_handler = setup_logging('.log/vfbot.log')
logger = logging.getLogger(__name__)

def parse_date_arg(arg: str) -> datetime:
    """
    Parse a relative time argument in the format '-XdYhZmWs' where:
    - X is days (optional)
    - Y is hours (optional)
    - Z is minutes (optional)
    - W is seconds (optional)
    Example: '-1d2h3m4s' means 1 day, 2 hours, 3 minutes, and 4 seconds ago
    """
    if not arg.startswith('-'):
        try:
            return datetime.strptime(arg, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            logger.warning(f"Invalid date format: {arg}")
            return None
    
    days, hours, minutes, seconds = 0, 0, 0, 0
    
    pattern = r'(\d+)d|(\d+)h|(\d+)m|(\d+)s'
    matches = re.finditer(pattern, arg[1:])
    
    for match in matches:
        if match.group(1):
            days = int(match.group(1))
        elif match.group(2):
            hours = int(match.group(2))
        elif match.group(3):
            minutes = int(match.group(3))
        elif match.group(4): 
            seconds = int(match.group(4))
    
    return datetime.now(timezone.utc) - timedelta(
        days=days,
        hours=hours,
        minutes=minutes,
        seconds=seconds
    )


class Bot:
    def __init__(self):
        self.pull_since = None
        self.sender = None
        self.receiver = None
        self.keep_alive_agent = None
        logger.info("Bot version: %s", VERSION)
    
        self.config = VFConfig('config.json')
        logger.info("Config loaded. %d channels to monitor.", len(self.config.channel_list))
        
    def run(self, **kwargs):
        if 'pull_since' in kwargs:
            date = parse_date_arg(kwargs['pull_since'])
            if date:
                logger.info("Forwarding history messages since %s", date)
                self.pull_since = date
        
        self.discord_thread = Thread(target=self.start_discord)
        self.discord_thread.start()
        self.start_monitor()
            
    def start_monitor(self):
        def wait_for_discord():
            while True:
                if self.keep_alive_agent and self.keep_alive_agent.bot_ready:
                    break
                time.sleep(1)
        
        def wait_for_resume():
            resume_timer = time.time()
            logger.warning("Discord bot is offline, waiting for it to auto-resume...")
            while True:
                if time.time() - resume_timer > AUTO_RESUME_TIMEOUT:
                    logger.warning("Auto-resume timeout, restarting...")
                    self.restart_discord_thread()
                    logger.info("Waiting for discord bots to start...")
                    time.sleep(5)
                    return
                if self.keep_alive_agent.receiver_ok:
                    logger.info("Discord reconnected.")
                    return
                time.sleep(1)
        
        while True:
            try:
                wait_for_discord()
                if not self.keep_alive_agent.receiver_ok:
                    wait_for_resume()
            except KeyboardInterrupt:
                logger.info("Ctrl+C again to shut down...")
                break
            except Exception as e:
                logger.error("Error in monitor thread: %s", e, exc_info=True)
                time.sleep(1)
            
    def restart_discord_thread(self):
        self.discord_thread.join(timeout=1)
        self.discord_thread = Thread(target=self.start_discord)
        self.discord_thread.start()
        logger.info("Discord thread restart requested.")
    
    def start_discord(self):
        logger.info("> Building discord bots...")
        self.sender = MessageSender()
        self.receiver = MessageReceiver(config=self.config, sender=self.sender)
        self.keep_alive_agent = KeepAliveAgent(sender=self.sender, receiver=self.receiver)
        
        self.receiver.forward_history_since = self.pull_since
        self.pull_since = None
        
        executor = ThreadPoolExecutor(max_workers=2)
        
        sender_future = executor.submit(self.sender.run, self.config.bot_token, log_handler=stream_handler)
        receiver_future = executor.submit(self.receiver.run, self.config.self_token, log_handler=stream_handler)
        
        logger.info("> Commissioning discord bots...")
        try:
            # Wait for sender to be ready before scheduling keep-alive agent
            while not self.sender.is_ready():
                time.sleep(0.1)
            asyncio.run_coroutine_threadsafe(self.keep_alive_agent.start(), self.sender.loop)
            
            sender_future.result()
            receiver_future.result()
        except KeyboardInterrupt:
            logger.info("Ctrl+C again to shut down...")
