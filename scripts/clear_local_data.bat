@echo off
setlocal EnableExtensions
title Count Down Tool - Clear Local Data

rem Clear user data / cache / autostart for count_down_tool
rem Does NOT delete the program install folder (where you extracted the zip).
rem Usage: clear_local_data.bat [/y]   /y = no confirm

set "AUTO_YES=0"
if /I "%~1"=="/y" set "AUTO_YES=1"
if /I "%~1"=="-y" set "AUTO_YES=1"
if /I "%~1"=="/yes" set "AUTO_YES=1"

set "CFG_DIR=%APPDATA%\count_down_tool"
set "STARTUP_LNK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\count_down_tool.lnk"
set "TEMP_ROOT=%TEMP%"
if not defined TEMP_ROOT set "TEMP_ROOT=%TMP%"

echo.
echo ========================================
echo   Count Down Tool - Clear Local Data
echo ========================================
echo.
echo Will remove (if present):
echo   1) User config:  %CFG_DIR%
echo      (config.json, sounds, app.log, locks, ...)
echo   2) Startup link: %STARTUP_LNK%
echo   3) Temp caches under %%TEMP%%:
echo      - count_down_tool*
echo      - count_down_tool_ncm_cache
echo      - count_down_tool_update*
echo      - _MEI*  (old onefile extract folders; best-effort)
echo.
echo Will NOT remove:
echo   - Your install folder (exe / _internal)
echo   - This script / git repo
echo.

if "%AUTO_YES%"=="0" (
    set /p "ANS=Type YES to continue: "
    if /I not "%ANS%"=="YES" (
        echo Cancelled.
        pause
        exit /b 1
    )
)

echo.
echo [1/4] Stopping running processes...
taskkill /F /IM count_down_tool.exe >nul 2>&1
rem Give handles a moment to release
timeout /t 1 /nobreak >nul 2>&1

echo [2/4] Removing config dir...
if exist "%CFG_DIR%" (
    rd /s /q "%CFG_DIR%" 2>nul
    if exist "%CFG_DIR%" (
        echo   [WARN] Could not fully delete: %CFG_DIR%
        echo          Close the app and retry, or delete manually.
    ) else (
        echo   OK: %CFG_DIR%
    )
) else (
    echo   Skip: not found
)

echo [3/4] Removing startup shortcut...
if exist "%STARTUP_LNK%" (
    del /f /q "%STARTUP_LNK%" 2>nul
    if exist "%STARTUP_LNK%" (
        echo   [WARN] Could not delete: %STARTUP_LNK%
    ) else (
        echo   OK: startup link removed
    )
) else (
    echo   Skip: no startup link
)

echo [4/4] Cleaning temp caches...
set "CLEANED=0"
if defined TEMP_ROOT (
    if exist "%TEMP_ROOT%\count_down_tool_ncm_cache" (
        rd /s /q "%TEMP_ROOT%\count_down_tool_ncm_cache" 2>nul
        set "CLEANED=1"
    )
    if exist "%TEMP_ROOT%\count_down_tool_update" (
        rd /s /q "%TEMP_ROOT%\count_down_tool_update" 2>nul
        set "CLEANED=1"
    )
    if exist "%TEMP_ROOT%\count_down_tool_update.log" (
        del /f /q "%TEMP_ROOT%\count_down_tool_update.log" 2>nul
        set "CLEANED=1"
    )
    rem Prefix folders: count_down_tool*
    for /d %%D in ("%TEMP_ROOT%\count_down_tool*") do (
        if exist "%%~fD" (
            rd /s /q "%%~fD" 2>nul
            set "CLEANED=1"
        )
    )
    rem Stale onefile extract dirs (may fail if locked by other apps)
    for /d %%D in ("%TEMP_ROOT%\_MEI*") do (
        rd /s /q "%%~fD" 2>nul
        set "CLEANED=1"
    )
)
if "%CLEANED%"=="1" (
    echo   OK: temp cleanup attempted
) else (
    echo   Skip: no matching temp items
)

echo.
echo ========================================
echo   Done.
echo   Re-run the app for a fresh config.
echo ========================================
echo.
if "%AUTO_YES%"=="0" pause
endlocal
exit /b 0
