# 🚀 Alibaba Cloud (ECS) Deployment Guide - Creierosu Bot

Deploying on Alibaba Cloud Elastic Compute Service (ECS) is a cost-effective way to host your bot.

---

## 1. Create an Alibaba ECS Instance
1.  Log into the [Alibaba Cloud Console](https://ecs.console.aliyun.com/).
2.  Click **Create Instance**.
3.  **Billing Method:** `Pay-As-You-Go` (Best for testing) or `Subscription` (Cheaper for long-term).
4.  **Region:** Choose `Central Europe (Frankfurt)` for low latency in Romania/Europe.
5.  **Instance Type:** Search for `ecs.t5` or `ecs.n4` (Burstable instances are perfect for low-load bots).
6.  **Image:** Search for `Ubuntu 22.04 64bit`.
7.  **System Disk:** `ESSD` or `Standard SSD` (20GB is plenty).
8.  **Public IP Address:** Ensure **Assign Public IPv4 Address** is checked. Select a bandwidth limit (e.g., 5 Mbps).
9.  **Password/Key Pair:** Set a `Root Password` for easy SSH access.
10. Click **Create Instance**.

---

## 2. Open Security Group Port 8888
Alibaba uses **Security Groups** to control traffic.
1.  Go to the **Security Group** tab in your ECS instance details.
2.  Click **Add Rule**.
3.  **Protocol:** `TCP`
4.  **Port Range:** `8888/8888`
5.  **Authorization Object:** `0.0.0.0/0` (Allow all)
6.  Click **Save**.

---

## 3. Server Setup (SSH)
Connect to your instance using an SSH client (like PuTTY or the built-in Terminal).
```bash
ssh root@[YOUR_ALIBABA_IP]
```

### A. Update & Install Docker
```bash
apt-get update
apt-get install -y docker.io docker-compose
systemctl start docker
systemctl enable docker

# Check if Ubuntu firewall is blocking (optional)
ufw allow 8888/tcp
ufw reload
```

---

## 4. Deploy the Bot
1.  **Clone your repository:**
    ```bash
    git clone https://github.com/YOUR_USERNAME/creierosubotsales.git
    cd creierosubotsales
    ```

2.  **Setup Environment:**
    ```bash
    nano .env
    ```
    *Paste your `.env` content. (Use `Ctrl+O` to Save and `Ctrl+X` to Exit)*
    **CRITICAL:** Ensure `DB_PATH=/app/data/bot_database.sqlite` is correctly set.

3.  **Prepare Directories:**
    ```bash
    mkdir -p data assets
    # Move database if it came with the git clone
    if [ -f bot_database.sqlite ]; then mv bot_database.sqlite data/; fi
    ```

4.  **Launch:**
    ```bash
    docker-compose up -d --build
    ```

---

## 5. Maintenance
- **View Bot Logs:** `docker logs -f creierosu-bot`
- **Check Status:** `docker ps`
- **Access Dashboard:** `http://[YOUR_ALIBABA_IP]:8888`

---
**Tip:** On Alibaba Cloud, you can also use their **Global Accelerator** if you have customers worldwide!
