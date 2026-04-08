import sqlite3
import asyncio
from aiogram import Bot
from config import BOT_TOKEN, ADMIN_IDS

async def fulfill_order_manual(sale_id):
    db_path = "bot_database.sqlite"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Get order data
    cursor.execute("""
        SELECT sales.item_id, sales.user_id, items.name, users.telegram_id, sales.amount_expected
        FROM sales 
        JOIN items ON sales.item_id = items.id
        JOIN users ON sales.user_id = users.id
        WHERE sales.id = ?
    """, (sale_id,))
    data = cursor.fetchone()
    
    if not data:
        print(f"Order #{sale_id} not found.")
        return
        
    item_id, user_db_id, item_name, user_tg_id, amount = data
    
    # 2. Find available stock
    cursor.execute("SELECT id, image_url, media_type, secret_group FROM item_images WHERE item_id = ? AND is_sold = 0 LIMIT 1", (item_id,))
    image_row = cursor.fetchone()
    
    if not image_row:
        print(f"ERROR: No stock for item '{item_name}' (Item ID: {item_id})")
        return
        
    img_db_id, _, _, group_id = image_row
    
    # Fetch bundle if exists
    if group_id:
        cursor.execute("SELECT id, image_url, media_type FROM item_images WHERE secret_group = ?", (group_id,))
        bundle_items = cursor.fetchall()
    else:
        cursor.execute("SELECT id, image_url, media_type FROM item_images WHERE id = ?", (img_db_id,))
        bundle_items = cursor.fetchall()

    print(f"Found stock. Delivering {len(bundle_items)} items to User {user_tg_id}...")

    # 3. Marks as paid and sold in DB
    for b_id, _, _ in bundle_items:
        cursor.execute("UPDATE item_images SET is_sold = 1 WHERE id = ?", (b_id,))
    
    # Update sale status
    cursor.execute("UPDATE sales SET status = 'paid', amount_paid = ?, image_id = ?, tx_hash = 'RECOVERY_FORCE' WHERE id = ?", (amount, img_db_id, sale_id))
    
    # Release address
    cursor.execute("UPDATE addresses SET in_use_by_sale_id = NULL, locked_until = NULL WHERE in_use_by_sale_id = ?", (sale_id,))
    
    conn.commit()
    
    # 4. Physical delivery via Bot
    bot = Bot(token=BOT_TOKEN)
    try:
        await bot.send_message(user_tg_id, f"🎉 <b>LIVRARE REUȘITĂ! (Recuperare Automată)</b>\n\nProdus: <b>{item_name}</b>\nSecretul tău:")
        for _, val, mt in bundle_items:
            try:
                if mt == 'photo': await bot.send_photo(user_tg_id, photo=val)
                elif mt == 'video': await bot.send_video(user_tg_id, video=val)
                else: await bot.send_message(user_tg_id, f"<code>{val}</code>")
            except Exception:
                await bot.send_message(user_tg_id, f"<code>{val}</code>")
        
        print("Bot delivery successful!")
    except Exception as e:
        print(f"Bot delivery FAILED: {e}")
    finally:
        await bot.session.close()
    
    conn.close()

if __name__ == "__main__":
    asyncio.run(fulfill_order_manual(8))
