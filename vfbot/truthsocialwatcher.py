from datetime import datetime, timezone
import time
import logging
import requests
import io

from bs4 import BeautifulSoup
import discord
from truthbrush import Api
from quickimgurpy import ImgurClient

from .sender import MessageSender
from .vfmessage import VFMessage
from .utils import translate

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
        self.imgur = ImgurClient()

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

    def upload_to_imgur(self, file_data: bytes, file_type: str):
        try:
            if file_type == 'image':
                resp = self.imgur.upload_image(file_data, force_base64=True)
            elif file_type == 'video':
                resp = self.imgur.upload_video(file_data, force_base64=True)
            if resp['status'] == 200:
                return resp['data']['link']
        except Exception as e:
            logger.error(f"Error uploading to imgur: {e}")
            
        return None
    
    def prepare_page(self, page: dict):
        page['attachments'], page['content_attachments'] = self.handle_attachments(page)
        content, url = self.parse_content(page['content'])
        if content:
            page['content'] = self.add_translation(content)
            if url:
                page['content'] = page['content'] + '\n' + f'-# [link]({url})'
        elif url:
            page['content'] = f'-# [link]({url})'
        return page
    
    def parse_content(self, html_content):
        soup = BeautifulSoup(html_content, 'html.parser')
        
        link = soup.find('a')
        url = ''
        if link:
            url = link.get('href', '')
            
        text_content = ''
        paragraphs = soup.find_all('p')
        if paragraphs:
            paragraph_texts = []
            for p in paragraphs:
                
                spans = p.find_all('span')
                for span in spans:
                    span.unwrap()
                
                for br in p.find_all('br'):
                    br.replace_with('\n')
                
                p_text = p.get_text().strip()
                if p_text:
                    paragraph_texts.append(p_text)
            
            text_content = '\n\n'.join(paragraph_texts)
            if url:
                text_content = text_content.replace(url, '').strip()
            
            text_content = text_content.strip()
            
            # Replace ill decoded characters
            text_content = text_content.replace('â€™', '\'').replace('Â', '').replace("â€œ", "“").replace("â€", "”").replace("â€™", "'")

        return text_content, url
    
    def add_translation(self, content: str):
        if not content:
            return content
        try:
            translation = translate(content)
        except Exception as e:
            logger.error(f"Error translating content: {e}")
            return '-# :small_orange_diamond:Translation failed' + '\n' + content
        
        lines = content.split('\n')
        content = [f'-# {line}' if line.strip() else line for line in lines]
        content = translation + '\n\n' + '\n'.join(content)
        return content
    
    def handle_attachments(self, status: dict):
        if not status['media_attachments']:
            return [], []
        
        def get_attachment_markup(attachment: dict):
            if attachment['type'] == 'video':
                return f':small_blue_diamond: [Click here to watch the video]({attachment["url"]})'
            else:
                return f':small_blue_diamond: [Click here to view the image]({attachment["url"]})'
            
        attachments = []
        content_attachments = []
        for attachment in status['media_attachments']:
            try:
                file_url = attachment['url']
                file_ext = file_url.split('.')[-1].lower()
                filename = f"media.{file_ext}"

                response = requests.get(file_url)
                response.raise_for_status()
                file_data = response.content

                imgur_url = None
                print(len(file_data)/1024/1024)
                if len(file_data) > VFMessage.DISCORD_FILE_LIMIT:
                    if attachment['type'] in ['image', 'video']:
                        imgur_url = self.upload_to_imgur(file_data, attachment['type'])
                    content_attachments.append(imgur_url or get_attachment_markup(attachment))
                else:
                    # File is small enough for Discord
                    discord_file = discord.File(
                        fp=io.BytesIO(file_data),
                        filename=filename
                    )
                    attachments.append(discord_file)

            except Exception as e:
                logger.error(
                    f"Failed to handle attachment {file_url}: {str(e)}")
                content_attachments.append(get_attachment_markup(attachment))

        return attachments, content_attachments

    def pull_all_statuses(self):
        for user in self.users:
            try:
                pages = []
                for page in self.api.pull_statuses(user_id=user.user_id, created_after=user.last_status_pull):
                    pages.append(page)
                for page in pages[::-1]:
                    page = self.prepare_page(page)
                    msg = VFMessage.from_truth_status(page, user.config)
                    self.sender.forward_message(msg)
                    if len(pages) > 3:
                        time.sleep(10)
                user.last_status_pull = datetime.now(timezone.utc)
            except Exception as e:
                logger.error(
                    f"Error pulling statuses for user {user.user_id}: {e}")
            