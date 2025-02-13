import json
from concurrent.futures import ThreadPoolExecutor
import logging
from datetime import datetime, time, timedelta

from .utils import setup_logging
from .sender import MessageSender
from .receiver import MessageReceiver


VERSION: str = 'SMK-0.1.0'


def parse_date_arg(arg: str) -> datetime:
    if arg == 'today':
        today = datetime.now().date()
        return datetime.combine(today, time.min)
    if arg == 'yesterday':
        yesterday = datetime.now().date() - timedelta(days=1)
        return datetime.combine(yesterday, time.min)
    else:
        return datetime.strptime(arg, '%Y-%m-%d %H:%M:%S')


class Bot:
    def __init__(self):
        setup_logging()
        self.logger = logging.getLogger(__name__)
        self.logger.info("Bot version: %s", VERSION)
    
        self.config = json.load(open('config.real.json'))
        self.config['channels'] = {int(k): v for k, v in self.config['channels'].items()}
        self.logger.info("Config loaded. %d channels to monitor.", len(self.config['channels']))

    def run(self, **kwargs):
        sender = MessageSender(config=self.config)
        receiver = MessageReceiver(config=self.config, sender=sender)
        
        # Parse forward_history_since argument if provided
        if 'forward_history_since' in kwargs:
            receiver.forward_history_since = parse_date_arg(kwargs['forward_history_since'])
        
        executor = ThreadPoolExecutor(max_workers=2)
        
        sender_future = executor.submit(sender.run, self.config['bot_token'])
        receiver_future = executor.submit(receiver.run, self.config['self_token'])
        
        self.logger.info("Starting bot...")
        try:
            sender_future.result()
            receiver_future.result()
        except KeyboardInterrupt:
            self.logger.info("Ctrl+C again to shut down...")
