import discord
import re
from typing_extensions import Self
from .utils import ASHLEY_ID, ANGELA_ID

class VFMessage:
    def __init__(self, content: str, config: dict):
        self._content = content
        self.config = config
        
        self.target_channel_id = config['target_channel_id']
        self.use_emoji = config.get('use_emoji_for_name', False)
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
        
        msg.set_author_name(config.get('author_name_override', dc_msg.author.display_name if not msg.use_emoji else f"{dc_msg.author.name}"))
        msg.credit = dc_msg.jump_url
        msg.set_embeds(dc_msg.embeds)
        return msg
        
    @property
    def content(self) -> str:
        _content = self._content
        if self.config.get('show_name', False):
            if self.is_emoji(self.author_name):
                _content = f"{self.author_name} {_content}"
            else:
                _content = f"【{self.author_name}】 {_content}"
        if self.config.get('show_credit', False):
            _content = f"{_content} | {self.credit}"
        return _content

    def set_embeds(self, embeds: list[discord.Embed]):
        for embed in embeds:
            if not embed.url:
                self.embeds.append(embed)
                
    def set_author_name(self, author_name: str):
        if author_name == '$cathy-whale$':
            self.author_name = '巨鲸分析'
        elif author_name == '$cathy-swing$':
            self.author_name = '短线分析'
        elif author_name == '$cathy-view$':
            self.author_name = '观点分享'
        elif author_name == '$cathy-invest$':
            self.author_name = '长线布局'
        elif author_name == '$cathy-strategy$':
            self.author_name = '交易心得'
        else:
            self.author_name = author_name
            
        if self.config.get('use_emoji_for_name', False) and not self.is_emoji(self.author_name):
            emoji = self.config.get('emoji_mapping', {}).get(self.author_name, None)
            if emoji:
                self.author_name = emoji
            else:
                self.use_emoji = False # If no emoji is found, disable emoji for name
                
    @staticmethod
    def is_emoji(val: str) -> bool:
        return val.startswith("<:") and val.endswith(">")
