from datetime import datetime, timezone
import time
import logging

from truthbrush import Api

from .sender import MessageSender
from .vfmessage import VFMessage
from .truthsocialpost import TruthPostBuilder

logger = logging.getLogger(__name__)


class TruthUser:
    def __init__(self, user_id: str, config: dict, pull_since: datetime):
        self.user_id = user_id
        self.config = config
        self.last_status_pull = datetime.now(
            timezone.utc) if pull_since is None else pull_since


class TruthSocialWatcher:
    def __init__(self, config: dict, sender: MessageSender, pull_since: datetime = None):
        self.config = config
        self.sender = sender
        self.users: list[TruthUser] = []
        self.api = Api()
        self.post_builder = TruthPostBuilder()

        for user_id in self.config['truth_social_users']:
            self.users.append(
                TruthUser(user_id, self.config['truth_social_users'][user_id], pull_since))

        self.interval = 60 * len(self.users)
        logger.info(
            f"TruthSocialWatcher initialized with {len(self.users)} users...")

    def run(self):
        logger.info(
            f"TruthSocialWatcher running with interval {self.interval} seconds...")
        while True:
            if not self.sender.is_ready():
                time.sleep(1)
                continue
            self.pull_all_statuses()
            time.sleep(self.interval)

    def pull_all_statuses(self):
        for user in self.users:
            try:
                posts = []
                for post in self.api.pull_statuses(user_id=user.user_id, created_after=user.last_status_pull):
                    posts.append(post)
                # import json
                # with open('trump_dump.json', 'r') as f:
                #     posts = json.load(f)
                #     posts = posts[:-3]
                for post in posts[::-1]:
                    try:
                        post = self.post_builder.build_post(post)
                        msg = VFMessage.from_truth_status(post, user.config)
                        self.sender.forward_message(msg)
                        if len(post) > 5:
                            time.sleep(1)
                    except Exception as e:
                        logger.error(f"Error building post: {e}")
                user.last_status_pull = datetime.now(timezone.utc)
            except Exception as e:
                logger.error(
                    f"Error pulling statuses for user {user.user_id}: {e}")
                