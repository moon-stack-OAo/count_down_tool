@echo off
chcp 65001 >nul
setlocal EnableExtensions
title Count Down Tool Builder

rem Script is under scripts/; project root is parent directory
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
for %%I in ("%SCRIPT_DIR%\..") do set "TOOL_DIR=%%~fI"
set "VENV_DIR=%TOOL_DIR%\.venv"
set "PYTHON=%VENV_DIR%\Scripts\python.exe"
set "ICON_FILE=%TOOL_DIR%\assets\count_down_tool.ico"
set "VER_FILE=%TEMP%\count_down_tool_version.txt"

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

rem Read version into zip name; exe stays count_down_tool.exe (same as mac .app)
set "VERSION="
"%PYTHON%" -c "from core.countdown_core import __version__; print(__version__, end='')" > "%VER_FILE%"
if errorlevel 1 (
    echo [ERROR] Failed to read __version__ from core.countdown_core
    pause
    exit /b 1
)
set /p VERSION=<"%VER_FILE%"
del /q "%VER_FILE%" 2>nul
if not defined VERSION (
    echo [ERROR] Failed to read __version__ from core.countdown_core
    pause
    exit /b 1
)
set "OUT_ZIP=count_down_tool-%VERSION%-win64.zip"
echo   Version: %VERSION%
echo   Exe:     dist\count_down_tool.exe
echo   Zip:     dist\%OUT_ZIP%
echo.

"%PYTHON%" -m PyInstaller --onefile --windowed --icon="%ICON_FILE%" --name "count_down_tool" --add-data "%ICON_FILE%;assets" --add-data "%TOOL_DIR%\assets\sounds;assets/sounds" --add-data "%TOOL_DIR%\assets\fonts;assets/fonts" --hidden-import core --hidden-import core.countdown_core --hidden-import core.themes --hidden-import core.fonts --hidden-import core.update --hidden-import services.autostart --hidden-import app --hidden-import app.countdown --hidden-import app.config_store --hidden-import app.window_chrome --hidden-import app.theme --hidden-import app.mode --hidden-import ui --hidden-import ui.widgets --hidden-import ui.mini_window --hidden-import ui.time_picker --hidden-import ui.full_window --hidden-import ui.context_menus --hidden-import ui.mini_text_picker --hidden-import ui.settings_window --hidden-import ui.update_dialog --hidden-import ui.design --hidden-import ui.design.tokens --hidden-import services --hidden-import services.tray --hidden-import services.updater --hidden-import services.sound --hidden-import services.ncm --hidden-import services.windows_native --hidden-import pystray --hidden-import pystray._win32 --hidden-import PIL --hidden-import PIL._tkinter_finder --distpath "%TOOL_DIR%\dist" --workpath "%TOOL_DIR%\build" --specpath "%TOOL_DIR%" "%TOOL_DIR%\count_down_tool.py"

echo.
echo ========================================
if exist "%TOOL_DIR%\dist\count_down_tool.exe" (
    if exist "%TOOL_DIR%\dist\%OUT_ZIP%" del /q "%TOOL_DIR%\dist\%OUT_ZIP%"
    rem PowerShell Compress-Archive: zip contains fixed name count_down_tool.exe
    powershell -NoProfile -Command "Compress-Archive -LiteralPath '%TOOL_DIR%\dist\count_down_tool.exe' -DestinationPath '%TOOL_DIR%\dist\%OUT_ZIP%' -Force"
    if not exist "%TOOL_DIR%\dist\%OUT_ZIP%" (
        echo   [ERROR] Failed to create zip
        echo ========================================
        pause
        exit /b 1
    )
    echo   Build successful!
    echo   Exe: %TOOL_DIR%\dist\count_down_tool.exe
    echo   Zip: %TOOL_DIR%\dist\%OUT_ZIP%
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

endlocal
pause
