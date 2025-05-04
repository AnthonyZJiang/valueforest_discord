import discord
import re
from typing_extensions import Self
from .utils import ASHLEY_ID, ANGELA_ID

class VFMessage:
    def __init__(self, content: str, config: dict, raw_msg_carrier = None, author_name = None, credit = None, embeds = []):
        self._content = content
        self.config = config
        
        self.target_channel_id = config.get('target_channel', None)
        self.webhook_url = config.get('webhook', None)
        if isinstance(self.webhook_url, dict):
            self.webhook_url = self.webhook_url.get('url', None)
            self.webhook_dynamic_avatar_name = self.webhook_url.get('dynamic_avatar_name', False)
        else:
            self.webhook_dynamic_avatar_name = False
        self.is_webhook = self.webhook_url is not None
        self.show_author_name = config.get('show_author_name', False) and not self.is_webhook
        self.show_credit = config.get('show_credit', False)
            
        self.raw_msg_carrier: discord.Message = raw_msg_carrier
        self.author_name: str = author_name
        self.credit: str = credit
        self.embeds: list[discord.Embed] = embeds
        
    @classmethod
    def from_dc_msg(cls, dc_msg: discord.Message, config: dict) -> Self:
        def get_author_name(author_name: str):
            if author_name == '$cathy-whale$':
                return '巨鲸分析'
            elif author_name == '$cathy-swing$':
                return '短线分析'
            elif author_name == '$cathy-view$':
                return '观点分享'
            elif author_name == '$cathy-invest$':
                return '长线布局'
            elif author_name == '$cathy-strategy$':
                return '交易心得'
            else:
                return author_name
        
        def get_embeds(embeds: list[discord.Embed]):
            embeds_list = []
            for embed in embeds:
                if not embed.url:
                    embeds_list.append(embed)
            return embeds_list
            
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

        author_name = config.get('author_name_override', 
                                 config.get('author', {}).get('name', dc_msg.author.display_name))

        msg = cls(content.strip(), 
                  config, 
                  raw_msg_carrier = dc_msg, 
                  author_name = get_author_name(author_name), 
                  credit = dc_msg.jump_url, 
                  embeds = get_embeds(dc_msg.embeds))
        
        return msg
        
    @property
    def content(self) -> str:
        _content = self._content
        
        if self.show_author_name:
            if self.is_emoji(self.author_name):
                _content = f"{self.author_name} {_content}"
            else:
                _content = f"【{self.author_name}】 {_content}"
        if self.show_credit:
            _content = f"{_content} | {self.credit}"
        return _content
                
    @staticmethod
    def is_emoji(val: str) -> bool:
        return val and val.startswith("<:") and val.endswith(">")
