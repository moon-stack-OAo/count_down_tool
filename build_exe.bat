@echo off
chcp 65001 >nul
title Count Down Tool Builder

set "TOOL_DIR=%~dp0"
if "%TOOL_DIR:~-1%"=="\" set "TOOL_DIR=%TOOL_DIR:~0,-1%"
set "VENV_DIR=%TOOL_DIR%\.venv"
set "PYTHON=%VENV_DIR%\Scripts\python.exe"

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

"%PYTHON%" -m PyInstaller --onefile --windowed --icon="%TOOL_DIR%\count_down_tool.ico" --name "count_down_tool" --add-data "%TOOL_DIR%\count_down_tool.ico;." --hidden-import countdown_core --hidden-import themes --hidden-import autostart --hidden-import ui --hidden-import ui.widgets --hidden-import ui.mini_window --hidden-import ui.time_picker --hidden-import ui.full_window --hidden-import services --hidden-import services.tray --hidden-import services.windows_native --hidden-import pystray --hidden-import pystray._win32 --hidden-import PIL --hidden-import PIL._tkinter_finder --distpath "%TOOL_DIR%\dist" --workpath "%TOOL_DIR%\build" --specpath "%TOOL_DIR%" "%TOOL_DIR%\count_down_tool.py"

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
