# ⚡ CryptoSales Bot v2.0 (a1_z1_c1_2c2)

A premium, high-performance Telegram Sales Bot supporting automated **LTC (Litecoin)** transactions, instant digital delivery, and professional branding. Fully localized in English and Romanian.

---

## 🌟 Exclusive Features

### 🌍 Global Reach
- **Native Dual Language**: Switch instantly between **English 🇺🇸** and **Romanian 🇷🇴**.
- **User Preference Memory**: Remembers user language across sessions.
- **Localized UI**: Everything from buttons to prompts adapts to the chosen language.

### 💰 Monetization & Payments
- **Adjustable Fee Engine**: Configure `TRANSACTION_FEE_PERCENT` in `.env`.
- **Automatic Conversion**: Real-time RON to LTC price fetching via CoinGecko.
- **Direct Wallet Transfers**: Payments go directly to your addresses—no middleman.
- **QR Code Generation**: Integrated QR codes for easier mobile payments.

### 📦 Delivery & Inventory
- **Instant Fulfillment**: Sends product data (photos, videos, text) immediately after 1 blockchain confirmation.
- **Bundle Support**: Supports sending multiple files/media as a single "secret packet".
- **Stock Tracking**: Real-time inventory monitoring with re-stock notification alerts for users.

### 🎨 Premium Branding
- **GTA-Style Overlays**: Automatically brands location/category images with custom fonts and transparency for a "High-End" look.
- **Spoiler Support**: Delivers real product photos under a spoiler (`has_spoiler=True`) to maintain maximum discretion for buyers.

### 🛠 Administrative Power
- **Admin Command Feed**: A live feed of user activity and pending orders.
- **Pending Order Management**: Quick `Approve` / `Reject` buttons for manual overrides.
- **Inventory Control**: Easy-to-use commands (`/items`, `/stats`) to manage sectors, categories, and stock.

---

## 📋 Command List

### 👤 User Commands
| Command | Description |
| :--- | :--- |
| `/start` | Launches the bot and language selector. |
| `/profile` | View purchase history, total spent, and change language. |
| `🏘️ Cities` | Browse locations and available sectors. |
| `💬 Support` | Direct link to the admin support center. |
| `⭐ Reviews` | View ratings and feedback from other buyers. |

### 🛠 Admin Commands
| Command | Description |
| :--- | :--- |
| `/pending` | Quick access to the last 3 pending orders for verification. |
| `/feed` | Toggle the live activity feed for all admins. |
| `/stats` | Global analytics (Total users, Completed sales, Active stock). |
| `/restart` | Safely clear temporary processes (requires admin privileges). |
| `/unfreeze` | Unlock LTC addresses that might be stuck in a "locked" state. |

---

## 🚀 Quick Setup Guide

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environments**:
   Edit the `.env` file with your credentials:
   - `BOT_TOKEN`: Get it from @BotFather.
   - `ADMIN_IDS`: Your Telegram ID (and others).
   - `LTC_ADDRESSES`: Your payment destination address(es).
   - `TATUM_API_KEY`: For LTC blockchain tracking.
   - `TRANSACTION_FEE_PERCENT`: Your profit margin (e.g., `10` for 10%).

3. **Initialize Database**:
   Run the setup script to create default values:
   ```bash
   python setup_defaults.py
   ```

4. **Launch the Bot**:
   ```bash
   python bot.py
   ```

---

## 📁 System Requirements
- **Python 3.12+**
- **Assets**: Ensure `assets/gta.ttf` and `assets/welcome.jpg` are present.
- **Database**: Uses SQLite for fast, portable data management (`bot_database.sqlite`).

---
*Developed for the Crypto Community.*  
**Join the Telegram Updates Channel for news!**
