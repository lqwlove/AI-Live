"""
AI 与火山引擎 TTS 凭证（仅服务端使用，不经由 Web 与 config.yaml 配置）。

优先读取环境变量；未设置时使用下方默认值。请勿将含真实密钥的版本推送到公开仓库。

环境变量：
  TK_LIVE_AI_API_KEY / TK_LIVE_AI_BASE_URL
  TK_LIVE_VOLCENGINE_API_KEY / TK_LIVE_VOLCENGINE_APP_ID /
  TK_LIVE_VOLCENGINE_ACCESS_TOKEN / TK_LIVE_VOLCENGINE_SPEAKER_ID /
  TK_LIVE_VOLCENGINE_RESOURCE_ID
"""

import os

# ---- AI（OpenAI 兼容接口，如豆包 Ark）----
_DEFAULT_AI_API_KEY = "79c610a0-5e8e-4974-a6f0-0d7828092af4"
_DEFAULT_AI_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"

# ---- 火山引擎语音合成（与控制台「语音合成」一致）----
_DEFAULT_VOLCENGINE: dict[str, str] = {
    "api_key": "",
    "app_id": "1918430576",
    "access_token": "j_sj8RmyeK67Jkn5I9XynxoF9W4sIuHZ",
    "speaker_id": "zh_female_vv_uranus_bigtts",
    "resource_id": "seed-tts-2.0",
}


def get_ai_api_key() -> str:
    return (os.environ.get("TK_LIVE_AI_API_KEY") or _DEFAULT_AI_API_KEY).strip()


def get_ai_base_url() -> str:
    return (os.environ.get("TK_LIVE_AI_BASE_URL") or _DEFAULT_AI_BASE_URL).strip()


def get_volcengine_config() -> dict[str, str]:
    out = dict(_DEFAULT_VOLCENGINE)
    env_map = {
        "api_key": "TK_LIVE_VOLCENGINE_API_KEY",
        "app_id": "TK_LIVE_VOLCENGINE_APP_ID",
        "access_token": "TK_LIVE_VOLCENGINE_ACCESS_TOKEN",
        "speaker_id": "TK_LIVE_VOLCENGINE_SPEAKER_ID",
        "resource_id": "TK_LIVE_VOLCENGINE_RESOURCE_ID",
    }
    for key, env_name in env_map.items():
        val = os.environ.get(env_name)
        if val is not None and str(val).strip() != "":
            out[key] = str(val).strip()
    return out
