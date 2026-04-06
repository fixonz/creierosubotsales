# 🚀 Google VPS (Compute Engine) Deployment Guide - Creierosu Bot

Deploying on Google Cloud Platform (GCP) provides a more stable environment for your bot.

---

## 1. Create a Google Cloud Instance
1.  Go to the [Google Cloud Console](https://console.cloud.google.com/).
2.  Search for **Compute Engine** -> **VM instances**.
3.  Click **CREATE INSTANCE**.
4.  **Name:** `creierosu-bot-service`
5.  **Region:** Choose `europe-west3` (Frankfurt) or any location close to your user base.
6.  **Machine configuration:**
    *   **Machine type:** `e2-micro` (2 vCPUs, 1 GB RAM) or `e2-small` for better performance.
7.  **Boot disk:**
    *   **Operating System:** `Ubuntu`
    *   **Version:** `Ubuntu 22.04 LTS`
8.  **Firewall:**
    *   Check `Allow HTTP traffic`
    *   Check `Allow HTTPS traffic`
9.  Click **CREATE**.

---

## 2. Open Firewall Port 8888
By default, Google blocks most ports. We need to open port **8888** for your dashboard.
1.  Search for **VPC network** -> **Firewall**.
2.  Click **CREATE FIREWALL RULE**.
3.  **Name:** `allow-dashboard-8888`
4.  **Targets:** `All instances in the network`
5.  **Source IPv4 ranges:** `0.0.0.0/0`
6.  **Protocols and ports:** Check `TCP` and type `8888`.
7.  Click **CREATE**.

---

## 3. Server Setup (SSH)
Connect to your instance via the **SSH** button in the Google Cloud Console. Run these commands:

### A. Update & Install Docker
```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose
sudo systemctl start docker
sudo systemctl enable docker
# Allow running docker without sudo (re-login required, or just use sudo later)
sudo usermod -aG docker $USER
```
*(Logout and back in for the group change to take effect, or just prefix docker commands with `sudo`)*

---

## 4. Deploy the Bot
1.  **Clone your repository:** (Replace with your actual GitHub repo URL)
    ```bash
    git clone https://github.com/YOUR_USERNAME/creierosubotsales.git
    cd creierosubotsales
    ```

2.  **Create your Environment File:**
    ```bash
    nano .env
    ```
    *Paste your `.env` content into the file. Use `Ctrl+O` to Save and `Ctrl+X` to Exit.*
    **CRITICAL:** Make sure `DB_PATH=/app/data/bot_database.sqlite` is in your .env or handled by Docker.

4.  **Copy existing data (Optional):**
    If you already have a `bot_database.sqlite` on your machine, you can upload it to the server. If not, the bot will start fresh.
    ```bash
    mkdir -p data assets
    # If the database is already in the root after git clone:
    mv bot_database.sqlite data/
    ```

5.  **Launch with Docker Compose:**
    ```bash
    sudo docker-compose up -d --build
    ```

---

## 5. Maintenance & Logs
- **Check if bot is running:** `sudo docker ps`
- **View logs (for debugging):** `sudo docker logs -f creierosu-bot`
- **Restart the bot:** `sudo docker-compose restart`
- **Stop the bot:** `sudo docker-compose down`

## 6. Accessing your Dashboard
Your dashboard will be available at:
`http://[YOUR_INSTANCE_EXTERNAL_IP]:8888`

You can find the "External IP" in the VM instances table in Google Cloud Console.

---
**Tip:** If you want a clean domain (like `bot.yourdomain.com`) with SSL (HTTPS), I recommend setting up **Nginx** and **Certbot** as a reverse proxy!
