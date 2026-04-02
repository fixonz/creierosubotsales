# 🤖 Sub-Bot Sales System (a1_z1_c1_2c2)

Welcome to the advanced, multi-language Telegram Sales Bot. This bot is designed for secure, automated transactions using Litecoin (LTC) with instant delivery and advanced branding features.

## 🚀 Key Features

-   **Dual Language Support**: Seamlessly switch between **Romanian 🇷🇴** and **English 🇺🇸**.
-   **Automated LTC Payouts**: Real-time blockchain verification with automated delivery.
-   **Transaction Fees**: Built-in fee calculation (`TRANSACTION_FEE_PERCENT`) to allow platform monetization.
-   **Advanced Branding**: Images are automatically branded with GTA-style fonts and location names.
-   **Admin Control**: Exclusive access to pending orders, inventory management, and live feed.
-   **Subscription Alerts**: Users can subscribe to "Out of Stock" items and get notified instantly when re-stocked.
-   **Review System**: Star ratings and comments for every successful purchase.

## 🛠 Commands

### User Commands
-   `/start` - Initialize the bot and setup language.
-   `/profile` - View your stats, order history, and change language.
-   `/pending` - (Admin only) View and manage latest pending orders.

### Admin Commands (Restricted)
-   `/items` - List and manage inventory.
-   `/stats` - View global sales statistics.
-   `/pending` - View latest 3 pending orders for quick approval/rejection.
-   `/feed` - Toggle the live admin notification feed.

## ⚙️ Configuration (.env)

| Variable | Description |
| :--- | :--- |
| `BOT_TOKEN` | Your Telegram Bot Token. |
| `ADMIN_IDS` | Comma-separated list of Telegram IDs allowed to use admin commands. |
| `TATUM_API_KEY` | Your Tatum.io API key for blockchain monitoring. |
| `LTC_ADDRESSES` | Comma-separated list of LTC addresses to receive payments. |
| `TRANSACTION_FEE_PERCENT` | Percentage added to the RON-to-LTC conversion (e.g., `5` for 5%). |

## 📁 Monitoring and Maintenance

-   **Database**: `bot_database.sqlite` stores all users, sales, and reviews.
-   **Logs**: Terminal output shows real-time verification status and errors.
-   **Assets**: Put your images in the `assets/` folder. Ensure `gta.ttf` is present for branding.

## ⚠️ Important Note
This version (`a1_z1_c1_2c2`) has been nulled for sensitive info. Remember to set your own `ADMIN_IDS` and `BOT_TOKEN` in the `.env` file before running.

---
*Created by Antigravity - Your Super Bot Inventor Adventurer.*
