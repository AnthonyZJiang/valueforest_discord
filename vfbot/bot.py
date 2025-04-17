import json
from concurrent.futures import ThreadPoolExecutor
import logging
import re
from datetime import datetime, timezone, timedelta

from .utils import setup_logging
from .sender import MessageSender
from .receiver import MessageReceiver


VERSION: str = 'SMK-0.2.0-no-trump'


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
        raise ValueError("Time argument must start with '-'")
    
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
        setup_logging()
        self.logger = logging.getLogger(__name__)
        self.logger.info("Bot version: %s", VERSION)
    
        self.config = json.load(open('config.json'))
        self.config['channels'] = {int(k): v for k, v in self.config['channels'].items()}
        self.logger.info("Config loaded. %d channels to monitor.", len(self.config['channels']))

    def run(self, **kwargs):
        sender = MessageSender(config=self.config)
        receiver = MessageReceiver(config=self.config, sender=sender)
        
        if 'pull_since' in kwargs:
            receiver.forward_history_since = parse_date_arg(kwargs['pull_since'])
            self.logger.info("Forwarding history messages since %s", receiver.forward_history_since)
        
        executor = ThreadPoolExecutor(max_workers=2)
        
        sender_future = executor.submit(sender.run, self.config['bot_token'])
        receiver_future = executor.submit(receiver.run, self.config['self_token'], log_level=logging.INFO)
        
        self.logger.info("Starting bot...")
        try:
            sender_future.result()
            receiver_future.result()
        except KeyboardInterrupt:
            self.logger.info("Ctrl+C again to shut down...")
