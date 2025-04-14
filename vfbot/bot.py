import json
from concurrent.futures import ThreadPoolExecutor
import logging
from datetime import datetime, time, timedelta, timezone

from .utils import setup_logging
from .sender import MessageSender
from .receiver import MessageReceiver
from .truthsocialwatcher import TruthSocialWatcher


VERSION: str = 'SMK-0.1.0'


def parse_date_arg(arg: str) -> datetime:
    if arg == 'today':
        today = datetime.now(timezone.utc).date()
        return datetime.combine(today, time.min)
    if arg == 'yesterday':
        yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
        return datetime.combine(yesterday, time.min)
    if arg.startswith('-'):
        return datetime.now(timezone.utc) - timedelta(hours=float(arg[1:]))
    parts = arg.split(' ', 1)
    if parts[0] in ['today', 'yesterday']:
        date_part = parts[0]
        time_part = parts[1]

        if date_part == 'today':
            base_date = datetime.now(timezone.utc).date()
        elif date_part == 'yesterday':
            base_date = datetime.now(timezone.utc).date() - timedelta(days=1)
        else:
            return datetime.strptime(arg, '%Y-%m-%d %H:%M:%S')
        
        try:
            time_obj = datetime.strptime(time_part, '%H:%M:%S').time()
            return datetime.combine(base_date, time_obj)
        except ValueError:
            raise ValueError(f"Time must be in HH:MM:SS format, got: {time_part}")


class Bot:
    def __init__(self):
        setup_logging()
        self.logger = logging.getLogger(__name__)
        self.logger.info("Bot version: %s", VERSION)
    
        self.config = json.load(open('config.json'))

    def run(self, **kwargs):
        sender = MessageSender(config=self.config)
        receiver = MessageReceiver(config=self.config, sender=sender)
        
        if 'forward_history_since' in kwargs:
            forward_history_since = parse_date_arg(kwargs['forward_history_since'])
            self.logger.info("Forwarding history messages since %s", forward_history_since)
        else:
            forward_history_since = None
            
        receiver.forward_history_since = forward_history_since
        truth_watcher = TruthSocialWatcher(config=self.config, sender=sender, pull_since=forward_history_since)
        
        executor = ThreadPoolExecutor(max_workers=2)
        
        sender_future = executor.submit(sender.run, self.config['bot_token'])
        receiver_future = executor.submit(receiver.run, self.config['self_token'])
        truth_watcher_future = executor.submit(truth_watcher.run)
        
        self.logger.info("Starting bot...")
        try:
            sender_future.result()
            receiver_future.result()
            truth_watcher_future.result()
        except KeyboardInterrupt:
            self.logger.info("Ctrl+C again to shut down...")
