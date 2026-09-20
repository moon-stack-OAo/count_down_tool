# -*- coding: utf-8 -*-
"""轻量设计 token（间距 / 圆角 / 字号 / 设置窗尺寸）。"""

# 间距（与 DESIGN 一致）
SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 12
SPACE_LG = 16
SPACE_XL = 24

# 圆角（视觉焕新：略收，层次靠边框）
RADIUS_SM = 6  # Chip、小按钮、输入框
RADIUS_MD = 10  # 卡片、主按钮
RADIUS_CARD = 10
RADIUS_LG = 12  # 对话框面板

# 字号（传给 app._font 的 size；分阶段微调，避免大改溢出）
FONT_META = 9
FONT_CAPTION = 10
FONT_BODY = 11
FONT_SECTION = 12
FONT_ICON = 12
FONT_TITLE = 14
FONT_SPIN = 14

# 主窗内容区边距
MAIN_CONTENT_PAD_X = 16
MAIN_CONTENT_PAD_Y_TOP = 16
MAIN_CONTENT_PAD_Y_BOTTOM = SPACE_LG

# 按钮几何（ttk 主按钮 / make_pill / make_chip 共用；勿再散落魔法数）
CHIP_PAD_X = 10
CHIP_PAD_Y = 5
PILL_PAD_X = 14
PILL_PAD_Y = 6
BTN_PAD_X = PILL_PAD_X
BTN_PAD_Y = PILL_PAD_Y
BTN_FONT_SIZE = FONT_SECTION
BTN_RADIUS = RADIUS_SM

PROGRESS_BAR_H = SPACE_XS

# 设置中心窗口
SETTINGS_WIDTH = 500
SETTINGS_HEIGHT = 560
SETTINGS_ALPHA = 0.94  # 略半透明（平台不支持则静默跳过）
SETTINGS_BESIDE_GAP = 16  # 相对父窗水平间距（像素）

# 更新对话框
UPDATE_DIALOG_WIDTH = 420
UPDATE_DIALOG_MIN_HEIGHT = 280
