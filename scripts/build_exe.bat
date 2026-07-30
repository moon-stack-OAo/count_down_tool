@echo off
setlocal EnableExtensions
title Count Down Tool Builder

rem Optional: build_exe.bat /nopause  (skip pause at end, for CI/tools)
set "NO_PAUSE=0"
if /I "%~1"=="/nopause" set "NO_PAUSE=1"
if /I "%~1"=="--nopause" set "NO_PAUSE=1"

rem Script under scripts/; project root is parent
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
for %%I in ("%SCRIPT_DIR%\..") do set "TOOL_DIR=%%~fI"
set "VENV_DIR=%TOOL_DIR%\.venv"
set "PYTHON=%VENV_DIR%\Scripts\python.exe"
set "ICON_FILE=%TOOL_DIR%\assets\count_down_tool.ico"
set "VER_FILE=%TEMP%\count_down_tool_version.txt"
set "README_SRC=%TOOL_DIR%\docs\readme.txt"

if not exist "%PYTHON%" (
    echo [ERROR] Python not found: %PYTHON%
    echo Create venv first: python -m venv .venv
    if "%NO_PAUSE%"=="0" pause
    exit /b 1
)

echo.
echo ========================================
echo   Building Count Down Tool (onedir)
echo ========================================
echo.

cd /d "%TOOL_DIR%"
if errorlevel 1 (
    echo [ERROR] Cannot cd to: %TOOL_DIR%
    if "%NO_PAUSE%"=="0" pause
    exit /b 1
)

set "VERSION="
"%PYTHON%" -c "from core.countdown_core import __version__; print(__version__, end='')" > "%VER_FILE%"
if errorlevel 1 (
    echo [ERROR] Failed to read __version__ from core.countdown_core
    if "%NO_PAUSE%"=="0" pause
    exit /b 1
)
set /p VERSION=<"%VER_FILE%"
del /q "%VER_FILE%" 2>nul
if not defined VERSION (
    echo [ERROR] Empty __version__
    if "%NO_PAUSE%"=="0" pause
    exit /b 1
)

set "OUT_ZIP=count_down_tool-%VERSION%-win64.zip"
set "APP_DIR=%TOOL_DIR%\dist\count_down_tool"
echo   Version: %VERSION%
echo   App:     dist\count_down_tool\count_down_tool.exe
echo   Zip:     dist\%OUT_ZIP%
echo.

rem onedir: DLLs next to exe (avoid onefile %%TEMP%%\_MEI* / python3xx.dll load failures)
"%PYTHON%" -m PyInstaller --noconfirm --clean --onedir --windowed --icon="%ICON_FILE%" --name "count_down_tool" --add-data "%ICON_FILE%;assets" --add-data "%TOOL_DIR%\assets\sounds;assets/sounds" --add-data "%TOOL_DIR%\assets\fonts;assets/fonts" --hidden-import core --hidden-import core.countdown_core --hidden-import core.app_logging --hidden-import core.themes --hidden-import core.fonts --hidden-import core.update --hidden-import services.autostart --hidden-import app --hidden-import app.countdown --hidden-import app.config_store --hidden-import app.window_chrome --hidden-import app.theme --hidden-import app.mode --hidden-import ui --hidden-import ui.widgets --hidden-import ui.mini_window --hidden-import ui.time_picker --hidden-import ui.full_window --hidden-import ui.context_menus --hidden-import ui.mini_text_picker --hidden-import ui.settings_window --hidden-import ui.update_dialog --hidden-import ui.app_dialogs --hidden-import ui.window_chrome_dialog --hidden-import ui.design --hidden-import ui.design.tokens --hidden-import services --hidden-import services.tray --hidden-import services.updater --hidden-import services.sound --hidden-import services.ncm --hidden-import services.windows_native --hidden-import pystray --hidden-import pystray._win32 --hidden-import PIL --hidden-import PIL._tkinter_finder --distpath "%TOOL_DIR%\dist" --workpath "%TOOL_DIR%\build" --specpath "%TOOL_DIR%" "%TOOL_DIR%\count_down_tool.py"
if errorlevel 1 (
    echo.
    echo   [ERROR] PyInstaller failed
    echo ========================================
    if "%NO_PAUSE%"=="0" pause
    exit /b 1
)

echo.
echo ========================================
if not exist "%APP_DIR%\count_down_tool.exe" (
    echo   [ERROR] Build failed: exe not found
    echo   Expected: %APP_DIR%\count_down_tool.exe
    echo ========================================
    if "%NO_PAUSE%"=="0" pause
    exit /b 1
)

if exist "%TOOL_DIR%\dist\%OUT_ZIP%" del /q "%TOOL_DIR%\dist\%OUT_ZIP%"

rem Ship readme next to exe (not inside _internal)
if exist "%README_SRC%" (
    copy /Y "%README_SRC%" "%APP_DIR%\readme.txt" >nul
)

rem Zip onedir contents (exe + _internal + readme)
rem Use simple paths (PS 5.1 Join-Path may lack -LiteralPath)
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path '%APP_DIR%\*' -DestinationPath '%TOOL_DIR%\dist\%OUT_ZIP%' -Force"
if not exist "%TOOL_DIR%\dist\%OUT_ZIP%" (
    echo   [ERROR] Failed to create zip
    echo ========================================
    if "%NO_PAUSE%"=="0" pause
    exit /b 1
)

echo   Build successful!
echo   Zip: %TOOL_DIR%\dist\%OUT_ZIP%
echo ========================================
echo.
echo   Cleaning build files...
rem Keep only zip under dist; remove onedir folder, build, and .spec
rd /s /q "%APP_DIR%" 2>nul
rd /s /q "%TOOL_DIR%\build" 2>nul
del /q "%TOOL_DIR%\count_down_tool.spec" 2>nul
echo   Done!
if "%NO_PAUSE%"=="0" (
    explorer "%TOOL_DIR%\dist"
    pause
)

endlocal
exit /b 0
