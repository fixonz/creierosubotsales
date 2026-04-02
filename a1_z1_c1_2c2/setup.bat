@echo off
echo 🚀 STARTING FULL SETUP FOR SUB-BOT (a1_z1_c1_2c2)...

:: 1. Install requirements
echo 📦 Installing dependencies...
pip install -r requirements.txt

:: 2. Setup database defaults
echo 🗄️ Initializing database with sectors, categories and items...
py -3.12 setup_defaults.py

:: 3. Kill existing bot processes to avoid conflicts
echo 🛑 Cleaning up old bot instances...
taskkill /F /IM python.exe /T 2>nul

:: 4. Start the bot
echo ✨ Everything is ready! Starting the bot...
start py -3.12 bot.py

echo ✅ Setup finished. The bot is now running in a new window.
pause
