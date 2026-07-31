# -*- coding: utf-8 -*-
"""音效常量与扩展名配置。"""

from __future__ import annotations

import os

# 配置值 sound_id：system | soft | chime | alert | custom
SOUND_ID_SYSTEM = "system"
SOUND_ID_SOFT = "soft"
SOUND_ID_CHIME = "chime"
SOUND_ID_ALERT = "alert"
SOUND_ID_CUSTOM = "custom"

SOUND_PRESETS = (
    (SOUND_ID_SYSTEM, "系统铃声"),
    (SOUND_ID_SOFT, "柔和提示"),
    (SOUND_ID_CHIME, "清脆钟声"),
    (SOUND_ID_ALERT, "紧急警报"),
)

# 历史自定义音效条数上限
SOUND_HISTORY_MAX = 12

_PRESET_FILES = {
    SOUND_ID_SOFT: os.path.join("assets", "sounds", "soft.wav"),
    SOUND_ID_CHIME: os.path.join("assets", "sounds", "chime.wav"),
    SOUND_ID_ALERT: os.path.join("assets", "sounds", "alert.wav"),
}

_AUDIO_EXTS = (
    ".wav",
    ".wave",
    ".mp3",
    ".aiff",
    ".aif",
    ".m4a",
    ".aac",
    ".ogg",
    ".flac",
    ".ncm",
)

# 文件选择对话框用的扩展名字符串
AUDIO_FILETYPES = [
    ("音频文件", "*.wav *.wave *.mp3 *.aiff *.aif *.m4a *.aac *.ogg *.flac *.ncm"),
    ("网易云 NCM", "*.ncm"),
    ("WAV", "*.wav *.wave"),
    ("所有文件", "*.*"),
]

# 路径探测超时：网络盘/失效 UNC 上 isfile 可能挂死主线程
_PATH_EXIST_TIMEOUT_S = 0.4

# 非 WAV 无法读时长时的保守估计（秒）
_DEFAULT_AUDIO_SECONDS = 30.0
_PENDING_PREPARE_SECONDS = 120.0

# Windows MCI 别名：同一时刻只保留一路结束音效
_WIN_MCI_ALIAS = "cdt_finish_sound"

# 系统铃声重复次数与间隔（毫秒）
_SYSTEM_BELL_TIMES = 3
_SYSTEM_BELL_INTERVAL_MS = 400
