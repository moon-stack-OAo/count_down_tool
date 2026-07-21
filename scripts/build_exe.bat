@echo off
chcp 65001 >nul
title Count Down Tool Builder

rem 脚本位于 scripts/，项目根为上一级
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
for %%I in ("%SCRIPT_DIR%\..") do set "TOOL_DIR=%%~fI"
set "VENV_DIR=%TOOL_DIR%\.venv"
set "PYTHON=%VENV_DIR%\Scripts\python.exe"
set "ICON_FILE=%TOOL_DIR%\assets\count_down_tool.ico"

if not exist "%PYTHON%" (
    echo [ERROR] Python not found at: %PYTHON%
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Building Count Down Tool
echo ========================================
echo.

cd /d "%TOOL_DIR%"

"%PYTHON%" -m PyInstaller --onefile --windowed --icon="%ICON_FILE%" --name "count_down_tool" --add-data "%ICON_FILE%;assets" --hidden-import core --hidden-import core.countdown_core --hidden-import core.themes --hidden-import services.autostart --hidden-import app --hidden-import app.countdown --hidden-import app.config_store --hidden-import app.window_chrome --hidden-import app.theme --hidden-import app.mode --hidden-import ui --hidden-import ui.widgets --hidden-import ui.mini_window --hidden-import ui.time_picker --hidden-import ui.full_window --hidden-import ui.context_menus --hidden-import ui.mini_text_picker --hidden-import services --hidden-import services.tray --hidden-import services.windows_native --hidden-import pystray --hidden-import pystray._win32 --hidden-import PIL --hidden-import PIL._tkinter_finder --distpath "%TOOL_DIR%\dist" --workpath "%TOOL_DIR%\build" --specpath "%TOOL_DIR%" "%TOOL_DIR%\count_down_tool.py"

echo.
echo ========================================
if exist "%TOOL_DIR%\dist\count_down_tool.exe" (
    echo   Build successful!
    echo   File: %TOOL_DIR%\dist\count_down_tool.exe
    echo ========================================
    echo.
    echo   Cleaning build files...
    rd /s /q "%TOOL_DIR%\build"
    del /q "%TOOL_DIR%\count_down_tool.spec" 2>nul
    echo   Done!
    explorer "%TOOL_DIR%\dist"
) else (
    echo   Build failed!
    echo ========================================
)

pause
