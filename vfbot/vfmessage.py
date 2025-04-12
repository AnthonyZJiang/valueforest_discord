import discord
import re
import logging
from bs4 import BeautifulSoup
from datetime import datetime
from .utils import ASHLEY_ID, ANGELA_ID


logger = logging.getLogger(__name__)


class VFMessage:
    DISCORD_FILE_LIMIT = 10 * 1024 * 1024  # 10MB in bytes
    
    def __init__(self, content: str, config: dict):
        self._content = content
        self.config = config
        
        self.target_channel_id = config['target_channel_id']
        self.author_name = None
        self.credit = None
        self.credit_link_markup = None
        self.attachments = []

    @staticmethod
    def from_dc_msg(dc_msg: discord.Message, config: dict):
        content = dc_msg.content

        if dc_msg.author.id == ASHLEY_ID: # ashley
            content = content.replace("@c2.ini", "")
            content = re.sub(r':9655_eyesshaking_new:|<a:9655_eyesshaking_new:\d+>', ":eyes:", content)
            content = content.replace(":pngwing:", ":red_circle:")
            content = content.replace(":verifyblue:", ":white_check_mark:")
            content = re.sub(r':RedAlert:|<a:RedAlert:\d+>', ":new:", content)
            
        elif dc_msg.author.id == ANGELA_ID: # angela
            content = content.replace("@c2.ini", "")
            content = re.sub(r':9655_eyesshaking_new:|<a:9655_eyesshaking_new:\d+>', ":eyes:", content)
            content = content.replace(":pngwing:", ":red_circle:")
            content = content.replace(":verifyblue:", ":white_check_mark:")
            content = re.sub(r':8375_siren_blue:|<a:8375_siren_blue:\d+>', ":new:", content)
            content = re.sub(r':RedAlert:|<a:RedAlert:\d+>', ":red_sqare:", content)
            content = re.sub(r':greensiren:|<a:greensiren:\d+>', ":green_square:", content)
        if dc_msg.attachments:
            content += " " + " ".join([f.url for f in dc_msg.attachments])
            
        msg = VFMessage(content.strip(), config)
        msg.author_name = config['author_name_override'] if config['author_name_override'] else dc_msg.author.display_name
        msg.credit = dc_msg.jump_url
        return msg
    
    @staticmethod
    def from_truth_status(status: dict, config: dict):        
        date_time = datetime.fromisoformat(status['created_at'])
        content = f'{status["content"]}\n{" | ".join(status["content_attachments"])}'.strip()
        content = f'[{date_time.strftime("%Y-%m-%d %H:%M:%S")} UTC]({status["uri"]}): {content}'.strip()
        
        msg = VFMessage(content, config)
        msg.author_name = status['account']['display_name']
        msg.attachments = status['attachments']
        return msg
        
    @property
    def content(self) -> str:
        _content = self._content
        if self.config['show_name']:
            if not self.author_name:
                logger.warning(f"VFMessage: author name is not set, skipped.")
            else:
                _content = f"【{self.author_name}】{_content}"
        if self.config['show_credit']:
            if not self.credit:
                logger.warning(f"VFMessage: credit is not set, skipped.")
            else:
                if self.credit_link_markup:
                    _content = f"{_content} | [{self.credit_link_markup}]({self.credit})"
                else:
                    _content = f"{_content} | Credit: {self.credit}"
        return _content
        