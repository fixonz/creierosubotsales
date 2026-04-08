from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import aiosqlite
import os
from config import ADMIN_IDS, DB_PATH

router = Router()

class AdminStates(StatesGroup):
    waiting_for_location_name = State()
    waiting_for_category_name = State()
    waiting_for_item_name = State()
    waiting_for_item_price = State()
    waiting_for_address = State()
    waiting_for_stock_image = State()
    waiting_for_item_product_image = State()
    waiting_for_category_sector = State()
    waiting_for_location_image = State()
    waiting_for_category_image = State()

async def smart_edit(message: types.Message, text: str, reply_markup: types.InlineKeyboardMarkup = None):
    if message.photo:
        try:
            await message.delete()
        except:
            pass
        await message.answer(text, reply_markup=reply_markup)
    else:
        try:
            await message.edit_text(text, reply_markup=reply_markup)
        except:
            await message.answer(text, reply_markup=reply_markup)

async def admin_panel_logic(message: types.Message):
    kb = [
        [types.InlineKeyboardButton(text="📍 Gestiune Locații", callback_data="admin_loc_list")],
        [types.InlineKeyboardButton(text="📁 Gestiune Categorii", callback_data="admin_cat_list")],
        [types.InlineKeyboardButton(text="📦 Gestiune Produse", callback_data="admin_item_list")],
        [types.InlineKeyboardButton(text="🖼️ Gestiune Stoc", callback_data="admin_stock_loc_list")],
        [types.InlineKeyboardButton(text="💳 Gestiune Adrese (Sloturi)", callback_data="admin_manage_addresses")],
        [types.InlineKeyboardButton(text="⏳ Comenzi în Așteptare", callback_data="admin_pending_sales")]
    ]
    await smart_edit(message, "👮 <b>PANOU CONTROL</b>\n\nSelectează o opțiune:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))

@router.message(Command("pending"))
async def cmd_pending(message: types.Message):
    if message.from_user.id not in ADMIN_IDS: return
    await show_admin_pending(message)

@router.callback_query(F.data == "admin_pending_sales")
async def cb_admin_pending(callback: types.CallbackQuery):
    await show_admin_pending(callback.message)
    await callback.answer()

async def show_admin_pending(message: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT s.id, i.name, s.amount_expected, u.username, s.status, s.created_at
            FROM sales s
            JOIN items i ON s.item_id = i.id
            JOIN users u ON s.user_id = u.id
            WHERE s.status IN ('pending', 'confirming')
            ORDER BY s.created_at DESC
        """) as cursor:
            pending = await cursor.fetchall()
            
    if not pending:
        return await smart_edit(message, "📭 <b>Nu există comenzi în așteptare.</b>", 
                               reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="🔙 Înapoi", callback_data="admin_main_go")]]))

    text = "⏳ <b>COMENZI ÎN AȘTEPTARE:</b>\n\n"
    kb = []
    for p in pending:
        s_id, i_name, amt, user, status, created = p
        text += f"• <b>#{s_id}</b> | {i_name} | {amt} LTC\n   👤 @{user or 'N/A'} | {status} | {created}\n\n"
        kb.append([
            types.InlineKeyboardButton(text=f"✅ Accept #{s_id}", callback_data=f"adm_force_ok_{s_id}"),
            types.InlineKeyboardButton(text=f"❌ Anulează #{s_id}", callback_data=f"adm_force_no_{s_id}")
        ])
    
    kb.append([types.InlineKeyboardButton(text="🔙 Înapoi", callback_data="admin_main_go")])
    await smart_edit(message, text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data.startswith("adm_force_ok_"))
async def adm_force_ok(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    sale_id = int(callback.data.split("_")[3])
    
    # We need to trigger the delivery logic. The easiest way without duplicating code 
    # is to fetch details and call the delivery part.
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT s.item_id, s.user_id, i.name, s.amount_expected, u.telegram_id
            FROM sales s 
            JOIN items i ON s.item_id = i.id
            JOIN users u ON s.user_id = u.id
            WHERE s.id = ?
        """, (sale_id,)) as cursor:
            sale = await cursor.fetchone()
            
    if not sale: return await callback.answer("Comandă inexistentă.")
    it_id, buyer_db_id, item_name, expected, buyer_tg_id = sale

    async with aiosqlite.connect(DB_PATH) as db:
        # Get stock
        async with db.execute("SELECT id, image_url, media_type FROM item_images WHERE item_id = ? AND is_sold = 0 LIMIT 1", (it_id,)) as img_cursor:
            img_row = await img_cursor.fetchone()
        
        if not img_row:
            return await callback.answer("STOC EPUIZAT! Nu pot finaliza manual.", show_alert=True)

        img_db_id, img_url, media_type = img_row
        await db.execute("UPDATE sales SET status = 'completed', tx_hash = ?, image_id = ?, amount_paid = ? WHERE id = ?", (f'MANUAL_BY_ADMIN_{sale_id}', img_db_id, expected, sale_id))
        await db.execute("UPDATE item_images SET is_sold = 1 WHERE id = ?", (img_db_id,))
        await db.execute("UPDATE addresses SET in_use_by_sale_id = NULL, locked_until = NULL WHERE in_use_by_sale_id = ?", (sale_id,))
        await db.commit()

    # Deliver to Buyer
    buyer_text = (
        f"✅ <b>COMANDĂ FINALIZATĂ MANUAL (# {sale_id})</b>\n\n"
        f"Produs: <b>{item_name}</b>\n"
        f"Admin-ul a aprobat plata ta.\n\n"
        f"<i>Îți mulțumim pentru achiziție!</i>"
    )
    
    try:
        file_input = types.FSInputFile(img_url) if os.path.exists(img_url) else img_url
        if media_type == 'video':
            await callback.bot.send_video(buyer_tg_id, video=file_input, caption=buyer_text)
        else:
            await callback.bot.send_photo(buyer_tg_id, photo=file_input, caption=buyer_text)
    except Exception as e:
        await callback.bot.send_message(buyer_tg_id, f"{buyer_text}\n\n⚠️ Eroare livrare media, dar comanda e validă.")

    # Notify Admins of manual delivery
    admin_notif_text = (
        f"✅ <b>COMANDĂ FINALIZATĂ MANUAL (# {sale_id})</b>\n\n"
        f"Produs: <b>{item_name}</b>\n"
        f"ID Client: {buyer_tg_id}\n\n"
        f"✅ Datele secrete (poză/video/coordonate) au fost trimise clientului cu succes."
    )
    for admin_id in ADMIN_IDS:
        try:
            await callback.bot.send_message(admin_id, admin_notif_text)
        except:
            pass

    await callback.answer(f"✅ Comanda #{sale_id} a fost finalizată manual!", show_alert=True)
    await show_admin_pending(callback.message)

@router.callback_query(F.data.startswith("adm_force_no_"))
async def adm_force_no(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    sale_id = int(callback.data.split("_")[3])
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE sales SET status = 'cancelled' WHERE id = ?", (sale_id,))
        await db.execute("UPDATE addresses SET in_use_by_sale_id = NULL, locked_until = NULL WHERE in_use_by_sale_id = ?", (sale_id,))
        await db.commit()
        
    await callback.answer(f"❌ Comanda #{sale_id} a fost anulată.", show_alert=True)
    await show_admin_pending(callback.message)

@router.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id not in ADMIN_IDS: return
    await admin_panel_logic(message)

@router.message(Command("unfreeze", prefix="!/"))
async def cmd_unfreeze_address(message: types.Message):
    if message.from_user.id not in ADMIN_IDS: return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("ℹ️ Utilizare: <code>/unfreeze [ADRESA] [TX_HASH_OPTIONAL] [SUMA_OPTIONAL]</code>")
        return
        
    address = parts[1]
    last_tx = parts[2] if len(parts) > 2 else None
    last_amount = None
    if len(parts) > 3:
        try:
            last_amount = float(parts[3])
        except: pass
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id FROM addresses WHERE crypto_address = ?", (address,)) as cursor:
            if not await cursor.fetchone():
                await message.answer(f"❌ Adresa <code>{address}</code> nu a fost găsită.")
                return
        
        await db.execute("""
            UPDATE addresses 
            SET in_use_by_sale_id = NULL, 
                locked_until = NULL,
                last_tx_hash = ?,
                last_amount = ?
            WHERE crypto_address = ?
        """, (last_tx, last_amount, address))
        await db.commit()
    
    msg = f"✅ Adresa <code>{address}</code> deblocată."
    if last_tx: msg += f"\nArzi TX: <code>{last_tx[:10]}...</code>"
    await message.answer(msg)

@router.callback_query(F.data == "admin_main_go")
async def cb_admin_main(callback: types.CallbackQuery):
    await admin_panel_logic(callback.message)
    await callback.answer()

# === LOCATIONS ===
@router.callback_query(F.data == "admin_loc_list")
async def loc_list(callback: types.CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, name FROM locations") as cursor:
            locs = await cursor.fetchall()
    kb = [[types.InlineKeyboardButton(text=l[1], callback_data=f"adm_loc_view_{l[0]}")] for l in locs]
    kb.append([types.InlineKeyboardButton(text="➕ Adaugă Locație", callback_data="admin_add_loc")])
    kb.append([types.InlineKeyboardButton(text="🔙 Înapoi", callback_data="admin_main_go")])
    await smart_edit(callback.message, "📍 <b>Locații:</b>", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@router.callback_query(F.data.startswith("adm_loc_view_"))
async def loc_view(callback: types.CallbackQuery):
    loc_id = int(callback.data.split("_")[3])
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name FROM locations WHERE id = ?", (loc_id,)) as cursor:
            loc = await cursor.fetchone()
    if not loc: return await callback.answer("Nu există.", show_alert=True)
    kb = [
        [types.InlineKeyboardButton(text="🖼️ Setează Imagine Menu", callback_data=f"adm_loc_img_{loc_id}")],
        [types.InlineKeyboardButton(text="🗑️ Șterge Locația", callback_data=f"adm_loc_del_{loc_id}")],
        [types.InlineKeyboardButton(text="🔙 Înapoi", callback_data="admin_loc_list")]
    ]
    await smart_edit(callback.message, f"📍 <b>Locație:</b> {loc[0]}\n\nPoți seta o imagine care va apărea ca fundal când utilizatorii selectează acest oraș.", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@router.callback_query(F.data.startswith("adm_loc_img_"))
async def adm_loc_img_start(callback: types.CallbackQuery, state: FSMContext):
    loc_id = int(callback.data.split("_")[3])
    await state.update_data(edit_loc_id=loc_id)
    await callback.message.answer("📸 Trimite o poză pentru fundalul acestei locații:")
    await state.set_state(AdminStates.waiting_for_location_image)
    await callback.answer()

@router.message(AdminStates.waiting_for_location_image, F.photo)
async def adm_loc_img_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    loc_id = data.get('edit_loc_id')
    file_id = message.photo[-1].file_id
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE locations SET display_image = ? WHERE id = ?", (file_id, loc_id))
        await db.commit()
    await message.answer("✅ Imaginea locației a fost actualizată!")
    await state.clear()
    await admin_panel_logic(message)

@router.callback_query(F.data.startswith("adm_loc_del_"))
async def loc_del(callback: types.CallbackQuery):
    loc_id = int(callback.data.split("_")[3])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM locations WHERE id = ?", (loc_id,))
        await db.commit()
    await callback.answer("Ștearsă cu succes!", show_alert=True)
    await loc_list(callback)

@router.callback_query(F.data == "admin_add_loc")
async def add_loc_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Te rog scrie numele noii locații (ex: Timișoara):")
    await state.set_state(AdminStates.waiting_for_location_name)
    await callback.answer()

@router.message(AdminStates.waiting_for_location_name)
async def add_loc_finish(message: types.Message, state: FSMContext):
    loc_name = message.text.strip()
    
    # Standard Categories Map
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
    
    async with aiosqlite.connect(DB_PATH) as db:
        # Default city image (bucuresti.jpg as a template)
        cursor = await db.execute("INSERT OR IGNORE INTO locations (name, display_image) VALUES (?, ?)", (loc_name, "assets/bucuresti.jpg"))
        loc_id = cursor.lastrowid
        
        if loc_id:
            # Auto-Add 9 Standard Categories
            for emoji, imgs in IMG_MAP.items():
                cat_img, sec_img = imgs
                cursor = await db.execute("INSERT INTO categories (location_id, name, description, display_image) VALUES (?, ?, ?, ?)", 
                                        (loc_id, emoji, f"Calitate premium {emoji}", cat_img))
                cat_id = cursor.lastrowid
                
                # Default 1x and 2x items
                await db.execute("INSERT INTO items (category_id, name, price_ron, product_image) VALUES (?, ?, ?, ?)", (cat_id, "1x", 500, sec_img))
                await db.execute("INSERT INTO items (category_id, name, price_ron, product_image) VALUES (?, ?, ?, ?)", (cat_id, "2x", 900, sec_img))
        
        await db.commit()
    await message.answer(f"✅ Locația <b>{loc_name}</b> a fost adăugată cu toate cele 9 categorii standard!")
    await state.clear()
    await admin_panel_logic(message)

# === CATEGORIES ===
# === ADMIN CATEGORIES NAVIGATION ===
@router.callback_query(F.data == "admin_cat_list")
async def navcat_loc_list(callback: types.CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, name FROM locations") as cursor:
            locs = await cursor.fetchall()
    
    kb = [[types.InlineKeyboardButton(text=l_name, callback_data=f"adm_navcat_loc_{l_id}")] for l_id, l_name in locs]
    kb.append([types.InlineKeyboardButton(text="➕ Adaugă Categorie Nouă", callback_data="admin_add_cat")])
    kb.append([types.InlineKeyboardButton(text="🔙 Înapoi", callback_data="admin_main_go")])
    await smart_edit(callback.message, "📁 <b>Gestiune Categorii - Alege Locația:</b>", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@router.callback_query(F.data.startswith("adm_navcat_loc_"))
async def navcat_sec_or_cat(callback: types.CallbackQuery):
    loc_id = int(callback.data.split("_")[3])
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name FROM locations WHERE id = ?", (loc_id,)) as cursor:
            loc = await cursor.fetchone()
            
    if loc and loc[0].lower() == "bucuresti":
        kb = [[types.InlineKeyboardButton(text=f"Sector {i}", callback_data=f"adm_navcat_sec_{loc_id}_{i}")] for i in range(1, 7)]
        kb.append([types.InlineKeyboardButton(text="Fără Sector", callback_data=f"adm_navcat_sec_{loc_id}_0")])
        kb.append([types.InlineKeyboardButton(text="🔙 Înapoi", callback_data="admin_cat_list")])
        await smart_edit(callback.message, "📁 <b>Gestiune Categorii - Alege Sectorul:</b>", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
        await callback.answer()
    else:
        await _show_nav_cats(callback, loc_id, 0)

@router.callback_query(F.data.startswith("adm_navcat_sec_"))
async def navcat_sec_list(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    loc_id = int(parts[3])
    sec_num = int(parts[4])
    await _show_nav_cats(callback, loc_id, sec_num)

async def _show_nav_cats(callback: types.CallbackQuery, loc_id: int, sec_num: int):
    async with aiosqlite.connect(DB_PATH) as db:
        if sec_num > 0:
            query = "SELECT id, name FROM categories WHERE location_id = ? AND sector = ?"
            params = (loc_id, sec_num)
        else:
            query = "SELECT id, name FROM categories WHERE location_id = ? AND (sector IS NULL OR sector = 0)"
            params = (loc_id,)
        async with db.execute(query, params) as cursor:
            cats = await cursor.fetchall()
            
    kb = []
    for c_id, c_name in cats:
        kb.append([types.InlineKeyboardButton(text=c_name, callback_data=f"adm_cat_view_{c_id}_{loc_id}_{sec_num}")])
        
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name FROM locations WHERE id = ?", (loc_id,)) as cursor:
            l_name = (await cursor.fetchone())[0]
            
    if l_name.lower() == "bucuresti":
        kb.append([types.InlineKeyboardButton(text="🔙 Înapoi", callback_data=f"adm_navcat_loc_{loc_id}")])
    else:
        kb.append([types.InlineKeyboardButton(text="🔙 Înapoi", callback_data="admin_cat_list")])
        
    await smart_edit(callback.message, "📁 <b>Modifică Categoria:</b>", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@router.callback_query(F.data.startswith("adm_cat_view_"))
async def cat_view(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    cat_id = int(parts[3])
    loc_id = int(parts[4]) if len(parts) > 4 else 0
    sec_num = int(parts[5]) if len(parts) > 5 else 0
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name FROM categories WHERE id = ?", (cat_id,)) as cursor:
            cat = await cursor.fetchone()
            
    if not cat: return await callback.answer("Nu există.", show_alert=True)
    
    if sec_num > 0:
        back_data = f"adm_navcat_sec_{loc_id}_{sec_num}"
    elif loc_id > 0:
        back_data = f"adm_navcat_loc_{loc_id}"
    else:
        back_data = "admin_cat_list"
        
    kb = [
        [types.InlineKeyboardButton(text="🖼️ Poză Categorie (+ descriere)", callback_data=f"adm_cat_img_{cat_id}")],
        [types.InlineKeyboardButton(text="🗑️ Șterge Categoria (Golește întâi Produsele)", callback_data=f"adm_cat_del_{cat_id}")],
        [types.InlineKeyboardButton(text="🔙 Înapoi", callback_data=back_data)]
    ]
    await smart_edit(callback.message, f"📁 <b>{cat[0]}</b>\n\nCe dorești să modifici?", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@router.callback_query(F.data.startswith("adm_cat_img_"))
async def adm_cat_img_start(callback: types.CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split("_")[3])
    await state.update_data(edit_cat_id=cat_id)
    await callback.message.answer("📸 Trimite o poză pentru fundalul acestei categorii:")
    await state.set_state(AdminStates.waiting_for_category_image)
    await callback.answer()

@router.message(AdminStates.waiting_for_category_image, F.photo)
async def adm_cat_img_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cat_id = data.get('edit_cat_id')
    file_id = message.photo[-1].file_id
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE categories SET display_image = ? WHERE id = ?", (file_id, cat_id))
        await db.commit()
    await message.answer("✅ Imaginea categoriei a fost actualizată!")
    await state.clear()
    await admin_panel_logic(message)

@router.callback_query(F.data.startswith("adm_cat_del_"))
async def cat_del(callback: types.CallbackQuery):
    cat_id = int(callback.data.split("_")[3])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
        await db.commit()
    await callback.answer("Ștearsă cu succes!", show_alert=True)
    await cat_list(callback)

@router.callback_query(F.data == "admin_add_cat")
async def add_cat_start(callback: types.CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, name FROM locations") as cursor:
            locs = await cursor.fetchall()
    if not locs:
        return await callback.answer("⚠️ Adaugă o locație mai întâi!", show_alert=True)
    kb = [[types.InlineKeyboardButton(text=l[1], callback_data=f"sel_loc_cat_{l[0]}")] for l in locs]
    kb.append([types.InlineKeyboardButton(text="🔙 Înapoi", callback_data="admin_cat_list")])
    await callback.message.edit_text("Selectează locația pentru categoria nouă:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@router.callback_query(F.data.startswith("sel_loc_cat_"))
async def add_cat_name(callback: types.CallbackQuery, state: FSMContext):
    loc_id = int(callback.data.split("_")[3])
    await state.update_data(loc_id=loc_id)
    await callback.message.answer("Scrie numele categoriei și emoji-ul ei (ex: ❄️ COCOS):")
    await state.set_state(AdminStates.waiting_for_category_name)
    await callback.answer()

@router.message(AdminStates.waiting_for_category_name)
async def add_cat_name_done(message: types.Message, state: FSMContext):
    cat_name = message.text.strip()
    await state.update_data(cat_name=cat_name)
    data = await state.get_data()
    loc_id = data['loc_id']
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name FROM locations WHERE id = ?", (loc_id,)) as cursor:
            loc = await cursor.fetchone()
            
    if loc and "bucuresti" in loc[0].lower():
        kb = []
        for i in range(1, 7):
            kb.append([types.InlineKeyboardButton(text=f"Sector {i}", callback_data=f"set_cat_sector_{i}")])
        kb.append([types.InlineKeyboardButton(text="Fără Sector (General)", callback_data="set_cat_sector_0")])
        await message.answer(f"📍 <b>București detectat!</b>\nÎn ce sector se află categoria <b>{cat_name}</b>?", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
        await state.set_state(AdminStates.waiting_for_category_sector)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT INTO categories (location_id, name) VALUES (?, ?)", (loc_id, cat_name))
            await db.commit()
        await message.answer(f"✅ Categoria <b>{cat_name}</b> adăugată!")
        await state.clear()
        await admin_panel_logic(message)

@router.callback_query(AdminStates.waiting_for_category_sector, F.data.startswith("set_cat_sector_"))
async def add_cat_sector_finish(callback: types.CallbackQuery, state: FSMContext):
    sector_num = int(callback.data.split("_")[3])
    data = await state.get_data()
    cat_name = data['cat_name']
    loc_id = data['loc_id']
    
    # sector 0 means NULL/General
    sector_val = sector_num if sector_num > 0 else None
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO categories (location_id, name, sector) VALUES (?, ?, ?)", 
                       (loc_id, cat_name, sector_val))
        await db.commit()
        
    await callback.message.answer(f"✅ Categoria <b>{cat_name}</b> adăugată în <b>Sector {sector_num if sector_num > 0 else 'General'}</b>!")
    await state.clear()
    await admin_panel_logic(callback.message)
    await callback.answer()

# === ITEMS ===
# === ADMIN ITEMS NAVIGATION ===
@router.callback_query(F.data == "admin_item_list")
async def navit_loc_list(callback: types.CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, name FROM locations") as cursor:
            locs = await cursor.fetchall()
            
    kb = [[types.InlineKeyboardButton(text=l_name, callback_data=f"adm_navit_loc_{l_id}")] for l_id, l_name in locs]
    kb.append([types.InlineKeyboardButton(text="➕ Adaugă Produs Nou", callback_data="admin_add_item")])
    kb.append([types.InlineKeyboardButton(text="🔙 Înapoi", callback_data="admin_main_go")])
    await smart_edit(callback.message, "📦 <b>Gestiune Produse - Alege Locația:</b>", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@router.callback_query(F.data.startswith("adm_navit_loc_"))
async def navit_sec_list(callback: types.CallbackQuery):
    loc_id = int(callback.data.split("_")[3])
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name FROM locations WHERE id = ?", (loc_id,)) as cursor:
            loc = await cursor.fetchone()
            
    if loc and loc[0].lower() == "bucuresti":
        kb = [[types.InlineKeyboardButton(text=f"Sector {i}", callback_data=f"adm_navit_sec_{loc_id}_{i}")] for i in range(1, 7)]
        kb.append([types.InlineKeyboardButton(text="Fără Sector", callback_data=f"adm_navit_sec_{loc_id}_0")])
        kb.append([types.InlineKeyboardButton(text="🔙 Înapoi", callback_data="admin_item_list")])
        await smart_edit(callback.message, "📦 <b>Gestiune Produse - Alege Sectorul:</b>", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
        await callback.answer()
    else:
        await _show_navit_cats(callback, loc_id, 0)

@router.callback_query(F.data.startswith("adm_navit_sec_"))
async def navit_sec_cat_list(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    loc_id = int(parts[3])
    sec_num = int(parts[4])
    await _show_navit_cats(callback, loc_id, sec_num)

async def _show_navit_cats(callback: types.CallbackQuery, loc_id: int, sec_num: int):
    async with aiosqlite.connect(DB_PATH) as db:
        if sec_num > 0:
            query = "SELECT id, name FROM categories WHERE location_id = ? AND sector = ?"
            params = (loc_id, sec_num)
        else:
            query = "SELECT id, name FROM categories WHERE location_id = ? AND (sector IS NULL OR sector = 0)"
            params = (loc_id,)
        async with db.execute(query, params) as cursor:
            cats = await cursor.fetchall()
            
    kb = [[types.InlineKeyboardButton(text=c_name, callback_data=f"adm_navit_c_{c_id}_{loc_id}_{sec_num}")] for c_id, c_name in cats]
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name FROM locations WHERE id = ?", (loc_id,)) as cursor:
            l_name = (await cursor.fetchone())[0]
            
    if l_name.lower() == "bucuresti":
        kb.append([types.InlineKeyboardButton(text="🔙 Înapoi", callback_data=f"adm_navit_loc_{loc_id}")])
    else:
        kb.append([types.InlineKeyboardButton(text="🔙 Înapoi", callback_data="admin_item_list")])
        
    await smart_edit(callback.message, "📦 <b>Gestiune Produse - Alege Categoria:</b>", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@router.callback_query(F.data.startswith("adm_navit_c_"))
async def navit_item_list(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    cat_id = int(parts[3])
    loc_id = int(parts[4]) if len(parts) > 4 else 0
    sec_num = int(parts[5]) if len(parts) > 5 else 0
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, name, price_ron FROM items WHERE category_id = ?", (cat_id,)) as cursor:
            items = await cursor.fetchall()
            
    kb = [[types.InlineKeyboardButton(text=f"{i_name} ({p_ron} RON)", callback_data=f"adm_item_view_{i_id}_{cat_id}_{loc_id}_{sec_num}")] for i_id, i_name, p_ron in items]
    
    if sec_num > 0:
        back_data = f"adm_navit_sec_{loc_id}_{sec_num}"
    elif loc_id > 0:
        back_data = f"adm_navit_loc_{loc_id}"
    else:
        back_data = "admin_item_list"
        
    kb.append([types.InlineKeyboardButton(text="🔙 Înapoi", callback_data=back_data)])
    await smart_edit(callback.message, "📦 <b>Gestiune Produse - Alege Produsul:</b>", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@router.callback_query(F.data.startswith("adm_item_view_"))
async def item_view(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    it_id = int(parts[3])
    cat_id = int(parts[4]) if len(parts) > 4 else 0
    loc_id = int(parts[5]) if len(parts) > 5 else 0
    sec_num = int(parts[6]) if len(parts) > 6 else 0
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name, price_ron, product_image FROM items WHERE id = ?", (it_id,)) as cursor:
            item = await cursor.fetchone()
    if not item: return await callback.answer("Nu există.", show_alert=True)
    
    name, price, current_img = item
    label_img = "🖼️ Schimbă Poză [ SECRET ] Spoiler" if current_img else "🖼️ Setează Poză [ SECRET ] Spoiler"
    
    if cat_id > 0:
        back_data = f"adm_navit_c_{cat_id}_{loc_id}_{sec_num}"
    else:
        back_data = "admin_item_list"
        
    kb = [
        [types.InlineKeyboardButton(text=label_img, callback_data=f"adm_item_set_img_{it_id}")],
        [types.InlineKeyboardButton(text="🗑️ Șterge Produsul", callback_data=f"adm_item_del_{it_id}")],
        [types.InlineKeyboardButton(text="🔙 Înapoi", callback_data=back_data)]
    ]
    
    caption = f"📦 <b>Produs:</b> {name}\n💰 <b>Preț:</b> {price} RON\n\n<i>POZA [ SECRET ] este cea cu watermark pe care o văd clienții blurred înainte de plată.</i>"
    
    if current_img:
        photo = types.FSInputFile(current_img) if (isinstance(current_img, str) and os.path.exists(current_img)) else current_img
        if callback.message.photo:
            await callback.message.edit_media(media=types.InputMediaPhoto(media=photo, caption=caption), reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
        else:
            await callback.message.answer_photo(photo=photo, caption=caption, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
            await callback.message.delete()
    else:
        await smart_edit(callback.message, caption, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()



@router.callback_query(F.data.startswith("adm_item_set_img_"))
async def adm_item_set_img_start(callback: types.CallbackQuery, state: FSMContext):
    it_id = int(callback.data.split("_")[4])
    await state.update_data(edit_item_id=it_id)
    await callback.message.answer("📸 Te rog trimite **O POZĂ** pe care dorești să o folosești ca IMAGINE SPOILER pentru acest produs:")
    await state.set_state(AdminStates.waiting_for_item_product_image)
    await callback.answer()

@router.message(AdminStates.waiting_for_item_product_image, F.photo)
async def adm_item_set_img_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    it_id = data.get('edit_item_id')
    file_id = message.photo[-1].file_id
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE items SET product_image = ? WHERE id = ?", (file_id, it_id))
        await db.commit()
        
    await message.answer("✅ Imaginea SPOILER a produsului a fost actualizată!")
    await state.clear()
    await admin_panel_logic(message)

@router.callback_query(F.data.startswith("adm_item_del_"))
async def item_del(callback: types.CallbackQuery):
    it_id = int(callback.data.split("_")[3])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM items WHERE id = ?", (it_id,))
        await db.commit()
    await callback.answer("Șters cu succes!", show_alert=True)
    await navit_loc_list(callback)

@router.callback_query(F.data == "admin_add_item")
async def add_item_start(callback: types.CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, name FROM locations") as cursor:
            locs = await cursor.fetchall()
            
    if not locs: return await callback.answer("Adaugă o locație mai întâi!", show_alert=True)
    
    kb = [[types.InlineKeyboardButton(text=l_name, callback_data=f"adm_addit_loc_{l_id}")] for l_id, l_name in locs]
    kb.append([types.InlineKeyboardButton(text="🔙 Înapoi", callback_data="admin_item_list")])
    await smart_edit(callback.message, "➕ <b>Adaugă Produs - Alege Locația:</b>", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@router.callback_query(F.data.startswith("adm_addit_loc_"))
async def add_item_sec_list(callback: types.CallbackQuery):
    loc_id = int(callback.data.split("_")[3])
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name FROM locations WHERE id = ?", (loc_id,)) as cursor:
            loc = await cursor.fetchone()
            
    if loc and loc[0].lower() == "bucuresti":
        kb = [[types.InlineKeyboardButton(text=f"Sector {i}", callback_data=f"adm_addit_sec_{loc_id}_{i}")] for i in range(1, 7)]
        kb.append([types.InlineKeyboardButton(text="Fără Sector", callback_data=f"adm_addit_sec_{loc_id}_0")])
        kb.append([types.InlineKeyboardButton(text="🔙 Înapoi", callback_data="admin_add_item")])
        await smart_edit(callback.message, "➕ <b>Adaugă Produs - Alege Sectorul:</b>", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
        await callback.answer()
    else:
        await _show_addit_cats(callback, loc_id, 0)

@router.callback_query(F.data.startswith("adm_addit_sec_"))
async def add_item_sec_cat_list(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    loc_id = int(parts[3])
    sec_num = int(parts[4])
    await _show_addit_cats(callback, loc_id, sec_num)

async def _show_addit_cats(callback: types.CallbackQuery, loc_id: int, sec_num: int):
    async with aiosqlite.connect(DB_PATH) as db:
        if sec_num > 0:
            query = "SELECT id, name FROM categories WHERE location_id = ? AND sector = ?"
            params = (loc_id, sec_num)
        else:
            query = "SELECT id, name FROM categories WHERE location_id = ? AND (sector IS NULL OR sector = 0)"
            params = (loc_id,)
        async with db.execute(query, params) as cursor:
            cats = await cursor.fetchall()
            
    if not cats:
        await callback.answer("Nu există categorii în această zonă.", show_alert=True)
        return
        
    kb = [[types.InlineKeyboardButton(text=c_name, callback_data=f"sel_cat_it_{c_id}")] for c_id, c_name in cats]
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name FROM locations WHERE id = ?", (loc_id,)) as cursor:
            l_name = (await cursor.fetchone())[0]
            
    if l_name.lower() == "bucuresti":
        kb.append([types.InlineKeyboardButton(text="🔙 Înapoi", callback_data=f"adm_addit_loc_{loc_id}")])
    else:
        kb.append([types.InlineKeyboardButton(text="🔙 Înapoi", callback_data="admin_add_item")])
        
    await smart_edit(callback.message, "➕ <b>Adaugă Produs - Categoria:</b>", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@router.callback_query(F.data.startswith("sel_cat_it_"))
async def add_item_name(callback: types.CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split("_")[3])
    await state.update_data(cat_id=cat_id)
    await callback.message.answer("Scrie numele produsului (ex: 1 PK, 0.5):")
    await state.set_state(AdminStates.waiting_for_item_name)
    await callback.answer()

@router.message(AdminStates.waiting_for_item_name)
async def add_item_price(message: types.Message, state: FSMContext):
    await state.update_data(item_name=message.text.strip())
    await message.answer("Scrie prețul în RON (doar număr, ex: 500):")
    await state.set_state(AdminStates.waiting_for_item_price)

@router.message(AdminStates.waiting_for_item_price)
async def add_item_finish(message: types.Message, state: FSMContext):
    try:
        price = float(message.text.strip())
        data = await state.get_data()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT INTO items (category_id, name, price_ron) VALUES (?, ?, ?)", 
                           (data['cat_id'], data['item_name'], price))
            await db.commit()
        await message.answer(f"✅ Produsul <b>{data['item_name']}</b> adăugat cu succes!")
        await state.clear()
        await admin_panel_logic(message)
    except:
        await message.answer("❌ Te rog introdu un număr valid (fără litere) pentru preț. Încearcă din nou!")

# === STOCK ===
# === ADMIN STOCK NAVIGATION ===
@router.callback_query(F.data == "admin_stock_loc_list")
async def stock_loc_list(callback: types.CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, name FROM locations") as cursor:
            locs = await cursor.fetchall()
            
    if not locs: return await callback.answer("Nu există locații.", show_alert=True)
    
    kb = []
    for l_id, l_name in locs:
        kb.append([types.InlineKeyboardButton(text=l_name, callback_data=f"adm_stk_loc_{l_id}")])
    kb.append([types.InlineKeyboardButton(text="🔙 Înapoi", callback_data="admin_main_go")])
    await smart_edit(callback.message, "🖼️ <b>Gestiune Stoc - Alege Locația:</b>", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@router.callback_query(F.data.startswith("adm_stk_loc_"))
async def stock_sec_or_cat_list(callback: types.CallbackQuery):
    loc_id = int(callback.data.split("_")[3])
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name FROM locations WHERE id = ?", (loc_id,)) as cursor:
            loc = await cursor.fetchone()
            
    if loc and loc[0].lower() == "bucuresti":
        kb = []
        for i in range(1, 7):
            kb.append([types.InlineKeyboardButton(text=f"Sector {i}", callback_data=f"adm_stk_sec_{loc_id}_{i}")])
        kb.append([types.InlineKeyboardButton(text="🔙 Înapoi", callback_data="admin_stock_loc_list")])
        await smart_edit(callback.message, "🖼️ <b>Gestiune Stoc - Alege Sectorul:</b>", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
        await callback.answer()
    else:
        await _show_stock_cats(callback, loc_id, 0)

@router.callback_query(F.data.startswith("adm_stk_sec_"))
async def stock_sec_cat_list(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    loc_id = int(parts[3])
    sec_num = int(parts[4])
    await _show_stock_cats(callback, loc_id, sec_num)

async def _show_stock_cats(callback: types.CallbackQuery, loc_id: int, sec_num: int):
    async with aiosqlite.connect(DB_PATH) as db:
        if sec_num > 0:
            query = "SELECT id, name FROM categories WHERE location_id = ? AND sector = ?"
            params = (loc_id, sec_num)
        else:
            query = "SELECT id, name FROM categories WHERE location_id = ? AND (sector IS NULL OR sector = 0)"
            params = (loc_id,)
        async with db.execute(query, params) as cursor:
            cats = await cursor.fetchall()
            
    if not cats:
        await callback.answer("Nu există categorii în această zonă.", show_alert=True)
        return
        
    kb = []
    for c_id, c_name in cats:
        kb.append([types.InlineKeyboardButton(text=c_name, callback_data=f"adm_stk_c_{c_id}_{loc_id}_{sec_num}")])
        
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name FROM locations WHERE id = ?", (loc_id,)) as cursor:
            l_name = (await cursor.fetchone())[0]
            
    if l_name.lower() == "bucuresti":
        kb.append([types.InlineKeyboardButton(text="🔙 Înapoi", callback_data=f"adm_stk_loc_{loc_id}")])
    else:
        kb.append([types.InlineKeyboardButton(text="🔙 Înapoi", callback_data="admin_stock_loc_list")])
        
    await smart_edit(callback.message, "🖼️ <b>Gestiune Stoc - Alege Categoria:</b>", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@router.callback_query(F.data.startswith("adm_stk_c_"))
async def stock_item_list(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    cat_id = int(parts[3])
    loc_id = int(parts[4]) if len(parts) > 4 else 0
    sec_num = int(parts[5]) if len(parts) > 5 else 0
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, name FROM items WHERE category_id = ?", (cat_id,)) as cursor:
            items = await cursor.fetchall()
            
    if not items: return await callback.answer("Nu există produse în această categorie.", show_alert=True)
    
    kb = [[types.InlineKeyboardButton(text=i[1], callback_data=f"adm_stk_i_{i[0]}_{cat_id}_{loc_id}_{sec_num}")] for i in items]
    
    if sec_num > 0:
        back_data = f"adm_stk_sec_{loc_id}_{sec_num}"
    elif loc_id > 0:
        back_data = f"adm_stk_loc_{loc_id}"
    else:
        back_data = "admin_stock_loc_list"
        
    kb.append([types.InlineKeyboardButton(text="🔙 Înapoi", callback_data=back_data)])
    await smart_edit(callback.message, "🖼️ <b>Gestiune Stoc - Alege Produsul:</b>", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@router.callback_query(F.data.startswith("adm_stk_i_"))
async def stock_item_view(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    it_id = int(parts[3])
    cat_id = int(parts[4]) if len(parts) > 4 else 0
    loc_id = int(parts[5]) if len(parts) > 5 else 0
    sec_num = int(parts[6]) if len(parts) > 6 else 0
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name FROM items WHERE id = ?", (it_id,)) as cursor:
            item = await cursor.fetchone()
        async with db.execute("SELECT COUNT(*) FROM item_images WHERE item_id = ? AND is_sold = 0", (it_id,)) as cursor:
            stock = (await cursor.fetchone())[0]
            
    if not item: return await callback.answer("Nu există.", show_alert=True)
    
    if cat_id > 0:
        back_data = f"adm_stk_c_{cat_id}_{loc_id}_{sec_num}"
    else:
        back_data = "admin_stock_loc_list"
        
    kb = [
        [types.InlineKeyboardButton(text="🖼️ Poză [ SECRET ] Spoiler", callback_data=f"adm_item_view_{it_id}")],
        [types.InlineKeyboardButton(text="📸 Adaugă Stoc (+1 Poză/Video)", callback_data=f"adm_stk_add_{it_id}")],
        [types.InlineKeyboardButton(text="🗑️ Golește TOT Stocul", callback_data=f"adm_stk_clear_{it_id}")],
        [types.InlineKeyboardButton(text="🔙 Înapoi", callback_data=back_data)]
    ]
    await smart_edit(callback.message, f"📦 <b>Stoc:</b> {item[0]}\n📈 <b>Cantitate actuală:</b> {stock} bucăți active\n\nAdaugă poze pentru stoc (care se trimit DUPĂ plată) sau gestionează spoilerul din butonul de mai sus.", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@router.callback_query(F.data.startswith("adm_stk_clear_"))
async def stock_clear(callback: types.CallbackQuery):
    it_id = int(callback.data.split("_")[3])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM item_images WHERE item_id = ?", (it_id,))
        await db.commit()
    await callback.answer("✅ Stoc complet golit!", show_alert=True)
    await stock_item_view(callback)

@router.callback_query(F.data.startswith("adm_stk_add_"))
async def stock_add_start(callback: types.CallbackQuery, state: FSMContext):
    it_id = int(callback.data.split("_")[3])
    await state.update_data(stk_item_id=it_id)
    await callback.message.answer("📥 Te rog trimite <b>O POZĂ</b> sau <b>UN VIDEO</b> (cu detalii/coordonate ascunse drept comentariu/caption) pentru acest produs.\nMedia va fi salvată în baza de date ca o bucată de stoc!")
    await state.set_state(AdminStates.waiting_for_stock_image)
    await callback.answer()

@router.message(AdminStates.waiting_for_stock_image, F.photo | F.video)
async def stock_add_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    it_id = data.get('stk_item_id')
    
    if message.photo:
        file_id = message.photo[-1].file_id
        media_type = 'photo'
    else:
        file_id = message.video.file_id
        media_type = 'video'
        
    secret_group = message.caption if message.caption else None
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO item_images (item_id, image_url, media_type, secret_group, is_sold) VALUES (?, ?, ?, ?, 0)", 
                       (it_id, file_id, media_type, secret_group))
        await db.commit()
        
    await message.answer(f"✅ <b>Stoc adăugat! (+1 {media_type.upper()})</b>\nTrimite o nouă media dacă mai dorești să adaugi stoc, altfel apasă /admin pentru a ieși.")

# --- MANAGE ADDRESSES ---
@router.callback_query(F.data == "admin_manage_addresses")
async def cb_manage_addresses(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, crypto_address FROM addresses ORDER BY id LIMIT 5") as cursor:
            slots = await cursor.fetchall()
            
    kb_rows = []
    for slot in slots:
        addr = slot[1]
        is_unset = addr.startswith("UNSET_SLOT_")
        label_text = "❌ SLOT NESETAT ❌" if is_unset else f"💎 {addr[:10]}...{addr[-6:]} 💎"
        btn_style = "danger" if is_unset else "success"
        
        kb_rows.append([types.InlineKeyboardButton(
            text=label_text, 
            callback_data=f"adm_edit_slot_{slot[0]}",
            **{"style": btn_style}
        )])
        
    kb_rows.append([types.InlineKeyboardButton(text="🔙 Înapoi", callback_data="admin_main_go")])
    kb = types.InlineKeyboardMarkup(inline_keyboard=kb_rows)
    
    label = "💳 <b>Gestiune Sloturi Adrese LTC</b>\nApasă pe un slot pentru a schimba adresa de primire.\nBot-ul va roti vizual aceste 5 adrese pentru plați și le va bloca selectiv pentru 30 minute la checkout."
    await smart_edit(callback.message, label, reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("adm_edit_slot_"))
async def cb_edit_address_slot(callback: types.CallbackQuery, state: FSMContext):
    slot_id = int(callback.data.split("_")[3])
    await state.update_data(edit_slot_id=slot_id)
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT crypto_address FROM addresses WHERE id = ?", (slot_id,)) as cursor:
            row = await cursor.fetchone()
            
    current_addr = row[0] if row else "UNSET"
    is_unset = current_addr.startswith("UNSET_SLOT_")
    
    if is_unset:
        label = f"📝 <b>Slot #{slot_id}</b> (Momentan Nesetat)\n\nTrimite noua adresă LTC în mesaje:"
        if callback.message.photo:
            await callback.message.edit_caption(caption=label, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="❌ Anulare", callback_data="admin_manage_addresses")]]))
        else:
            await callback.message.edit_text(label, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="❌ Anulare", callback_data="admin_manage_addresses")]]))
    else:
        label = (
            f"📝 <b>Slot #{slot_id}</b>\n\n"
            f"Adresă curentă: <code>{current_addr}</code>\n\n"
            "Trimite o nouă adresă LTC pentru a o schimba sau apasă Înapoi."
        )
        from utils.qr_gen import generate_ltc_qr
        qr = generate_ltc_qr(current_addr)
        if callback.message.photo:
            await callback.message.edit_media(media=types.InputMediaPhoto(media=qr, caption=label), reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="🔙 Înapoi", callback_data="admin_manage_addresses")]]))
        else:
            await callback.message.answer_photo(photo=qr, caption=label, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="🔙 Înapoi", callback_data="admin_manage_addresses")]]))
            await callback.message.delete()
    
    await state.set_state(AdminStates.waiting_for_address)
    await callback.answer()

@router.message(AdminStates.waiting_for_address)
async def process_new_slot_address(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    new_addr = message.text.strip()
    if len(new_addr) < 20:
        return await message.answer("❌ Adresa pare invalidă. Te rugăm să trimiți o adresă LTC validă.")
        
    data = await state.get_data()
    slot_id = data.get('edit_slot_id')
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE addresses SET crypto_address = ?, in_use_by_sale_id = NULL, locked_until = NULL WHERE id = ?", (new_addr, slot_id))
        await db.commit()
        
    await message.answer(f"✅ Slotul #{slot_id} a fost actualizat cu succes!\n\nNoua adresă: <code>{new_addr}</code>")
    await state.clear()
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="🔙 Înapoi la Adrese", callback_data="admin_manage_addresses")]])
    await message.answer("Panou Control:", reply_markup=kb)
