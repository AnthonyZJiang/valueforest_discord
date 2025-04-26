import discord
import re
from typing_extensions import Self
from .utils import ASHLEY_ID, ANGELA_ID

class VFMessage:
    def __init__(self, content: str, config: dict):
        self._content = content
        self.config = config
        
        self.target_channel_id = config['target_channel_id']
        self.author_name = None
        self.credit = None
        self.embeds = []
        
    @classmethod
    def from_dc_msg(cls, dc_msg: discord.Message, config: dict) -> Self:
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
            
        msg = cls(content.strip(), config)
        
        msg.author_name = msg.config.get('author_name_override', '')
        if not msg.author_name:
            msg.author_name = dc_msg.author.display_name
        msg.credit = dc_msg.jump_url
        msg.embeds = dc_msg.embeds
        return msg
        
    @property
    def content(self) -> str:
        _content = self._content
        if self.config.get('show_name', False):
            _content = f"【{self.author_name}】{_content}"
        if self.config.get('show_credit', False):
            _content = f"{_content} | {self.credit}"
        return _content
