# -*- coding: utf-8 -*-
"""轻量设计 token（间距 / 圆角 / 字号 / 设置窗尺寸）。"""

# 间距
SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 12
SPACE_LG = 16
SPACE_XL = 24

# 圆角（CARD=14 对齐主窗卡片既有视觉）
RADIUS_SM = 8  # → BTN_RADIUS；pill/chip 语义目标
RADIUS_MD = 12  # 备用：中等圆角（对话框/次级卡片可选用）
RADIUS_CARD = 14
RADIUS_LG = 16

# 字号（传给 app._font 的 size）
FONT_META = 8
FONT_CAPTION = 9
FONT_BODY = 10
FONT_SECTION = 11
FONT_ICON = 12
FONT_TITLE = 13
FONT_SPIN = 14

# 主窗 / 标题栏几何（语义命名，数值对齐既有布局）
MAIN_CONTENT_PAD_X = 22
MAIN_CONTENT_PAD_Y_TOP = 14
MAIN_CONTENT_PAD_Y_BOTTOM = SPACE_LG
MAIN_TITLE_HEIGHT = 48
DIALOG_TITLE_HEIGHT = 40
CIRCLE_BTN_SIZE = SPACE_LG

# 按钮几何（ttk 主按钮 / make_pill / make_chip 共用；勿再散落魔法数）
# - ttk Accent|Primary*|Secondary.padding ↔ PILL_PAD_*
# - make_pill padx/pady ↔ PILL_PAD_*
# - make_chip 更紧凑，用 CHIP_PAD_*
CHIP_PAD_X = SPACE_SM
CHIP_PAD_Y = 5
PILL_PAD_X = 14
PILL_PAD_Y = 6
BTN_PAD_X = PILL_PAD_X
BTN_PAD_Y = PILL_PAD_Y
# 主按钮字号：对齐 FONTS["button"] / FONT_SECTION；pill primary 同此
BTN_FONT_SIZE = FONT_SECTION
# 圆角语义目标（ttk clam 难画圆角；pill/chip 靠 Label 内边距近似）
BTN_RADIUS = RADIUS_SM

PROGRESS_BAR_H = SPACE_XS

# 设置中心窗口（与主窗 500 宽对齐；高度含自绘标题栏 + Tab）
SETTINGS_WIDTH = 500
SETTINGS_HEIGHT = 560

# 更新对话框
UPDATE_DIALOG_WIDTH = 420
UPDATE_DIALOG_MIN_HEIGHT = 280
