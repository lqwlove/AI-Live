import logging
import random
import re

from openai import OpenAI

logger = logging.getLogger(__name__)

MULTILANG_SUFFIX = (
    "\n\n【输出规则】"
    "先判断观众消息的语言，在回复最前面标注语言标签后紧跟回复内容。"
    "格式：[zh]中文回复 或 [en]English reply。"
    "用观众使用的语言进行回复。只输出一种语言，不要混合。"
)

_LANG_TAG_RE = re.compile(r"^\[(\w{2})](.+)$", re.DOTALL)


def parse_lang_reply(raw: str) -> tuple[str, str]:
    """解析 AI 回复中的语言标签，返回 (lang, reply_text)"""
    m = _LANG_TAG_RE.match(raw.strip())
    if m:
        return m.group(1).lower(), m.group(2).strip()
    return "zh", raw.strip()


class AIReplier:
    """调用 LLM API 生成直播间回复"""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        system_prompt: str,
        max_history: int = 10,
        multilang: bool = False,
    ):
        self.model = model
        self.multilang = multilang
        self.system_prompt = system_prompt
        if multilang:
            self.system_prompt += MULTILANG_SUFFIX
        self.max_history = max_history
        self._history: list[dict] = []
        self._mock_mode = not api_key or api_key == "your-api-key-here"

        if self._mock_mode:
            self.client = None
            logger.warning("未配置 AI API Key，使用模拟回复模式")
        else:
            self.client = OpenAI(api_key=api_key, base_url=base_url)

    def reply(self, user: str, content: str) -> tuple[str, str]:
        """返回 (lang, reply_text)。非多语言模式 lang 固定 'zh'。"""
        if self._mock_mode:
            return self._mock_reply(user, content)

        user_msg = f"观众「{user}」说：{content}"
        self._history.append({"role": "user", "content": user_msg})

        if len(self._history) > self.max_history * 2:
            self._history = self._history[-self.max_history * 2 :]

        messages = [
            {"role": "system", "content": self.system_prompt},
            *self._history,
        ]

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=150,
                temperature=0.8,
            )
            raw = resp.choices[0].message.content.strip()
            self._history.append({"role": "assistant", "content": raw})

            if self.multilang:
                lang, reply_text = parse_lang_reply(raw)
            else:
                lang, reply_text = "zh", raw

            logger.info(f"AI 回复 [{user}] (lang={lang}): {reply_text}")
            return lang, reply_text
        except Exception as e:
            logger.error(f"AI 回复生成失败: {e}")
            return "zh", ""

    def _mock_reply(self, user: str, content: str) -> tuple[str, str]:
        """模拟回复，用于测试完整流程"""
        zh_templates = [
            f"谢谢{user}的提问！这个问题问得很好，我们正在讲解中哦。",
            f"{user}你好！感谢关注，稍后会详细介绍的。",
            f"好问题！{user}，我们马上就说到这个了。",
        ]
        en_templates = [
            f"Thanks for asking, {user}! Great question, we're covering that now.",
            f"Hi {user}! Thanks for watching, we'll explain that soon.",
            f"Good question {user}! Stay tuned, we'll get to that.",
        ]
        if (
            self.multilang
            and any(c.isascii() for c in content)
            and not any("\u4e00" <= c <= "\u9fff" for c in content)
        ):
            reply = random.choice(en_templates)
            lang = "en"
        else:
            reply = random.choice(zh_templates)
            lang = "zh"
        logger.info(f"模拟回复 [{user}] (lang={lang}): {reply}")
        return lang, reply

    def batch_reply(self, comments: list[dict]) -> tuple[str, str]:
        """Process a batch of comments with a single LLM call (simple mode)."""
        if self._mock_mode:
            users = [c["user"] for c in comments]
            return self._mock_reply(
                users[0] if users else "观众",
                comments[0]["content"] if comments else "",
            )

        formatted = "\n".join(f"- {c['user']}：{c['content']}" for c in comments)
        user_msg = f"以下是最近一批观众评论，请挑重点统一回复：\n{formatted}"
        self._history.append({"role": "user", "content": user_msg})

        if len(self._history) > self.max_history * 2:
            self._history = self._history[-self.max_history * 2 :]

        messages = [
            {"role": "system", "content": self.system_prompt},
            *self._history,
        ]

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=250,
                temperature=0.8,
            )
            raw = resp.choices[0].message.content.strip()
            self._history.append({"role": "assistant", "content": raw})

            if self.multilang:
                return parse_lang_reply(raw)
            return "zh", raw
        except Exception as e:
            logger.error(f"AI 批量回复生成失败: {e}")
            return "zh", ""

    def clear_history(self):
        self._history.clear()
