from openai import OpenAI
from discord_webhook import DiscordWebhook
import json
import re
from concurrent.futures import ThreadPoolExecutor
import threading
from selfcord import Message as DiscordMessage
import logging
import time
from .actionserver_webhook import ActionServer

logger = logging.getLogger(__name__)

"""
"llm_config": {
    "920923501559443516": [
        {
            "webhook": "https://discord.com/api/webhooks/1395526838197026973/PZwMjJoP8YmZ07wjfwJgORicfuMcu0IjZUVDp008bs9SYiBdEmgiCd8775Dmm9roEiad",
            "ignore_ignored_posts": false,
            "ignored_posts_use_mention": false,
            "mention": ["everyone"]
        },
        {
            "webhook": "https://discord.com/api/webhooks/1427987391511134321/bt098ncSYB-PcYngW5bSaMk0MnaaEsG72O0sqadQ6kY2qJx6jDHwXlHcl9AaASOQamQE",
            "ignore_ignored_posts": false,
            "ignored_posts_use_mention": false,
            "mention": ["everyone"]
        }
    ],
}
"""

class LLMAnalyser:
    def __init__(self, llm_config: dict, max_workers: int = 3):
        self.openai_client = OpenAI()
        self.action_server = ActionServer()
        self.llm_config = {}
        for channel_id, config in llm_config.items():
            self.llm_config[int(channel_id)] = config
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="LLMAnalyser")
        self._lock = threading.Lock()
        self.time_start = time.perf_counter()

    def analyse(self, message: DiscordMessage):
        self.time_start = time.perf_counter()
        logger.info(f"Analysing message {message.id} from {message.author.display_name} in {message.channel.name}.")
        cleaned_content = self._cleanup_message(message.content)
        if not cleaned_content:
            return
        msg = {
            "content": cleaned_content,
            "dc_msg": message
        }
        future = self.executor.submit(self._execute, msg)
        return future
    
    def _execute(self, message: dict):
        """
        Synchronous analysis method that runs in the thread pool.
        """
        try:
            response = self._get_response_from_llm(message['content'])
            # response = {
            #     'error': None,
            #     'response': '$TEST,BTO,O=100,S=90;$TEST2,TP;$TEST3,SL,S=80;$TEST,MS,S=70;ign'
            # }
        except Exception as e:
            logger.error(f"Failed to analyse message: {e}", exc_info=True)
            response = {
                'error': str(e),
                'response': None
            }
        self.action_server.add_action(response['response'], message['dc_msg'], self.llm_config[message['dc_msg'].channel.id])
    
    def _cleanup_message(self, message: str):
        # remove timestamp <t:1231245> <t:1231245:R>, emoji <a:emoji_132.abc:321> <:emoji:321>, remove mentions <@!12345> <@3214512> <@&12345> <#32134>
        message = re.sub(r'<[#@:ta][&!]?[^>]+R?>', '', message).strip()
        # remove @everyone, @here, @unknown-role etc.
        message = re.sub(r'@(everyone|here|unknown-role)', '', message)
        # remove links
        message = re.sub(r'https?://[^\s]+', '', message)
        return message.strip()

    def _get_response_from_llm(self, message: str):
        response = self.openai_client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {
                "role": "system",
                "content": [
                    {
                    "type": "input_text",
                    "text": "你是资深股票交易员。你订阅了推特博主的股票推荐。该博主定期发推文分享他的交易思路和交易操作。你需要首先等待用户提供推文，然后做以下几个步：\n\n1. 仔细阅读该推文。\n2. 如果推文内容是他的交易操作，则进入步骤3。否则直接跳过其他步骤并回复\"ign\"\n3. 提取股表代码，分析内容是否为开仓（进入步骤4），止盈（进入步骤5），止损（进入步骤6）或者调整/设置止损（进入步骤7）。如果有多个步骤，则按先后顺序依次处理，回复之间用\";\"隔开\n4. 开仓：分析是否提到开仓价或止损价，并按以下格式回复\"$<股票代码>,BTO,O=<开仓价>,S=<止损价>\"。若未提及具体止损或开仓价，则无需回复相关内容。\n5. 止盈：按以下格式回复\"$<股票代码,TP\"。\n6. 止损：按以下格式回复\"$<股票代码>,SL\"。\n7. 调整或设置止损：提取止损价，并按以下格式回复\"$<股票代码,MS,S=<止损价>\"。注意若未提及止损价，比如只是说Vwap, ema之类的，则回复ign。\n\n## 举例\n推文：Took CADA 2.3\n回复内容：$CADA,BTO,O=2.3\n\n推文：GLTO bouncing off EMA\n回复内容：ign\n\n推文：Took MRM 2.50: MRM < $3 - Series A Round Valuation stop under 2.10\n回复内容：$MRM,BTO,O=2.50,S=2.1\n\n推文：BJDX going for downtrend break at this point stop loss under 3.80\n回复内容：$BJDX,MS,S=3.8\n\n推文：ABCD took some profit at 3.2 and holding runners. Stop under 3 for the rest.\n回复内容：$ABCD,TP;$ABCD,MS,S=3\n\n## 注意：\n禁止回复任何分析、描述，只可按上面提到的格式回复。"
                    }
                ]
                },
                {
                "role": "user",
                "content": [
                    {
                    "type": "input_text",
                    "text": message
                    }
                ]
                }
            ],
            text={
                "format": {
                "type": "text"
                }
            },
            reasoning={},
            tools=[],
            temperature=1,
            max_output_tokens=2048,
            top_p=1,
            store=False,
            include=["web_search_call.action.sources"]
        )
        return {
            'error': response.error,
            'response': response.output_text
        }

        
    def shutdown(self, wait: bool = True):
        """
        Shutdown the thread pool. Call this when the analyser is no longer needed.
        """
        self.executor.shutdown(wait=wait)
    
    def __del__(self):
        """
        Cleanup when the object is destroyed.
        """
        try:
            self.shutdown(wait=False)
        except:
            pass