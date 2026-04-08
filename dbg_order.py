import sqlite3
import json

db_path = "bot_database.sqlite"

def query_order(order_id):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check sale
    cursor.execute("""
        SELECT sales.id, sales.status, items.name, sales.amount_expected, sales.address_used, users.telegram_id, sales.user_id, sales.item_id
        FROM sales 
        JOIN items ON sales.item_id = items.id 
        JOIN users ON sales.user_id = users.id 
        WHERE sales.id = ?;
    """, (order_id,))
    sale = cursor.fetchone()
    
    if not sale:
        print(f"Order #{order_id} not found.")
        return

    print(f"Order #{sale[0]}")
    print(f"Status: {sale[1]}")
    print(f"Item: {sale[2]}")
    print(f"Expected: {sale[3]} LTC")
    print(f"Address: {sale[4]}")
    print(f"User TG ID: {sale[5]}")
    
    # Check stock for this item
    item_id = sale[7]
    cursor.execute("SELECT id, secret_group FROM item_images WHERE item_id = ? AND is_sold = 0 LIMIT 5;", (item_id,))
    stock = cursor.fetchall()
    print(f"\nAvailable Stock for this Item: {len(stock)} packages found (showing up to 5)")
    for s in stock:
        print(f" - Image ID: {s[0]} | Group: {s[1]}")
    
    conn.close()

if __name__ == "__main__":
    query_order(8)
