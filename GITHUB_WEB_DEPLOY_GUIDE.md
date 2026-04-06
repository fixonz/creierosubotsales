# 🐙 How to Launch "Fucking Free" from GitHub (using WSL)

This is the fastest "One-Click" deployment method.

---

## 1. Push your code to GitHub (using WSL)
Open your **Ubuntu (WSL)** terminal and run these commands to make sure GitHub has your latest code:

```bash
# Navigate to the project
cd /mnt/c/Users/fixxZ/Downloads/creierosubotsales

# Update git with all your changes
git add .
git commit -m "Production ready deployment"

# Push to your GitHub repo
# (Note: If it asks for credentials, use your GitHub Token)
git push origin main
```

---

## 2. Connect to Koyeb (Free Tier)
We will use **Koyeb** because it supports GitHub deployment for free.

1.  **Go to:** [Koyeb.com](https://www.koyeb.com/) and Sign Up.
2.  **Select:** "Create Service" -> **GitHub**.
3.  **Authorize:** Link your GitHub account and select the `creierosubotsales` repository.
4.  **Build Settings:**
    *   Koyeb will automatically detect your `Dockerfile`. 
    *   Make sure **Deployment Method** is set to **Docker**.
5.  **Variables (CRITICAL):**
    Click **Add Environment Variables** and add everything from your `.env`:
    *   `BOT_TOKEN`
    *   `ADMIN_IDS`
    *   `TATUM_API_KEY`
    *   `LTC_ADDRESSES`
    *   `DB_PATH` = `/app/data/bot_database.sqlite` (Mandatory!)
6.  **Persistent Storage (Optional but recommended):**
    *   Koyeb's free tier resets the filesystem on restart. 
    *   If you want to keep data forever, you should use their **Volume** feature if available on your tier, or use a remote DB like MongoDB Atlas (Free).
7.  **Click Deploy.**

---

## 3. Why GitHub is better:
- **Auto-Update:** Every time you `git push` from your WSL terminal, the bot on the server will automatically update and restart!
- **Zero Config:** No more setting up Linux servers manually.

---
**Tip:** If you use the [Oracle Cloud Free Tier](file:///c:/Users/fixxZ/Downloads/creierosubotsales/FREE_HOSTING_GUIDE.md), you can also "launch from github" by simply doing a `git clone` on the server and using `docker-compose up`.
