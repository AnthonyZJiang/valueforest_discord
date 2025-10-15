from openai import OpenAI
from discord_webhook import DiscordWebhook
import json
import re
from concurrent.futures import ThreadPoolExecutor
import threading
import discord
import logging
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class LLMAnalyser:
    def __init__(self, webhook_url: str | list[str], max_workers: int = 3):
        self.openai_client = OpenAI()
        self.webhook_urls = webhook_url if isinstance(webhook_url, list) else [webhook_url]
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="LLMAnalyser")
        self._lock = threading.Lock()
        self.time_start = time.perf_counter()

    def analyse(self, message: discord.Message):
        self.time_start = time.perf_counter()
        logger.info(f"Analysing message {message.id} from {message.author.display_name} in {message.channel.name}.")
        cleaned_content = self._cleanup_message(message.content)
        if not cleaned_content:
            return
        msg = {
            "content": cleaned_content,
            "original_message": message
        }
        future = self.executor.submit(self._analyse_sync, msg)
        return future
    
    def _analyse_sync(self, message: dict):
        """
        Synchronous analysis method that runs in the thread pool.
        """
        try:
            response = self._analyse(message['content'])
        except Exception as e:
            logger.error(f"Failed to analyse message: {e}", exc_info=True)
            response = {
                'error': str(e),
                'response': None
            }
        self._send_message(message, response)
        logger.info(f"Message analysed:\n{json.dumps(message, indent=4)}\n{json.dumps(response, indent=4)}")
        return response
    
    def _cleanup_message(self, message: str):
        # remove timestamp <t:1231245> <t:1231245:R>, emoji <a:emoji_132.abc:321> <:emoji:321>, remove mentions <@!12345> <@3214512> <@&12345> <#32134>
        message = re.sub(r'<[#@:ta][&!]?[^>]+R?>', '', message).strip()
        # remove @everyone, @here, @unknown-role etc.
        message = re.sub(r'@(everyone|here|unknown-role)', '', message)
        # remove links
        message = re.sub(r'https?://[^\s]+', '', message)
        return message.strip()

    def _analyse(self, message: str):
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

    def _send_message(self, message: dict, response: dict):
        try:
            error_message = f"\nError:{response['error']}" if response['error'] else ""
            embeds = self._build_webhook_embeds(message, response['response'])
            for webhook_url in self.webhook_urls:
                webhook = DiscordWebhook(url=webhook_url)
                webhook.content = error_message
                webhook.embeds = embeds
                webhook.username = "LLM Analyser"
                webhook.execute()
            print(f"Webhook message sent.")
        except Exception as e:
            # Log error but don't let it crash the analysis
            logger.error(f"Failed to send webhook message: {e}", exc_info=True)
            
    def _get_actions_from_response(self, response: str):
        #$<股票代码>,BTO,O=<开仓价>,S=<止损价>
        #$<股票代码,TP
        #$<股票代码,SL
        #$<股票代码,MS,S=<止损价>
        #ign
        actions = []
        parts = response.split(";")
        for part in parts:
            if part == 'ign':
                continue
            chunk = part.split(",")
            if len(chunk[0]) < 2:
                # ticker must be at least 2 characters with $
                continue 
            if chunk[1] == 'BTO':
                actions.append({
                    'ticker': chunk[0],
                    'action': 'Buy to open'
                })
            elif chunk[1] == 'TP':
                actions.append({
                    'ticker': chunk[0],
                    'action': 'Sell (take a profit)'
                })
            elif chunk[1] == 'SL':
                actions.append({
                    'ticker': chunk[0],
                    'action': 'Sell (take a loss)'
                })
            elif chunk[1] == 'MS':
                actions.append({
                    'ticker': chunk[0],
                    'action': 'Move stop loss'
                })
            for c in chunk[2:]:
                if c.startswith('O='):
                    actions[-1]['price'] = c[2:]
                elif c.startswith('S='):
                    actions[-1]['stop_loss'] = c[2:]
        return actions
    
    def _build_webhook_embeds(self, message: dict, response: str):
        embeds = []
        dc_msg = message['original_message']
        actions = self._get_actions_from_response(response)
        embed = {
            "description": "",
            "fields": [
            ],
            "author": {
                "name": dc_msg.author.display_name,
                "icon_url": dc_msg.author.avatar.url
            },
            "title": "New alert",
            "url": dc_msg.jump_url
        }
        if actions:
            _prev_ticker = None
            for action in actions:
                _ticker = action['ticker']
                action_str = f"- *Action:* {action['action']}"
                price_str = f"\n- *Open price:* ${action['price']}" if action.get('price') else ""
                stop_loss_str = f"\n- *Stop loss:* ${action['stop_loss']}" if action.get('stop_loss') else ""
                if _ticker != _prev_ticker:
                    embed['fields'].append({
                        "name": f"{_ticker}",
                        "value": f"{action_str}{price_str}{stop_loss_str}",
                        "inline": False
                    })
                    _prev_ticker = _ticker
                else:
                    embed['fields'][-1]['value'] += f"\n{action_str}{price_str}{stop_loss_str}"
        else:
            embed["description"] = "No actions."
        embed['fields'].append({
            "name": "Original post",
            "value": message['content']
            })
        embed['fields'].append({
            "name": "Time reference",
            "value": f"Posted at <t:{int(dc_msg.created_at.timestamp())}> ({dc_msg.created_at.second}s)\nDelay since post: {(datetime.now(timezone.utc).second - dc_msg.created_at.second):.2f}s"
            })
        embeds.append(embed)
        return embeds
        
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