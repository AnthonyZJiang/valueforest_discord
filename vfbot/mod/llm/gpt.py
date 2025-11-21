from __future__ import annotations
from typing import TYPE_CHECKING
import re
from concurrent.futures import ThreadPoolExecutor
import threading
import logging
import time

from openai import OpenAI


CHATGPT_PROMPT_ID = "pmpt_68e8333a6adc8193985f9321e7f67b5b0a798ea7eb9aacb5"
CHATGPT_PROMPT_VERSION = "10"

if __name__ != "__main__":
    from .actionserver_webhook import ActionServer
    
    if TYPE_CHECKING:
        from ..vfmessage import VFMessage

    logger = logging.getLogger(__name__)


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

        def analyse(self, message: VFMessage):
            self.time_start = time.perf_counter()
            logger.info(f"Analysing message from {message.author_name} in {message.raw_msg_carrier.channel.name}.")
            cleaned_content = self._cleanup_message(message.cleaned_content)
            if not cleaned_content:
                return
            msg = {
                "content": cleaned_content,
                "dc_msg": message.raw_msg_carrier
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
            # remove @everyone, @here, @unknown-role, <@role_id>, etc.
            message = re.sub(r'@(everyone|here|unknown-role)|<@&\d+>', '', message)
            # remove links
            message = re.sub(r'https?://[^\s]+', '', message)
            # remove contents starting with "-# " until the next "\n"
            message = re.sub(r'(^-# :small_)[^\n]*\n+', '', message)
            return message.strip()

        def _get_response_from_llm(self, message: str):
            response = self.openai_client.responses.create(
                prompt={
                    "id": CHATGPT_PROMPT_ID,
                    "version": CHATGPT_PROMPT_VERSION
                },
                input=[
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
                max_output_tokens=2048,
                store=True,
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
else:
    import dotenv
    dotenv.load_dotenv()
    openai_client = OpenAI()
    response = openai_client.responses.create(
        prompt={
                "id": CHATGPT_PROMPT_ID,
                "version": CHATGPT_PROMPT_VERSION
            },
            input=[
                {
                "role": "user",
                "content": [
                    {
                    "type": "input_text",
                    "text": "GSIT - read that"
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
            max_output_tokens=2048,
            store=True,
            include=["web_search_call.action.sources"]
    )
    print(response.output_text)