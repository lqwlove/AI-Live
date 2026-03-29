# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for tk-live.

Build:
    pyinstaller tk-live.spec

Prerequisites:
    1. cd web && npm install && npm run build && cd ..
    2. pip install pyinstaller
"""

import os
import sys

block_cipher = None

a = Analysis(
    ["server.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("web/dist", "web/dist"),
        ("sign.js", "."),
        ("sign_wrapper.js", "."),
        ("proto/*.py", "proto"),
    ],
    hiddenimports=[
        # uvicorn internals
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.protocols.websockets.wsproto_impl",
        "uvicorn.lifespan.on",
        # fastapi / starlette
        "multipart",
        "multipart.multipart",
        # project modules
        "api",
        "api.app",
        "api.ws",
        "api.routes.health",
        "api.routes.config_routes",
        "api.routes.session",
        "api.routes.products",
        "api.routes.bgm",
        "core",
        "core.engine",
        "core.events",
        "core.session",
        "danmaku",
        "danmaku.client",
        "danmaku.tiktok_client",
        "danmaku.youtube_client",
        "ai",
        "ai.replier",
        "ai.agent",
        "tts",
        "tts.speaker",
        "tts.volcengine_speaker",
        "utils",
        "utils.audio_player",
        "utils.bgm_player",
        "utils.message_queue",
        "utils.paths",
        "knowledge",
        "knowledge.product_store",
        "config",
        "ac_signature",
        "proto",
        "proto.douyin",
        "proto.stream_list_pb2",
        "proto.stream_list_pb2_grpc",
        # third-party
        "tiktoklive",
        "edge_tts",
        "pygame",
        "pygame.mixer",
        "grpc",
        "google.protobuf",
        "google.auth",
        "google_auth_oauthlib",
        "googleapiclient",
        "langchain",
        "langchain_openai",
        "betterproto",
        "yaml",
        "openai",
        "websocket",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "notebook", "scipy", "PIL"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="tk-live",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="tk-live",
)
