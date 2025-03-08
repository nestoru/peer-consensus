"""
Module: peer_consensus.llm_providers
This module implements the two supported LLM providers:
    - openai-chatgpt
    - anthropic-claude
"""

from abc import ABC, abstractmethod
from typing import List, Dict
import openai
import requests
from peer_consensus.utils.logging import get_logger

logger = get_logger(__name__)

class BaseGPT(ABC):
    """Base class for GPT implementations."""
    def __init__(self, api_key: str, model_name: str):
        self.api_key = api_key
        self.model_name = model_name

    @abstractmethod
    def generate_completion(self, messages: List[Dict]) -> str:
        """Generate a completion from a list of message dicts."""
        pass

class OpenAIGPT(BaseGPT):
    """OpenAI ChatGPT implementation."""
    def __init__(self, api_key: str, model_name: str):
        super().__init__(api_key, model_name)
        openai.api_key = api_key

    def generate_completion(self, messages: List[Dict]) -> str:
        response = openai.ChatCompletion.create(
            model=self.model_name,
            messages=messages,
        )
        return response.choices[0]["message"]["content"]

class AnthropicClaudeGPT(BaseGPT):
    """Anthropic Claude GPT implementation."""
    ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
    ANTHROPIC_VERSION = "2023-06-01"

    def __init__(self, api_key: str, model_name: str):
        super().__init__(api_key, model_name)

    def generate_completion(self, messages: List[Dict]) -> str:
        # Format messages into a single prompt string.
        prompt = ""
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            prompt += f"\n\n{role.upper()}: {content}"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.ANTHROPIC_VERSION,
            "Content-Type": "application/json"
        }
        request_body = {
            "model": self.model_name,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}]
        }
        try:
            response = requests.post(self.ANTHROPIC_API_URL, headers=headers, json=request_body)
            if response.status_code == 200:
                resp_json = response.json()
                if "content" in resp_json:
                    content_list = resp_json["content"]
                    if isinstance(content_list, list) and len(content_list) > 0:
                        return content_list[0].get("text", "")
                else:
                    logger.error("Anthropic response missing 'content': %s", resp_json)
            else:
                logger.error("Anthropic API error %s: %s", response.status_code, response.text)
        except Exception as e:
            logger.error("Error during Anthropic request: %s", e)
        return ""

def get_gpt_implementation(api_key: str, model_name: str, model_provider: str) -> BaseGPT:
    """
    Factory function to return the appropriate GPT implementation.
    
    Supported providers:
      - "openai-chatgpt"
      - "anthropic-claude"
    """
    if model_provider == "openai-chatgpt":
        return OpenAIGPT(api_key, model_name)
    elif model_provider == "anthropic-claude":
        return AnthropicClaudeGPT(api_key, model_name)
    else:
        raise ValueError(f"Unsupported model provider: {model_provider}")

