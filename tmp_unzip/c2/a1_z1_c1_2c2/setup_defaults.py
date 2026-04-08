import sqlite3
import os

DB_PATH = "bot_database.sqlite"

def setup():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Clear existing to start fresh
    c.execute("DELETE FROM locations")
    c.execute("DELETE FROM categories")
    c.execute("DELETE FROM items")
    c.execute("DELETE FROM item_images") 
    c.execute("DELETE FROM preorders")

    # Mapping emojis to images
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
    c.execute("INSERT INTO locations (name, display_image) VALUES (?, ?)", ("Bucuresti", "assets/bucuresti.jpg"))
    buc_id = c.lastrowid
    c.execute("INSERT INTO locations (name, display_image) VALUES (?, ?)", ("Craiova", "assets/craiova.jpg"))
    craiova_id = c.lastrowid

    # 2. Add Standard Categories for Bucuresti (All Sectors)
    buc_categories = [
        "❄️", "🐎", "☘️", 
        "🍾", "🍬", "🏃", 
        "🍫", "🔮", "💎"
    ]
    
    for sector_num in range(1, 7):
        for cat_name in buc_categories:
            emoji = cat_name.split()[0]
            cat_img, sec_img = IMG_MAP.get(emoji, (None, None))
            
            c.execute("INSERT INTO categories (location_id, name, description, sector, display_image) VALUES (?, ?, ?, ?, ?)", 
                      (buc_id, cat_name, f"Calitate premium {cat_name}", sector_num, cat_img))
            cat_id = c.lastrowid
            
            c.execute("INSERT INTO items (category_id, name, price_ron, product_image) VALUES (?, ?, ?, ?)", (cat_id, "1x", 500, sec_img))
            c.execute("INSERT INTO items (category_id, name, price_ron, product_image) VALUES (?, ?, ?, ?)", (cat_id, "2x", 900, sec_img))

    # 3. Add Categories for Craiova
    cra_categories = ["❄️", "☘️", "🍬"]
    for cat_name in cra_categories:
        emoji = cat_name.split()[0]
        cat_img, sec_img = IMG_MAP.get(emoji, (None, None))
        
        c.execute("INSERT INTO categories (location_id, name, description, sector, display_image) VALUES (?, ?, ?, ?, ?)", 
                  (craiova_id, cat_name, f"Calitate premium {cat_name}", None, cat_img))
        cat_id = c.lastrowid
        
        c.execute("INSERT INTO items (category_id, name, price_ron, product_image) VALUES (?, ?, ?, ?)", (cat_id, "1x", 500, sec_img))
        c.execute("INSERT INTO items (category_id, name, price_ron, product_image) VALUES (?, ?, ?, ?)", (cat_id, "2x", 900, sec_img))

    conn.commit()
    conn.close()
    print("✅ Database prepared with Bucuresti (9 cats) and Craiova (3 cats) with proper images.")

if __name__ == "__main__":
    setup()
