@echo off
setlocal enabledelayedexpansion

echo ========================================
echo POKEMON YELLOW RL AGENT
echo ========================================

set PROJECT_DIR=C:\Users\gilli\OneDrive\Desktop\projects\pokemon_yellow_agent
set BIZHAWK_EXE=%PROJECT_DIR%\tools\bizhawk\EmuHawk.exe
set ROM_PATH=%PROJECT_DIR%\roms\Pokemon - Yellow Version (UE) [C][!].gbc
set LUA_SCRIPT=%PROJECT_DIR%\tools\bizhawk\pokemon_yellow_rl_bridge.lua

:: Get screen dimensions and calculate positions using PowerShell
echo Calculating window positions...
for /f %%i in ('powershell -command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea.Width"') do set SCREEN_WIDTH=%%i
for /f %%i in ('powershell -command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea.Height"') do set SCREEN_HEIGHT=%%i

:: Calculate positions
:: Console: left 1/3 of screen (0, 0, 1/3 width, full height)
set /a CONSOLE_WIDTH=SCREEN_WIDTH/3
set /a CONSOLE_HEIGHT=SCREEN_HEIGHT

:: BizHawk: right 2/3 of screen (1/3 width, 0, 2/3 width, full height)
set /a BIZHAWK_LEFT=SCREEN_WIDTH/3
set /a BIZHAWK_WIDTH=SCREEN_WIDTH*2/3
set /a BIZHAWK_HEIGHT=SCREEN_HEIGHT

echo Screen: %SCREEN_WIDTH% x %SCREEN_HEIGHT%
echo Console: 0, 0, %CONSOLE_WIDTH% x %CONSOLE_HEIGHT%
echo BizHawk: %BIZHAWK_LEFT%, 0, %BIZHAWK_WIDTH% x %BIZHAWK_HEIGHT%

:: Start BizHawk with ROM and Lua script
echo.
echo Starting BizHawk with Pokemon Yellow...
start "" "%BIZHAWK_EXE%" "%ROM_PATH%" --lua="%LUA_SCRIPT%"

:: Wait for BizHawk to start
echo Waiting for BizHawk to load...
timeout /t 5 /nobreak >nul

:: Position BizHawk window (right 2/3)
echo Positioning BizHawk window...
powershell -command "$null = Add-Type -MemberDefinition '[DllImport(\"user32.dll\")] public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);' -Name 'Win32' -Namespace 'User32'; $hwnd = (Get-Process EmuHawk -ErrorAction SilentlyContinue | Select-Object -First 1).MainWindowHandle; if ($hwnd -ne 0) { [User32.Win32]::SetWindowPos($hwnd, 0, %BIZHAWK_LEFT%, 0, %BIZHAWK_WIDTH%, %BIZHAWK_HEIGHT%, 0x0040) }"

:: Position console window (left 1/3)
echo Positioning console window...
powershell -command "$null = Add-Type -MemberDefinition '[DllImport(\"user32.dll\")] public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);' -Name 'Win32Console' -Namespace 'User32Console'; $hwnd = (Get-Process -Id $PID).MainWindowHandle; [User32Console.Win32Console]::SetWindowPos($hwnd, 0, 0, 0, %CONSOLE_WIDTH%, %CONSOLE_HEIGHT%, 0x0040)"

echo.
echo ========================================
echo STARTING RL AGENT
echo ========================================
echo.

:: Activate virtual environment and run RL agent
cd /d %PROJECT_DIR%\pokemon_yellow_rl
call C:\Users\gilli\.venv\Scripts\activate.bat
python -u train_rl.py

pause
