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
        
        await db.commit()
        await ensure_5_slots()
        logging.info("A1 Z1 C1 2C2 Database initialized with reviews support.")

async def ensure_5_slots():
    """Ensure there are at least 5 rows in the addresses table."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM addresses") as cursor:
            count = (await cursor.fetchone())[0]
        
        if count < 5:
            for i in range(5 - count):
                await db.execute("INSERT INTO addresses (crypto_address) VALUES (?)", (f"UNSET_SLOT_{i+count+1}",))
            await db.commit()

# --- Repository functions ---

async def get_and_create_sale(user_tg_id: int, item_id: int, base_amount: float, timeout_minutes: int):
    """
    Finds an address and creates a pending sale. 
    If all addresses are "locked", it reuses one but adds a small increment (0.0001 LTC) 
    to the amount to stay unique.
    Returns (address, final_amount, sale_id).
    """
    from datetime import datetime, timedelta
    now = datetime.now()
    now_str = now.strftime('%Y-%m-%d %H:%M:%S')
    expires_at = now + timedelta(minutes=timeout_minutes)
    expires_str = expires_at.strftime('%Y-%m-%d %H:%M:%S')

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        
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

