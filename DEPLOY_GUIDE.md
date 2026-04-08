# ⚡ Creierosu Deployment Guide (WSL + Railway)

This guide will help you get your bot online 24/7 using **WSL (Windows Subsystem for Linux)** and **Railway.app**.

## 1. Prepare your Repository using WSL
Open your WSL terminal (e.g., Ubuntu) and follow these steps:

1. **Navigate to your project folder:**
   ```bash
   cd /mnt/c/Users/fixxZ/Downloads/creierosubotsales
   ```

2. **Initialize Git & Push to GitHub:**
   ```bash
   git init
   git add .
   git commit -m "Production ready deployment"
   # Create a new private repo on GitHub, then:
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
   git branch -M main
   git push -u origin main
   ```

## 2. Deploy to Railway
1. Go to [Railway.app](https://railway.app/) and log in.
2. Click **+ New Project** -> **Deploy from GitHub repo**.
3. Select your repository.
4. **Variables (CRITICAL):**
   Go to the **Variables** tab and add everything from your `.env`:
   - `BOT_TOKEN` (Your Telegram Bot Token)
   - `ADMIN_IDS` (Comma separated IDs)
   - `TATUM_API_KEY`
   - `LTC_ADDRESSES` (5 comma separated addresses)
   - `DB_PATH` = `/app/data/bot_database.sqlite` (This is mandatory!)

## 3. Persistent Database (Don't skip this!)
Railway resets the file system on every restart unless you add a Volume.
1. In your Railway service, go to **Settings**.
2. Scroll to **Volumes** -> **+ Add Volume**.
3. Set the **Mount Path** to `/app/data`.
4. Click **Add Volume**.
5. Your bot will now remember items, categories, and sales even after a restart!

## 4. Dashboard Access
- Railway will provide a public URL (e.g., `https://bot-production-xxx.railway.app`).
- You can access your admin dashboard there.
- **Tip:** You no longer need the `/link` command or Serveo. Your URL is now permanent!

## 5. Why it won't "fall" again:
- **Auto-Restart:** If the bot crashes, Railway automatically restarts it.
- **Dockerized:** The `Dockerfile` ensures it runs in a perfect environment.
- **Persistent Storage:** Your SQLite database is safe on the Railway Volume.
- **No Serveo:** We use Railway's built-in networking which is much more stable than SSH tunnels.
