@echo off
title Bot Setup Wizard — Build EXE
color 0D
echo.
echo  ============================================
echo   BOT SETUP WIZARD  ^|  Building .exe
echo  ============================================
echo.

:: 1. Ensure tools are present
echo [1/4] Installing dependencies...
py -m pip install pyinstaller pillow python-dotenv aiosqlite aiogram --quiet
if errorlevel 1 ( echo  ERROR: pip install failed. & pause & exit /b 1 )
echo  Done.
echo.

:: 2. Clean previous build
echo [2/4] Cleaning previous build...
if exist build   rmdir /s /q build
if exist dist    rmdir /s /q dist
if exist BotSetup.spec del /q BotSetup.spec
echo  Done.
echo.

:: 3. Build the wizard exe
echo [3/4] Compiling setup_wizard.py ...
echo      Wait for completion (this may take 1-2 minutes)
py -m PyInstaller ^
  --noconfirm ^
  --onefile ^
  --windowed ^
  --name "BotSetup" ^
  --icon "assets\icon.ico" ^
  --add-data "assets;assets" ^
  --add-data "handlers;handlers" ^
  --add-data "utils;utils" ^
  --add-data "config;config" ^
  --add-data "config.py;." ^
  --add-data "database.py;." ^
  --add-data "bot.py;." ^
  --add-data "requirements.txt;." ^
  --hidden-import "PIL._tkinter_finder" ^
  --hidden-import "aiogram" ^
  --hidden-import "aiosqlite" ^
  --hidden-import "dotenv" ^
  setup_wizard.py

if errorlevel 1 (
  echo.
  echo  *** Build FAILED. See errors above. ***
  pause
  exit /b 1
)

echo.
echo [4/4] Done! 
echo.
echo  ==============================================
echo   Your .exe is at:  dist\BotSetup.exe
echo   Distribute the dist\ folder to buyers.
echo   They only need BotSetup.exe — no Python.
echo  ==============================================
echo.
pause
