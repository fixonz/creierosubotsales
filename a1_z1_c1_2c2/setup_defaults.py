import sqlite3
import os
import aiosqlite
import asyncio
from database import init_db

DB_PATH = "bot_database.sqlite"

async def setup():
    # 0. Initialize the DB structure first
    await init_db()
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Clear existing to start fresh
    print("🧹 Clearing old data...")
    c.execute("DELETE FROM locations")
    c.execute("DELETE FROM categories")
    c.execute("DELETE FROM items")
    c.execute("DELETE FROM item_images") 
    c.execute("DELETE FROM preorders")

    # Mapping emojis to images (adjusting to what's likely in assets)
    IMG_MAP = {
        "❄️": ("assets/cat_snow.jpg", "assets/SECRET_SNOW.jpg"),
        "🐎": ("assets/cat_horse.jpg", "assets/SECRET_HORSE.jpg"),
        "☘️": ("assets/cat_weed.jpg", "assets/SECRET_WEED.jpg"),
        "🍾": ("assets/cat_champagne.jpg", "assets/SECRET_CHAMPAGNE.jpg"),
        "🍬": ("assets/cat_candy.jpg", "assets/secret_candy.jpg"),
        "🏃": ("assets/cat_runner.jpg", "assets/SECRET_RUNNER.jpg"),
        "🍫": ("assets/cat_chocolate.jpg", "assets/SECRET_CHOCOLATE.jpg"),
        "🔮": ("assets/cat_crystal.jpg", "assets/SECRET_CRYSTAL.jpg"),
        "💎": ("assets/cat_diamond.jpg", "assets/SECRET_DIAMOND.jpg")
    }

    # 1. Add Cities
    print("📍 Adding locations...")
    c.execute("INSERT INTO locations (name, display_image) VALUES (?, ?)", ("Bucuresti", "assets/bucuresti.jpg"))
    buc_id = c.lastrowid

    # 2. Add Standard Categories for Bucuresti (All Sectors)
    buc_categories = [
        "❄️ 100", "🐎 200", "☘️ 300", 
        "🍾 400", "🍬 500", "🏃 600", 
        "🍫 700", "🔮 800", "💎 900"
    ]
    
    print("🏗️ Creating sectors, categories and products...")
    for sector_num in range(1, 7):
        for cat_name in buc_categories:
            emoji = cat_name.split()[0]
            cat_img, sec_img = IMG_MAP.get(emoji, (None, None))
            
            c.execute("INSERT INTO categories (location_id, name, description, sector, display_image) VALUES (?, ?, ?, ?, ?)", 
                      (buc_id, cat_name, f"Calitate premium {cat_name} în Sector {sector_num}", sector_num, cat_img))
            cat_id = c.lastrowid
            
            # Add 2 items per category
            for i_name, p_ron in [("Calitate 1", 500), ("Calitate 2", 900)]:
                c.execute("INSERT INTO items (category_id, name, price_ron, product_image) VALUES (?, ?, ?, ?)", 
                          (cat_id, i_name, p_ron, sec_img))
                it_id = c.lastrowid
                
                # Add 1 piece of dummy stock per item so it's ready to buy
                c.execute("INSERT INTO item_images (item_id, image_url, media_type, caption, is_sold) VALUES (?, ?, ?, ?, 0)", 
                          (it_id, "SECRET_CONTENT_1", "text", f"Iată secretul tău pentru {cat_name}!",))

    conn.commit()
    conn.close()
    print("✅ Database prepared with Bucuresti (S1-S6) and stock added!")

if __name__ == "__main__":
    asyncio.run(setup())
