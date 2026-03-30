import logging

from openai import OpenAI

logger = logging.getLogger(__name__)

_SYSTEM = (
    "你是翻译助手。将用户输入翻译成简体中文。"
    "只输出译文，不要解释、不要前后缀、不要用引号包裹全文。"
)


class ToZhTranslator:
    def __init__(self, api_key: str, base_url: str, model: str):
        self._mock = not api_key or api_key == "your-api-key-here"
        self.model = model
        self.client: OpenAI | None = None
        if not self._mock:
            self.client = OpenAI(api_key=api_key, base_url=base_url)

    @property
    def available(self) -> bool:
        return not self._mock and self.client is not None

    def translate(self, text: str) -> str:
        if self._mock or not self.client or not (text or "").strip():
            return ""
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": text.strip()},
                ],
                max_tokens=500,
                temperature=0.3,
            )
            out = (resp.choices[0].message.content or "").strip()
            return out
        except Exception as e:
            logger.warning(f"翻译失败: {e}")
            return ""
