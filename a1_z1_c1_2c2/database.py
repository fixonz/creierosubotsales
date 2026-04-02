import aiosqlite
import logging

DB_PATH = "bot_database.sqlite"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=NORMAL")
        
        # User Interaction Layer (C1)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                username TEXT,
                language TEXT DEFAULT 'ro',
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        
        # Zone Management (Z1)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                display_image TEXT DEFAULT NULL
            )
        ''')
        
        try:
            await db.execute("ALTER TABLE locations ADD COLUMN display_image TEXT DEFAULT NULL")
        except Exception:
            pass

        await db.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_id INTEGER,
                name TEXT,
                description TEXT,
                display_image TEXT DEFAULT NULL,
                FOREIGN KEY (location_id) REFERENCES locations (id)
            )
        ''')
        
        try:
            await db.execute("ALTER TABLE categories ADD COLUMN description TEXT")
        except Exception:
            pass
            
        try:
            await db.execute("ALTER TABLE categories ADD COLUMN display_image TEXT DEFAULT NULL")
        except Exception:
            pass

        try:
            await db.execute("ALTER TABLE categories ADD COLUMN sector INTEGER DEFAULT NULL")
        except Exception:
            pass

        await db.execute('''
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER,
                name TEXT,
                price_ron REAL,
                product_image TEXT DEFAULT NULL,
                FOREIGN KEY (category_id) REFERENCES categories (id)
            )
        ''')
        try:
            await db.execute("ALTER TABLE items ADD COLUMN product_image TEXT DEFAULT NULL")
        except Exception:
            pass

        # Communication & Confirmation Layer (2C2)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS item_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER,
                image_url TEXT,
                media_type TEXT DEFAULT 'photo',
                caption TEXT DEFAULT NULL,
                secret_group TEXT DEFAULT NULL,
                is_sold BOOLEAN DEFAULT 0,
                FOREIGN KEY (item_id) REFERENCES items (id)
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                item_id INTEGER,
                image_id INTEGER DEFAULT NULL,
                amount_expected REAL,
                amount_paid REAL DEFAULT 0,
                address_used TEXT,
                tx_hash TEXT UNIQUE DEFAULT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (item_id) REFERENCES items (id),
                FOREIGN KEY (image_id) REFERENCES item_images (id)
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS preorders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                item_id INTEGER,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (item_id) REFERENCES items (id)
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS addresses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                crypto_address TEXT UNIQUE,
                in_use_by_sale_id INTEGER DEFAULT NULL,
                locked_until TIMESTAMP DEFAULT NULL,
                last_tx_hash TEXT DEFAULT NULL,
                last_amount REAL DEFAULT NULL
            )
        ''')
        
        # Migrations for existing DB
        try:
            await db.execute("ALTER TABLE addresses ADD COLUMN last_tx_hash TEXT DEFAULT NULL")
        except: pass
        try:
            await db.execute("ALTER TABLE addresses ADD COLUMN last_amount REAL DEFAULT NULL")
        except: pass
        
        try:
            await db.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'ro'")
        except: pass

        await db.execute('''
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                sale_id INTEGER UNIQUE,
                rating INTEGER,
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (sale_id) REFERENCES sales (id)
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS stock_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                item_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, item_id),
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (item_id) REFERENCES items (id)
            )
        ''')
        # Performance Indexes
        await db.execute("CREATE INDEX IF NOT EXISTS idx_sales_user_status ON sales(user_id, status)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_sales_item ON sales(item_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_item_images_item_sold ON item_images(item_id, is_sold)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_items_cat ON items(category_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_cats_loc ON categories(location_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_preorders_status ON preorders(status)")
        
        await db.commit()
        await ensure_5_slots()
        logging.info("A1 Z1 C1 2C2 Database initialized with reviews and settings support.")

async def ensure_5_slots():
    """Maintain exactly 5 rows in the addresses table."""
    async with aiosqlite.connect(DB_PATH) as db:
        # 1. Get current rows
        async with db.execute("SELECT id FROM addresses ORDER BY id ASC") as cursor:
            rows = await cursor.fetchall()
        
        count = len(rows)
        # 2. Handle excess slots
        if count > 5:
            for i in range(5, count):
                await db.execute("DELETE FROM addresses WHERE id = ?", (rows[i][0],))
            await db.commit()
        # 3. Handle missing slots
        elif count < 5:
            for i in range(5 - count):
                await db.execute("INSERT INTO addresses (crypto_address) VALUES (?)", (f"UNSET_SLOT_NEW_{i+1}",))
            await db.commit()
        
        logging.info(f"Sub-Bot: Initialized with exactly 5 LTC slots (Current count: {count if count <= 5 else 5}).")

# --- Repository functions ---

async def get_and_create_sale(user_tg_id: int, item_id: int, base_amount: float, timeout_minutes: int):
    """
    Finds an address and creates a pending sale. 
    Returns (address, final_amount, sale_id).
    """
    from datetime import datetime, timedelta
    now = datetime.now()
    now_str = now.strftime('%Y-%m-%d %H:%M:%S')
    expires_at = now + timedelta(minutes=timeout_minutes)
    expires_str = expires_at.strftime('%Y-%m-%d %H:%M:%S')

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        try:
            # 1. Get a truly FREE address
            async with db.execute("""
                SELECT crypto_address FROM addresses 
                WHERE crypto_address NOT LIKE 'UNSET_SLOT_%'
                  AND in_use_by_sale_id IS NULL
                  AND (locked_until IS NULL OR locked_until < ?)
                ORDER BY locked_until ASC
            """, (now_str,)) as cursor:
                row = await cursor.fetchone()
                
            if not row:
                logging.warning("No free LTC addresses available (all in use or cooldown)")
                await db.execute("ROLLBACK")
                return None, None, None

            address = row['crypto_address']
            final_amount = round(base_amount, 5)

            # 2. Create Sale
            cursor = await db.execute("""
                INSERT INTO sales (user_id, item_id, amount_expected, address_used, created_at, status) 
                VALUES ((SELECT id FROM users WHERE telegram_id=?), ?, ?, ?, ?, 'pending')
            """, (user_tg_id, item_id, final_amount, address, now_str))
            sale_id = cursor.lastrowid

            # 3. Mark Address as in use and set timeout lock
            await db.execute("""
                UPDATE addresses SET in_use_by_sale_id = ?, locked_until = ? 
                WHERE crypto_address = ?
            """, (sale_id, expires_str, address))
            
            await db.commit()
            return address, final_amount, sale_id
        except Exception as e:
            await db.execute("ROLLBACK")
            logging.error(f"Error in get_and_create_sale: {e}")
            return None, None, None

async def seed_addresses(addresses_list: list):
    async with aiosqlite.connect(DB_PATH) as db:
        for addr in addresses_list:
            await db.execute("INSERT OR IGNORE INTO addresses (crypto_address) VALUES (?)", (addr,))
        await db.commit()

async def add_user(telegram_id: int, username: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (telegram_id, username) VALUES (?, ?)",
            (telegram_id, username)
        )
        await db.commit()

async def is_silent_mode():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM bot_settings WHERE key = 'silent_mode'") as cursor:
            row = await cursor.fetchone()
            return row and row[0] == 'on'

async def set_silent_mode(enabled: bool):
    val = 'on' if enabled else 'off'
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES ('silent_mode', ?)", (val,))
        await db.commit()

async def cleanup_completed_orders():
    """
    Deletes all successful sales and marks their associated images as unsold (put the secret back up).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        # Mark all images belonging to the same secrets as unsold
        await db.execute("""
            UPDATE item_images 
            SET is_sold = 0 
            WHERE id IN (
                SELECT img.id 
                FROM item_images img
                JOIN item_images img_ref ON (img.secret_group = img_ref.secret_group OR img.id = img_ref.id)
                WHERE img_ref.id IN (SELECT image_id FROM sales WHERE status IN ('completed', 'paid', 'delivered'))
            )
        """)
        # 2. Delete the sales
        await db.execute("DELETE FROM sales WHERE status IN ('completed', 'paid', 'delivered')")
        await db.commit()

async def restore_secret_and_delete_sale(sale_id: int):
    """
    Deletes a specific sale and marks its associated image (and its group) as unsold.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT image_id FROM sales WHERE id = ?", (sale_id,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                image_id = row[0]
                # Restore the whole group if it was part of one
                await db.execute("""
                    UPDATE item_images 
                    SET is_sold = 0 
                    WHERE secret_group = (SELECT secret_group FROM item_images WHERE id = ?)
                       OR id = ?
                """, (image_id, image_id))
        # 2. Delete the sale
        await db.execute("DELETE FROM sales WHERE id = ?", (sale_id,))
        await db.commit()

async def get_item_stats(item_id):
    """
    Returns (item_name, total_bought, best_buyer_info, current_stock)
    best_buyer_info is (username, tg_id, count) or None
    """
    async with aiosqlite.connect(DB_PATH) as db:
        # Total bought (completed or paid)
        async with db.execute("SELECT COUNT(*) FROM sales WHERE item_id = ? AND status IN ('completed', 'paid')", (item_id,)) as c:
            total_bought = (await c.fetchone())[0]
            
        # Best buyer
        async with db.execute("""
            SELECT u.username, u.telegram_id, COUNT(s.id) as count
            FROM sales s
            JOIN users u ON s.user_id = u.id
            WHERE s.item_id = ? AND s.status IN ('completed', 'paid')
            GROUP BY s.user_id
            ORDER BY count DESC
            LIMIT 1
        """, (item_id,)) as c:
            best_buyer = await c.fetchone()
            
        # Item Name
        async with db.execute("SELECT name FROM items WHERE id = ?", (item_id,)) as c:
            name_row = await c.fetchone()
            item_name = name_row[0] if name_row else "Unknown"
            
        # Current Stock
        async with db.execute("""
            SELECT 
                (SELECT COUNT(DISTINCT secret_group) FROM item_images WHERE item_id = ? AND is_sold = 0 AND secret_group IS NOT NULL) +
                (SELECT COUNT(*) FROM item_images WHERE item_id = ? AND is_sold = 0 AND secret_group IS NULL)
        """, (item_id, item_id)) as c:
            current_stock = (await c.fetchone())[0]
            
        return item_name, total_bought, best_buyer, current_stock

async def get_user_total_sales(telegram_id):
    """Returns the total number of paid/completed sales for a user."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT COUNT(*) FROM sales 
            WHERE user_id = (SELECT id FROM users WHERE telegram_id = ?) 
              AND status IN ('paid', 'completed')
        """, (telegram_id,)) as c:
            row = await c.fetchone()
            return row[0] if row else 0

