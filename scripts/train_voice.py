#!/usr/bin/env python3
"""
火山引擎声音复刻 — 一次性训练脚本

用法:
  python scripts/train_voice.py \
    --app-id YOUR_APP_ID \
    --access-token YOUR_ACCESS_TOKEN \
    --audio sample_voice.wav \
    --speaker-name "my-live-voice"

说明:
  1. 准备一段 10~60 秒的清晰人声录音（WAV / MP3）
  2. 运行本脚本完成声音复刻训练
  3. 训练成功后获得 speaker_id，写入 config.yaml 的 volcengine.speaker_id
  4. 训练是一次性操作，之后在直播中直接使用合成接口
"""

import argparse
import base64
import json
import logging
import sys
import time

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TRAIN_URL = "https://openspeech.bytedance.com/api/v1/vc/train"
STATUS_URL = "https://openspeech.bytedance.com/api/v1/vc/status"


def read_audio_b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def train(app_id: str, access_token: str, audio_path: str, speaker_name: str):
    audio_b64 = read_audio_b64(audio_path)
    suffix = audio_path.rsplit(".", 1)[-1].lower()

    headers = {
        "X-Api-App-Id": app_id,
        "X-Api-Access-Key": access_token,
        "Content-Type": "application/json",
    }

    payload = {
        "speaker_name": speaker_name,
        "audio": {
            "data": audio_b64,
            "format": suffix,
        },
    }

    logger.info(f"正在提交声音复刻训练任务 [{speaker_name}]...")
    resp = requests.post(TRAIN_URL, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    result = resp.json()

    if result.get("code") != 0:
        logger.error(f"训练提交失败: {json.dumps(result, ensure_ascii=False)}")
        sys.exit(1)

    task_id = result["data"]["task_id"]
    logger.info(f"训练任务已提交，task_id = {task_id}")
    logger.info("等待训练完成（通常需要 1~5 分钟）...")

    while True:
        time.sleep(10)
        status_resp = requests.get(
            STATUS_URL,
            headers=headers,
            params={"task_id": task_id},
            timeout=30,
        )
        status_resp.raise_for_status()
        status = status_resp.json()

        state = status.get("data", {}).get("status", "unknown")
        logger.info(f"训练状态: {state}")

        if state == "success":
            speaker_id = status["data"]["speaker_id"]
            logger.info("=" * 50)
            logger.info(f"训练完成！speaker_id = {speaker_id}")
            logger.info("请将此 speaker_id 填写到 config.yaml 的 volcengine.speaker_id 中")
            logger.info("=" * 50)
            return speaker_id
        elif state in ("failed", "error"):
            logger.error(f"训练失败: {json.dumps(status, ensure_ascii=False)}")
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="火山引擎声音复刻训练")
    parser.add_argument("--app-id", required=True, help="火山引擎 App ID")
    parser.add_argument("--access-token", required=True, help="火山引擎 Access Token")
    parser.add_argument("--audio", required=True, help="训练用音频文件路径（WAV/MP3，10~60秒清晰人声）")
    parser.add_argument("--speaker-name", default="live-host-voice", help="音色名称")
    args = parser.parse_args()

    train(args.app_id, args.access_token, args.audio, args.speaker_name)


if __name__ == "__main__":
    main()
