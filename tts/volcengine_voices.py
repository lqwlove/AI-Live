"""预设火山引擎音色列表。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class VolcengineVoice:
    id: str  # speaker_id，传给 API 的实际值
    name: str  # 显示名称
    lang: str  # 擅长语言描述（仅展示用）
    resource_id: str  # 火山 API 的资源 ID，必须与 speaker_id 匹配


# 预设音色列表，按照用途排序
VOLCENGINE_VOICES: list[VolcengineVoice] = [
    VolcengineVoice(
        id="zh_female_vv_uranus_bigtts",
        name="vv",
        lang="中英双语(全能)",
        resource_id="seed-tts-2.0",
    ),
    VolcengineVoice(
        id="en_female_dacey_uranus_bigtts",
        name="Dacey",
        lang="美式英语(英语推荐)",
        resource_id="seed-tts-2.0",
    ),
    VolcengineVoice(
        id="zh_female_yingyujiaoxue_uranus_bigtts",
        name="Tina老师",
        lang="中英双语",
        resource_id="seed-tts-2.0",
    ),
    VolcengineVoice(
        id="en_female_lauren_moon_bigtts",
        name="Lauren",
        lang="美式英语",
        resource_id="seed-tts-1.0",
    ),
    VolcengineVoice(
        id="en_female_candice_emo_v2_mars_bigtts",
        name="Candice",
        lang="美式英语",
        resource_id="seed-tts-1.0",
    ),
    VolcengineVoice(
        id="en_female_skye_emo_v2_mars_bigtts",
        name="Serena",
        lang="英语",
        resource_id="seed-tts-1.0",
    ),
    VolcengineVoice(
        id="multi_female_sophie_conversation_wvae_bigtts",
        name="智美",
        lang="日语",
        resource_id="seed-tts-1.0",
    ),
    VolcengineVoice(
        id="multi_female_maomao_conversation_wvae_bigtts",
        name="月",
        lang="日语",
        resource_id="seed-tts-1.0",
    ),
]


def get_voices_dict() -> list[dict]:
    return [
        {"id": v.id, "name": v.name, "lang": v.lang, "resource_id": v.resource_id}
        for v in VOLCENGINE_VOICES
    ]


def get_voice_by_id(speaker_id: str) -> VolcengineVoice | None:
    for v in VOLCENGINE_VOICES:
        if v.id == speaker_id:
            return v
    return None
