# -*- coding: utf-8 -*-
"""设计层入口：tokens + themed 工厂 + 按钮语义。

**tokens**（``ui.design.tokens``）
  间距 ``SPACE_*``、圆角 ``RADIUS_*``、字号 ``FONT_*``、按钮几何 ``BTN_*`` / ``CHIP_*``、
  设置窗/更新对话框尺寸。UI 优先引用 token，避免散落魔法数。

**themed**（本包 re-export）
  ``register_themed`` / ``recolor_*`` / ``themed_frame|label|button``：
  控件登记 COLORS 角色后可就地换肤（主窗 + 设置窗）。

**按钮 / 可点击控件**（勿再长第三套视觉）：

- **ttk Button**（``Accent`` / ``PrimaryRunning`` / ``PrimaryFinished`` / ``Secondary``）
  主窗主操作（开始/暂停/重置）。几何用 ``BTN_PAD_*`` / ``BTN_FONT_SIZE``，
  色走 ``btn_primary`` / ``btn_on_primary`` 等。由 ``ui.full_window.setup_styles`` 注册。
- **make_pill** / **themed_button**
  对话框与设置确认/取消。primary 与 ttk Accent 同色同 pad；``primary=False`` 为次要。
- **make_chip**
  主窗快捷预设、轻量标签按钮；更紧凑（``CHIP_PAD_*`` + ``FONT_CAPTION``），非主 CTA。
- **selectable_row**
  设置列表单选行，不是按钮。

统一入口：对话框优先 ``themed_button``（薄封装 ``make_pill``）；主窗 ttk 勿改用 Label pill。
"""

from ui.design.themed import (  # noqa: F401
    color_of,
    recolor_app,
    recolor_one,
    recolor_widget_tree,
    register_themed,
    resolve_colors,
    themed_button,
    themed_frame,
    themed_label,
)
