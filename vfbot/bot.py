import json
from concurrent.futures import ThreadPoolExecutor
import logging
import re
import time
from datetime import datetime, timezone, timedelta
from threading import Thread

from .utils import setup_logging
from .sender import MessageSender
from .receiver import MessageReceiver


VERSION: str = 'SMK-0.2.0-no-trump'

setup_logging()
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
        
        logger.info("Bot version: %s", VERSION)
    
        self.config = json.load(open('config.json'))
        self.config['channels'] = {int(k): v for k, v in self.config['channels'].items()}
        logger.info("Config loaded. %d channels to monitor.", len(self.config['channels']))
        
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
                if self.receiver and self.receiver.is_ready() and self.sender and self.sender.is_ready():
                    break
                time.sleep(1)
                
        while True:
            try:
                wait_for_discord()
                if self.receiver.is_closed():
                    self.restart_discord_thread()
                time.sleep(1)
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
    
    def start_discord(self):
        self.sender = MessageSender(config=self.config)
        self.receiver = MessageReceiver(config=self.config, sender=self.sender)
        
        self.receiver.forward_history_since = self.pull_since
        self.pull_since = None
        
        executor = ThreadPoolExecutor(max_workers=2)
        
        sender_future = executor.submit(self.sender.run, self.config['bot_token'])
        receiver_future = executor.submit(self.receiver.run, self.config['self_token'], log_level=logging.INFO)
        
        logger.info("Starting bot...")
        try:
            sender_future.result()
            receiver_future.result()
        except KeyboardInterrupt:
            logger.info("Ctrl+C again to shut down...")
