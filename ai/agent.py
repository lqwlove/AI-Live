"""
LangChain Agent for live-stream AI assistant.

Wraps ChatOpenAI with tools (product search) and sliding-window memory.
Exposes batch_reply() / reply() with the same return signature as AIReplier.
"""

import logging
import random
import re

from langchain_openai import ChatOpenAI
from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    SystemMessage,
    trim_messages,
)
from langchain_core.tools import tool as langchain_tool

from ai.replier import parse_lang_reply, MULTILANG_SUFFIX

logger = logging.getLogger(__name__)


def _build_product_search_tool(product_store):
    """Create a LangChain tool bound to a ProductStore instance."""

    @langchain_tool
    def product_search(query: str) -> str:
        """搜索直播间商品信息。当观众询问商品价格、功效、优惠、推荐等问题时使用此工具。"""
        product_store.load()
        all_products = product_store.get_all()
        logger.info(
            f'[Tool] product_search(query="{query}"), 商品库共 {len(all_products)} 个商品'
        )
        products = product_store.search(query)
        if not products:
            logger.info(f"[Tool] 未匹配到商品")
            return "当前直播间没有匹配的商品信息。"
        names = [p.name for p in products]
        logger.info(f"[Tool] 匹配到 {len(products)} 个商品: {names}")
        return product_store.format_for_prompt(products)

    return product_search


class LiveAgent:
    """LangChain Agent that replaces AIReplier with tool-calling and memory."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        system_prompt: str,
        max_history: int = 10,
        multilang: bool = False,
        product_store=None,
    ):
        self.multilang = multilang
        self.system_prompt = system_prompt
        if multilang:
            self.system_prompt += MULTILANG_SUFFIX
        self.max_history = max_history
        self._mock_mode = not api_key or api_key == "your-api-key-here"
        self._history: list = []

        self.tools = []
        if product_store is not None:
            self.tools.append(_build_product_search_tool(product_store))

        if self._mock_mode:
            self.llm = None
            logger.warning("未配置 AI API Key，Agent 使用模拟回复模式")
        else:
            self.llm = ChatOpenAI(
                api_key=api_key,
                base_url=base_url,
                model=model,
                max_tokens=250,
                temperature=0.8,
            )
            if self.tools:
                self.llm_with_tools = self.llm.bind_tools(self.tools)
            else:
                self.llm_with_tools = self.llm

    def _trim_history(self):
        max_messages = self.max_history * 2
        if len(self._history) > max_messages:
            self._history = self._history[-max_messages:]

    def _invoke_with_tools(self, user_message: str) -> str:
        """Single LLM call with optional tool use (iterative)."""
        self._trim_history()
        messages = [
            SystemMessage(content=self.system_prompt),
            *self._history,
            HumanMessage(content=user_message),
        ]

        tool_map = {t.name: t for t in self.tools}

        for round_i in range(3):
            response = self.llm_with_tools.invoke(messages)
            messages.append(response)

            if not response.tool_calls:
                logger.info(f"[Agent] 第{round_i+1}轮: LLM 直接回复，无工具调用")
                break

            from langchain_core.messages import ToolMessage

            for tc in response.tool_calls:
                logger.info(
                    f"[Agent] 第{round_i+1}轮: 调用工具 {tc['name']}({tc['args']})"
                )
                fn = tool_map.get(tc["name"])
                if fn:
                    result = fn.invoke(tc["args"])
                else:
                    result = f"Unknown tool: {tc['name']}"
                logger.info(f"[Agent] 工具返回: {str(result)[:200]}")
                messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
        else:
            response = self.llm.invoke(messages)
            messages.append(response)

        raw = response.content or ""
        self._history.append(HumanMessage(content=user_message))
        self._history.append(AIMessage(content=raw))
        return raw.strip()

    def batch_reply(self, comments: list[dict]) -> tuple[str, str]:
        """
        Process a batch of comments and return a single combined reply.
        comments: [{"user": "A", "content": "..."}, ...]
        Returns: (lang, reply_text)
        """
        if self._mock_mode:
            return self._mock_batch_reply(comments)

        formatted = "\n".join(f"- {c['user']}：{c['content']}" for c in comments)
        user_msg = f"以下是最近一批观众评论，请挑重点统一回复：\n{formatted}"

        raw = self._invoke_with_tools(user_msg)
        if not raw:
            return "zh", ""

        if self.multilang:
            return parse_lang_reply(raw)
        return "zh", raw

    def reply(self, user: str, content: str) -> tuple[str, str]:
        """Single-comment reply (CLI compatibility)."""
        return self.batch_reply([{"user": user, "content": content}])

    def _mock_batch_reply(self, comments: list[dict]) -> tuple[str, str]:
        users = [c["user"] for c in comments]
        names = "、".join(users[:3])
        if len(users) > 3:
            names += f"等{len(users)}位观众"
        templates = [
            f"感谢{names}的提问！这些问题问得很好，我们正在讲解中哦。",
            f"谢谢{names}的关注！稍后会详细介绍的。",
            f"好问题！{names}，我们马上就说到这个了。",
        ]
        reply = random.choice(templates)
        logger.info(f"模拟批量回复 ({len(comments)} 条): {reply}")
        return "zh", reply

    def clear_history(self):
        self._history.clear()
