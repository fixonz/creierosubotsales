import os
import aiosqlite
import logging
import asyncio
import time
import unicodedata
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, FSInputFile

from config import DB_PATH, DEPOSIT_TIMEOUT_MINUTES, ADMIN_IDS
from database import add_user, get_and_create_sale
from utils.qr_gen import generate_ltc_qr
from utils.tatum import check_ltc_transaction
from utils.ltc_price import get_ltc_ron_price, ron_to_ltc

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

class ReviewState(StatesGroup):
    wait_rating = State()
    wait_comment = State()
    sale_id = State()

router = Router()

def get_branded_image(img_path, text, cache_key):
    """Brands an image with GTA font, transparency, and no diacritics."""
    if not img_path or not os.path.exists(img_path):
        return None
    
    # Remove diacritics and uppercase
    clean_text = "".join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn').upper()
    
    try:
        temp_path = f"tmp/{cache_key}.jpg"
        os.makedirs("tmp", exist_ok=True)
        
        with Image.open(img_path) as img:
            img = img.convert("RGBA")
            txt_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
            draw = ImageDraw.Draw(txt_layer)
            
            width, height = img.size
            font_path = "assets/gta.ttf"
            
            # Dynamic font size based on image height
            f_size = int(height * 0.1) 
            try:
                font = ImageFont.truetype(font_path, f_size)
            except:
                font = ImageFont.load_default()
            
            bbox = draw.textbbox((0, 0), clean_text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            
            x = (width - tw) / 2
            y = height - th - int(height * 0.08) # 8% from bottom
            
            # Shadow
            draw.text((x+2, y+2), clean_text, font=font, fill=(0, 0, 0, 150))
            # White transparent text
            draw.text((x, y), clean_text, font=font, fill=(255, 255, 255, 180))
            
            out = Image.alpha_composite(img, txt_layer)
            out = out.convert("RGB")
            out.save(temp_path, "JPEG", quality=90)
            return FSInputFile(temp_path)
    except Exception as e:
        logging.error(f"Branding error for {text}: {e}")
        return FSInputFile(img_path)

active_verifications = set() 

def get_main_menu(user_id: int):
    kb = [
        [InlineKeyboardButton(text="🏘️ Orașe", callback_data="show_locations")],
        [
            InlineKeyboardButton(text="👤 Profil", callback_data="user_profile"),
            InlineKeyboardButton(text="💬 Suport", callback_data="user_support")
        ],
        [InlineKeyboardButton(text="⭐ Recenzii", callback_data="show_reviews_0")]
    ]
    if user_id in ADMIN_IDS:
        kb.append([InlineKeyboardButton(text="🛠️ Panou Admin", callback_data="admin_main_go")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

async def check_and_show_pending(event: CallbackQuery | Message) -> bool:
    user_tg_id = event.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT sales.id, items.name, sales.amount_expected, sales.address_used, sales.created_at, items.price_ron, sales.status, categories.name
            FROM sales 
            JOIN items ON sales.item_id = items.id 
            JOIN users ON sales.user_id = users.id
            JOIN categories ON items.category_id = categories.id
            WHERE users.telegram_id = ? AND sales.status IN ('pending', 'confirming')
        """, (user_tg_id,)) as cursor:
            pending = await cursor.fetchone()

    if pending:
        sale_id, item_name, amount_ltc, address, created_at, price_ron, status, cat_name = pending
        emoji = cat_name.split()[0] if cat_name else "💎"
        created_dt = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
        expiry_dt = created_dt + timedelta(minutes=DEPOSIT_TIMEOUT_MINUTES)
        now = datetime.now()
        
        if now > expiry_dt and status == 'pending':
            async with aiosqlite.connect(DB_PATH) as db:
                cooldown_str = (datetime.now() + timedelta(minutes=30)).strftime('%Y-%m-%d %H:%M:%S')
                await db.execute("UPDATE sales SET status = 'cancelled' WHERE id = ? AND status = 'pending'", (sale_id,))
                await db.execute("UPDATE addresses SET in_use_by_sale_id = NULL, locked_until = ? WHERE in_use_by_sale_id = ?", (cooldown_str, sale_id))
                await db.commit()
            if isinstance(event, CallbackQuery):
                await event.answer("⚠️ Comanda ta a expirat și a fost anulată.", show_alert=True)
                try:
                    await event.message.delete()
                except: pass
                await event.message.answer("Comanda a expirat. Te rugăm să folosești /start pentru o nouă comandă.")
            else:
                await event.answer("⚠️ Comanda anterioară a expirat. Folosește /start pentru a începe una nouă.")
            return False 
            
        time_left = expiry_dt - now
        minutes_left = max(0, int(time_left.total_seconds() // 60))
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Verifică Plata", callback_data=f"verify_pay_{sale_id}")],
            [InlineKeyboardButton(text="❌ Anulează Comanda", callback_data=f"cancel_order_{sale_id}")]
        ])
        
        text = (
            f"⏳ <b>COMANDĂ ACTIVĂ (# {sale_id})</b>\n"
            f"Status: <code>{status.upper()}</code>\n"
            f"Confirmări: <code>0/1</code>\n\n"
            f"Ai o comandă activă pentru: <b>{item_name.replace('X', 'x')}{emoji}</b>\n\n"
            f"💰 <b>Suma MINIMĂ:</b> <code>{amount_ltc}</code> LTC\n"
            f"📍 <b>Adresa LTC:</b> <code>{address}</code>\n\n"
            f"⏰ <b>Expiră în:</b> <code>{minutes_left} minute</code>\n\n"
            f"<i>Botul verifică automat rețeaua. Livrarea se face INSTANT după prima confirmare.</i>"
        )
        
        qr_file = generate_ltc_qr(address, amount_ltc)
        if isinstance(event, CallbackQuery):
            try:
                qr_file = generate_ltc_qr(address, amount_ltc)
                if event.message.photo:
                    await event.message.edit_media(
                        media=InputMediaPhoto(media=qr_file, caption=text),
                        reply_markup=kb
                    )
                else:
                    await event.message.answer_photo(photo=qr_file, caption=text, reply_markup=kb)
                    await event.message.delete()
            except Exception as e:
                if "is not modified" not in str(e):
                    logging.error(f"Error showing pending with QR: {e}")
                if event.message.photo: 
                    try:
                        await event.message.edit_caption(caption=text, reply_markup=kb)
                    except Exception: pass
                else: 
                    try:
                        await event.message.edit_text(text, reply_markup=kb)
                    except Exception: pass
            await event.answer()
        else:
            await event.answer_photo(photo=qr_file, caption=text, reply_markup=kb)
        return True
    return False

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    await add_user(message.from_user.id, message.from_user.username)
    if await check_and_show_pending(message): return

    text = (
        "🏙 <b>New Simple Crypto Bot</b>\n\n"
        "Bun venit în cel mai securizat magazin digital. "
        "Plăți LTC verificate cu livrare instantanee.\n\n"
        "🛒 <b>Alege orașul de mai jos pentru a începe.</b>"
    )

    img_path = "assets/welcome.jpg"
    final_img = get_branded_image(img_path, "WELCOME", "welcome_branded")
    kb = get_main_menu(message.from_user.id)
    
    if final_img:
        await message.answer_photo(final_img, caption=text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=kb)

@router.callback_query(F.data == "back_to_menu")
async def cb_back_to_menu(callback: CallbackQuery):
    if await check_and_show_pending(callback): return
    text = (
        "🏙 <b>New Simple Crypto Bot</b>\n\n"
        "Bun venit în cel mai securizat magazin digital. "
        "Plăți LTC verificate cu livrare instantanee.\n\n"
        "🛒 <b>Alege orașul de mai jos pentru a începe.</b>"
    )
    kb = get_main_menu(callback.from_user.id)
    img_path = "assets/welcome.jpg"
    
    if os.path.exists(img_path):
        await callback.message.edit_media(media=InputMediaPhoto(media=FSInputFile(img_path), caption=text), reply_markup=kb)
    else:
        if callback.message.photo: await callback.message.edit_caption(caption=text, reply_markup=kb)
        else: await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data == "show_locations")
async def show_locations(callback: types.CallbackQuery):
    if await check_and_show_pending(callback): return
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, name FROM locations") as cursor:
            locs = await cursor.fetchall()

    if not locs:
        await callback.answer("Nicio locație configurată încă.", show_alert=True)
        return

    kb_rows = [[InlineKeyboardButton(text=f"📍 {l[1]}", callback_data=f"user_loc_{l[0]}")] for l in locs]
    kb_rows.append([InlineKeyboardButton(text="🔙 Înapoi la meniu", callback_data="back_to_menu")])
    
    caption = "🏘️ <b>SELECTEAZĂ ORAȘUL:</b>"
    # Note: We don't have a generic city overview image yet, so we stay on current image or set one
    if callback.message.photo:
        await callback.message.edit_caption(caption=caption, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    else:
        await callback.message.edit_text(caption, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    await callback.answer()

@router.callback_query(F.data.startswith("user_loc_"))
async def show_loc_or_sectors(callback: types.CallbackQuery):
    if await check_and_show_pending(callback): return
    loc_id = int(callback.data.split("_")[2])
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name, display_image FROM locations WHERE id = ?", (loc_id,)) as cursor:
            loc_data = await cursor.fetchone()
            
    if not loc_data: return await callback.answer("Locație invalidă.")
    
    is_bucuresti = "bucuresti" in loc_data[0].lower()
    
    if is_bucuresti:
        kb_rows = []
        # Row 1-2: Sectors 1-6
        kb_rows.append([
            InlineKeyboardButton(text="🔹 Sector 1", callback_data=f"user_sector_1_{loc_id}"),
            InlineKeyboardButton(text="🔹 Sector 2", callback_data=f"user_sector_2_{loc_id}"),
            InlineKeyboardButton(text="🔹 Sector 3", callback_data=f"user_sector_3_{loc_id}")
        ])
        kb_rows.append([
            InlineKeyboardButton(text="🔹 Sector 4", callback_data=f"user_sector_4_{loc_id}"),
            InlineKeyboardButton(text="🔹 Sector 5", callback_data=f"user_sector_5_{loc_id}"),
            InlineKeyboardButton(text="🔹 Sector 6", callback_data=f"user_sector_6_{loc_id}")
        ])
        kb_rows.append([InlineKeyboardButton(text="🔙 Înapoi la orașe", callback_data="show_locations")])
        kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
        caption = "🏙️ <b>BUCUREȘTI - ALEGE SECTORUL:</b>"
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT id, name FROM categories WHERE location_id = ?", (loc_id,)) as cursor:
                cats = await cursor.fetchall()
        
        if not cats:
            await callback.answer("✖️ Nicio categorie disponibilă aici.", show_alert=True)
            return await callback.answer()

        kb_rows = []
        current_row = []
        for cat in cats:
            # ONLY EMOJI
            btn_text = cat[1].split()[0] if cat[1] else "💎"
            current_row.append(InlineKeyboardButton(text=btn_text, callback_data=f"user_cat_{cat[0]}"))
            if len(current_row) == 3:
                kb_rows.append(current_row)
                current_row = []
        if current_row:
            kb_rows.append(current_row)
        
        kb_rows.append([InlineKeyboardButton(text="🔙 Înapoi la orașe", callback_data="show_locations")])
        kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
        caption = f"💎 <b>Alege o Categorie in {loc_data[0]}:</b>"

    img_path = loc_data[1] if loc_data and loc_data[1] else None
    logging.info(f"Showing location: {loc_data[0]} with image: {img_path}")
    
    final_img = None
    if img_path:
        # Try branding if it's a local file
        final_img = get_branded_image(img_path, loc_data[0], f"loc_{loc_id}")
        if not final_img:
            # Fallback to original img_path (FSInputFile for local, or file_id string)
            if os.path.exists(img_path): final_img = FSInputFile(img_path)
            else: final_img = img_path # Treat as File ID

    if final_img:
        try:
            await callback.message.edit_media(media=InputMediaPhoto(media=final_img, caption=caption), reply_markup=kb)
        except Exception as e:
            logging.error(f"Error editing media in show_loc_or_sectors: {e}")
            if callback.message.photo: await callback.message.edit_caption(caption=caption, reply_markup=kb)
            else: await callback.message.edit_text(caption, reply_markup=kb)
    else:
        if callback.message.photo: await callback.message.edit_caption(caption=caption, reply_markup=kb)
        else: await callback.message.edit_text(caption, reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("user_sector_"))
async def show_sector_categories(callback: types.CallbackQuery):
    if await check_and_show_pending(callback): return
    parts = callback.data.split("_")
    sector_num = int(parts[2])
    loc_id = int(parts[3])
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name, display_image FROM locations WHERE id = ?", (loc_id,)) as cursor:
            loc_data = await cursor.fetchone()
        async with db.execute("SELECT id, name FROM categories WHERE location_id = ? AND (sector = ? OR sector IS NULL)", (loc_id, sector_num)) as cursor:
            cats = await cursor.fetchall()
            
    if not cats:
        return await callback.answer(f"✖️ Nicio categorie disponibilă în Sector {sector_num}.", show_alert=True)

    kb_rows = []
    current_row = []
    for cat in cats:
        btn_text = cat[1].split()[0] if cat[1] else "💎"
        current_row.append(InlineKeyboardButton(text=btn_text, callback_data=f"user_cat_{cat[0]}_{sector_num}"))
        if len(current_row) == 3:
            kb_rows.append(current_row)
            current_row = []
    if current_row: kb_rows.append(current_row)
    
    kb_rows.append([InlineKeyboardButton(text="🔙 Înapoi la Sectoare", callback_data=f"user_loc_{loc_id}")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    
    caption = f"🏙️ <b>BUCUREȘTI - SECTOR {sector_num}</b>\n💎 Alege o categorie:"
    
    # Dynamic Image with Sector text
    img_path = loc_data[1] if loc_data and loc_data[1] else "assets/welcome.jpg"
    final_photo = get_branded_image(img_path, f"SECTOR {sector_num}", f"sector_{sector_num}_{loc_id}") or img_path
    
    if isinstance(final_photo, str):
        final_photo = FSInputFile(final_photo) if os.path.exists(final_photo) else final_photo

    if callback.message.photo:
        await callback.message.edit_media(media=InputMediaPhoto(media=final_photo, caption=caption), reply_markup=kb)
    else:
        await callback.message.answer_photo(photo=final_photo, caption=caption, reply_markup=kb)
        await callback.message.delete()
    await callback.answer()

@router.callback_query(F.data.startswith("user_cat_"))
async def show_items(callback: types.CallbackQuery):
    if await check_and_show_pending(callback): return
    parts = callback.data.split("_")
    cat_id = int(parts[2])
    sector_num = int(parts[3]) if len(parts) > 3 else 0
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name, description, display_image, location_id FROM categories WHERE id = ?", (cat_id,)) as cursor:
            cat_data = await cursor.fetchone()
        async with db.execute("""
            SELECT items.id, items.name, items.price_ron, categories.name,
                   (SELECT COUNT(*) FROM item_images WHERE item_id = items.id AND is_sold = 0) as stock
            FROM items 
            JOIN categories ON items.category_id = categories.id
            WHERE items.category_id = ?
            ORDER BY price_ron ASC
        """, (cat_id,)) as cursor:
            items = await cursor.fetchall()

    if not items:
        await callback.answer("✖️ Niciun produs disponibil.", show_alert=True)
        return await callback.answer()

    kb_rows = []
    for it in items:
        i_id, i_name, p_ron, cat_name, stock = it
        emoji = cat_name.split()[0] if cat_name else "💎"
        if stock > 0:
            label = f"🟢 {i_name.replace('X', 'x')}{emoji} | {int(p_ron)} RON"
            kb_rows.append([InlineKeyboardButton(text=label, callback_data=f"view_item_{i_id}_{sector_num}", **{"style": "success"})])
        else:
            label = f"🔴 {i_name.replace('X', 'x')}{emoji} | {int(p_ron)} RON"
            kb_rows.append([InlineKeyboardButton(text=label, callback_data=f"view_item_{i_id}_{sector_num}", **{"style": "danger"})])
    
    # Back button: if sector exists, go back to sector list, else back to loc
    if sector_num > 0:
        back_data = f"user_sector_{sector_num}_{cat_data[3]}"
    else:
        back_data = f"user_loc_{cat_data[3]}"
        
    kb_rows.append([InlineKeyboardButton(text="🔙 Înapoi", callback_data=back_data)])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    
    caption = f"🛒 <b>{cat_data[0]}</b>\n<i>{cat_data[1] or ''}</i>\n\n<b>PRODUSE DISPONIBILE:</b>"
    img_path = cat_data[2] if cat_data and cat_data[2] else None
    logging.info(f"Showing category items: {cat_data[0]} with image: {img_path}")

    final_img = None
    if img_path:
        if os.path.exists(img_path): final_img = FSInputFile(img_path)
        else: final_img = img_path

    if final_img:
        try:
            await callback.message.edit_media(media=InputMediaPhoto(media=final_img, caption=caption), reply_markup=kb)
        except Exception as e:
            logging.error(f"Error editing media in show_items: {e}")
            if callback.message.photo: await callback.message.edit_caption(caption=caption, reply_markup=kb)
            else: await callback.message.edit_text(caption, reply_markup=kb)
    else:
        if callback.message.photo: await callback.message.edit_caption(caption=caption, reply_markup=kb)
        else: await callback.message.edit_text(caption, reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("view_item_"))
async def view_item(callback: types.CallbackQuery):
    if await check_and_show_pending(callback): return
    parts = callback.data.split("_")
    item_id = int(parts[2])
    sector_num = int(parts[3]) if len(parts) > 3 else 0
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT i.name, i.price_ron, c.name, c.description, c.display_image, c.id,
                   (SELECT COUNT(*) FROM item_images WHERE item_id = i.id AND is_sold = 0) as stock
            FROM items i
            JOIN categories c ON i.category_id = c.id
            WHERE i.id = ?
        """, (item_id,)) as cursor:
            item = await cursor.fetchone()
            
    if not item: return await callback.answer("Produs inexistent.")
    
    name, price, cat_name, cat_desc, cat_img, cat_id, stock = item
    emoji = cat_name.split()[0] if cat_name else "💎"
    
    text = (
        f"<b>{name.replace('X', 'x')}{emoji}</b>\n\n"
        f"💰 Preț: <b>{int(price)} RON</b>\n"
        f"📦 Stoc: <b>{stock} disponibile</b>\n\n"
        f"<i>{cat_desc or ''}</i>"
    )
    
    kb_list = []
    if stock > 0:
        kb_list.append([InlineKeyboardButton(text=f"💳 Cumpără {name.replace('X', 'x')}{emoji}", callback_data=f"confirm_buy_{item_id}", **{"style": "success"})])
    else:
        kb_list.append([InlineKeyboardButton(text=f"⏳ Precomandă {name.replace('X', 'x')}{emoji}", callback_data=f"do_preorder_{item_id}", **{"style": "danger"})])
    
    kb_list.append([InlineKeyboardButton(text="📸 VEZI POZA REALĂ (SPOILER)", callback_data=f"real_photo_{item_id}_{sector_num}")])
    kb_list.append([InlineKeyboardButton(text="🔙 Înapoi", callback_data=f"user_cat_{cat_id}_{sector_num}")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=kb_list)
    
    if cat_img and os.path.exists(cat_img):
        await callback.message.edit_media(media=InputMediaPhoto(media=FSInputFile(cat_img), caption=text), reply_markup=kb)
    else:
        if callback.message.photo: await callback.message.edit_caption(caption=text, reply_markup=kb)
        else: await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("real_photo_"))
async def view_real_photo(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    item_id = int(parts[2])
    sector_num = int(parts[3]) if len(parts) > 3 else 0
    
    async with aiosqlite.connect(DB_PATH) as db:
        # Get the product image and category image
        async with db.execute("""
            SELECT i.product_image, i.name, c.display_image 
            FROM items i 
            JOIN categories c ON i.category_id = c.id 
            WHERE i.id = ?
        """, (item_id,)) as cursor:
            row = await cursor.fetchone()
            
    if not row: return await callback.answer("Eroare date.")
    product_img, item_name, cat_img = row

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Cumpără", callback_data=f"confirm_buy_{item_id}")],
        [InlineKeyboardButton(text="🔙 Înapoi", callback_data=f"view_item_{item_id}_{sector_num}")]
    ])
    
    caption = f"📸 <b>POZĂ REALĂ: {item_name}</b>\n<i>Produsul este sub spoiler pentru discreție.</i>"
    
    # Determine the photo to show
    photo = None
    if product_img:
        if os.path.exists(product_img):
            photo = FSInputFile(product_img)
        else:
            photo = product_img # Treat as File ID
    elif cat_img:
        # Resolve SECRET path
        secret_path = cat_img.replace("cat_", "SECRET_").replace("snow", "SNOW").replace("horse", "HORSE").replace("weed", "WEED").replace("champagne", "CHAMPAGNE").replace("candy", "CANDY").replace("runner", "RUNNER").replace("chocolate", "CHOCOLATE").replace("crystal", "CRYSTAL").replace("diamond", "DIAMOND")
        if os.path.exists(secret_path):
            photo = FSInputFile(secret_path)
    
    if photo:
        try:
            await callback.message.edit_media(media=InputMediaPhoto(media=photo, caption=caption, has_spoiler=True), reply_markup=kb)
        except Exception as e:
            logging.error(f"Error editing media in view_real_photo: {e}")
            await callback.answer("Imaginea nu a putut fi afișată.", show_alert=True)
    else:
        await callback.answer("Imaginea spoiler nu este disponibilă.", show_alert=True)
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_buy_"))
async def confirm_buy(callback: types.CallbackQuery):
    if await check_and_show_pending(callback): return
    item_id = int(callback.data.split("_")[2])
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM item_images WHERE item_id = ? AND is_sold = 0", (item_id,)) as cursor:
            stock = (await cursor.fetchone())[0]
        
        if stock <= 0:
            return await callback.answer("🚫 STOC EPUIZAT!", show_alert=True)

        async with db.execute("SELECT name, price_ron FROM items WHERE id = ?", (item_id,)) as cursor:
            item = await cursor.fetchone()
    
    if not item: return await callback.answer("Produs inexistent.")
    
    item_name, price_ron = item
    ltc_price = await get_ltc_ron_price()
    if not ltc_price: return await callback.answer("Eroare curs LTC.", show_alert=True)
    
    amount_ltc = ron_to_ltc(price_ron, ltc_price)
    address, final_amount, sale_id = await get_and_create_sale(callback.from_user.id, item_id, amount_ltc, DEPOSIT_TIMEOUT_MINUTES)
    
    if not address:
        return await callback.answer("Nu există adrese LTC.", show_alert=True)

    await check_and_show_pending(callback)

@router.callback_query(F.data.startswith("verify_pay_"))
async def verify_payment(callback: types.CallbackQuery):
    sale_id = int(callback.data.split("_")[2])
    if sale_id in active_verifications:
        return await callback.answer("⏳ Verificare în curs...", show_alert=True)
    
    label = "⏳ <b>VERIFICARE ACTIVĂ...</b>\n\nInterogăm blockchain-ul Litecoin. Te rugăm să aștepți."
    if callback.message.photo:
        await callback.message.edit_caption(caption=label, reply_markup=None)
    else:
        await callback.message.edit_text(label, reply_markup=None)
    await callback.answer()
    
    active_verifications.add(sale_id)
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("""
                SELECT s.address_used, s.amount_expected, s.created_at, s.status, i.name, s.user_id, s.item_id, a.last_tx_hash
                FROM sales s
                JOIN items i ON s.item_id = i.id
                JOIN addresses a ON s.address_used = a.crypto_address
                WHERE s.id = ?
            """, (sale_id,)) as cursor:
                sale = await cursor.fetchone()
        
        if not sale or sale[3] not in ['pending', 'confirming']:
            return await callback.answer("❌ Comandă invalidă sau deja procesată.")

        address, expected, created_at, status, item_name, user_id, it_id, last_tx = sale
        created_dt = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
        # Reducem bufferul la 2 minute (120s) pentru siguranță maximă împotriva tranzacțiilor vechi
        ts_since = int(created_dt.timestamp()) - 120

        is_paid, confirmations, tx_hash, paid_amount, needs_review = await check_ltc_transaction(address, expected, ts_since, last_tx)
        
        if is_paid and needs_review:
            # --- BORDERLINE PAYMENT - suspend and alert admins ---
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE sales SET status = 'confirming', tx_hash = ?, amount_paid = ? WHERE id = ?", (tx_hash, paid_amount, sale_id))
                await db.commit()

            diff_pct = round((paid_amount - expected) / expected * 100, 2)
            diff_sign = "+" if diff_pct >= 0 else ""
            confs_label = f"{confirmations} confirmări" if confirmations > 0 else "neconfirmat încă"

            review_kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✅ Aprobă și Livrează", callback_data=f"adm_force_ok_{sale_id}"),
                InlineKeyboardButton(text="❌ Refuză", callback_data=f"adm_force_no_{sale_id}")
            ]])
            review_msg = (
                f"⚠️ <b>PLATĂ BORDERLINE - NECESITĂ APROBARE</b>\n\n"
                f"🛍 Produs: <b>{item_name}</b>\n"
                f"👤 Client: @{callback.from_user.username or 'N/A'} ({callback.from_user.id})\n"
                f"💰 Trimis: <code>{paid_amount}</code> LTC\n"
                f"💵 Așteptat: <code>{expected}</code> LTC\n"
                f"📊 Diferență: <code>{diff_sign}{diff_pct}%</code>\n"
                f"🔗 TX: <code>{tx_hash}</code>\n"
                f"✅ Confirmări: <code>{confs_label}</code>\n\n"
                f"Apasă un buton pentru a decide:"
            )
            for admin_id in ADMIN_IDS:
                try:
                    await callback.bot.send_message(admin_id, review_msg, reply_markup=review_kb)
                except Exception as e:
                    logging.error(f"Failed to send review notif to admin {admin_id}: {e}")

            await callback.answer(
                f"⏳ Plată detectată dar în afara limitei automate ({diff_sign}{diff_pct}%). Adminul va decide în scurt timp.",
                show_alert=True
            )
            return

        if is_paid:
            logging.info(f"TATUM | VERIFY SUB | sale={sale_id} | path=auto_accept | confs={confirmations} ({type(confirmations)})")
            if confirmations < 1: # Changed from 3 to 1
                # Mark as confirming if it was pending
                if status == 'pending':
                    async with aiosqlite.connect(DB_PATH) as db:
                        await db.execute("UPDATE sales SET status = 'confirming', tx_hash = ? WHERE id = ?", (tx_hash, sale_id))
                        await db.commit()
                
                await callback.answer(f"⏳ Plată detectată! ({confirmations}/1 confirmări)", show_alert=False)
                
                # Update the message text to show confirmations
                text_update = (
                    f"⏳ <b>PLATĂ DETECTATĂ (# {sale_id})</b>\n"
                    f"Status: <code>CONFIRMING</code>\n"
                    f"Confirmări: <code>{confirmations}/1</code>\n\n"
                    f"Produs: <b>{item_name}</b>\n"
                    f"TX: <code>{tx_hash[:12]}...</code>\n"
                    f"Suma: <code>{paid_amount}</code> LTC\n\n"
                    f"<i>LTC Network a confirmat tranzacția. Livrarea se face automat la prima confirmare completă.</i>"
                )
                
                # Keep the buttons
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Re-verifică", callback_data=f"verify_pay_{sale_id}")],
                    [InlineKeyboardButton(text="❌ Anulează Comanda", callback_data=f"cancel_order_{sale_id}")]
                ])
                
                try:
                    if callback.message.photo:
                        await callback.message.edit_caption(caption=text_update, reply_markup=kb)
                    else:
                        await callback.message.edit_text(text=text_update, reply_markup=kb)
                except Exception:
                    pass
            else: # 1+ Confirmations -> DELIVER # Changed from 3+ to 1+
                # 3+ Confirmations -> DELIVER
                async with aiosqlite.connect(DB_PATH) as db:
                    # 0. Check for duplicate hash
                    async with db.execute("SELECT id FROM sales WHERE tx_hash = ? AND id != ?", (tx_hash, sale_id)) as dup_cursor:
                        if await dup_cursor.fetchone():
                            logging.warning(f"Double spend blocked! tx={tx_hash}")
                            await callback.answer("❌ Această tranzacție a fost deja procesată.", show_alert=True)
                            return

                    # 1. Get a random image from stock
                    async with db.execute("SELECT id, image_url, media_type FROM item_images WHERE item_id = ? AND is_sold = 0 LIMIT 1", (it_id,)) as img_cursor:
                        img_row = await img_cursor.fetchone()
                    
                    if not img_row:
                        # This should theoretically not happen if stock check was correct, but better safe
                        await callback.answer("⚠️ Eroare: Stoc epuizat în momentul livrării. Contactează suportul.", show_alert=True)
                        return

                    img_db_id, img_url, media_type = img_row

                    # 2. Update Sale and Item Image in a transaction
                    await db.execute("UPDATE sales SET status = 'completed', tx_hash = ?, image_id = ?, amount_paid = ? WHERE id = ?", (tx_hash, img_db_id, paid_amount, sale_id))
                    await db.execute("UPDATE item_images SET is_sold = 1 WHERE id = ?", (img_db_id,))
                    # 3. Scurt cooldown de siguranță de 3 minute chiar și la plată reușită
                    cooldown_str = (datetime.now() + timedelta(minutes=3)).strftime('%Y-%m-%d %H:%M:%S')
                    await db.execute("""
                        UPDATE addresses 
                        SET in_use_by_sale_id = NULL, 
                            locked_until = ?, 
                            last_tx_hash = ?, 
                            last_amount = ? 
                        WHERE in_use_by_sale_id = ?
                    """, (cooldown_str, tx_hash, paid_amount, sale_id))
                    await db.commit()

                # 4. Deliver to Buyer
                buyer_text = (
                    f"✅ <b>COMANDĂ FINALIZATĂ (# {sale_id})</b>\n\n"
                    f"Produs: <b>{item_name}</b>\n"
                    f"Livrăm coordonatele și pozele produsului tău mai jos.\n\n"
                    f"<i>Îți mulțumim pentru achiziție!</i>"
                )
                
                try:
                    file_input = FSInputFile(img_url) if os.path.exists(img_url) else img_url
                    if media_type == 'video':
                        await callback.message.answer_video(video=file_input, caption=buyer_text)
                    else:
                        await callback.message.answer_photo(photo=file_input, caption=buyer_text)
                    await callback.message.delete() 
                except Exception as e:
                    logging.error(f"Error delivering photo: {e}")
                    await callback.message.answer(f"{buyer_text}\n\n⚠️ Eroare la trimiterea pozei, dar comanda este salvată în profil.")

                # 5. Notify Admins
                admin_msg = (
                    f"💰 <b>VÂNZARE NOUĂ (AUTO-APROBATĂ)! (# {sale_id})</b>\n\n"
                    f"Produs: <b>{item_name}</b>\n"
                    f"Client: @{callback.from_user.username or 'Fara_Username'} (ID: {callback.from_user.id})\n"
                    f"Sumă primită: <code>{paid_amount}</code> LTC (Așteptat: {expected})\n"
                    f"Confirmări: <code>{confirmations}</code>\n"
                    f"TX: <code>{tx_hash}</code>\n\n"
                    f"✅ Datele secrete (poză/video/coordonate) au fost trimise clientului."
                )
                for admin_id in ADMIN_IDS:
                    try:
                        await callback.bot.send_message(admin_id, admin_msg)
                    except: pass
                    
                await callback.answer("✅ Produs livrat cu succes!", show_alert=True)
        else:
            fail_text = (
                f"❌ <b>PLATA NU A FOST GĂSITĂ ÎN BLOCKCHAIN</b>\n\n"
                f"Comandă: #<code>{sale_id}</code>\n"
                f"Suma așteptată: <code>{expected}</code> LTC\n"
                f"Adresa: <code>{address}</code>\n\n"
                f"<i>Dacă ai trimis deja banii, mai așteaptă puțin. Tranzacția este <b>PENDING</b> până apare în blockchain. "
                "Dacă nu este nimic valabil (nici măcar PENDING), înseamnă că nu ai trimis nimic. Asigură-te că ai trimis corect!</i>"
            )
            await callback.answer("❌ Nu am găsit nicio tranzacție.", show_alert=True)
            
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Re-verifică", callback_data=f"verify_pay_{sale_id}")],
                [InlineKeyboardButton(text="❌ Anulează Comanda", callback_data=f"cancel_order_{sale_id}")]
            ])
            
            try:
                if callback.message.photo:
                    await callback.message.edit_caption(caption=fail_text, reply_markup=kb)
                else:
                    await callback.message.edit_text(text=fail_text, reply_markup=kb)
            except: pass
    except Exception as e:
        logging.exception(f"Error in verify_payment: {e}")
        await callback.answer("⚠️ Eroare internă la verificare.", show_alert=True)
    finally:
        active_verifications.remove(sale_id)

@router.callback_query(F.data.startswith("cancel_order_"))
async def cancel_order(callback: types.CallbackQuery):
    sale_id = int(callback.data.split("_")[2])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE sales SET status = 'cancelled' WHERE id = ?", (sale_id,))
        await db.execute("UPDATE addresses SET in_use_by_sale_id = NULL, locked_until = NULL WHERE in_use_by_sale_id = ?", (sale_id,))
        await db.commit()
    await callback.answer("❌ Comandă anulată.")
    await show_locations(callback)

@router.callback_query(F.data == "admin_main_go")
async def admin_main_go(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    from handlers.admin import admin_panel_logic
    await admin_panel_logic(callback.message)
    await callback.answer()

@router.callback_query(F.data == "user_profile")
async def user_profile(callback: CallbackQuery):
    if await check_and_show_pending(callback): return
    user_tg_id = callback.from_user.id
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT u.username, u.joined_at, 
                   COUNT(s.id), 
                   SUM(CASE WHEN s.status = 'completed' THEN i.price_ron ELSE 0 END)
            FROM users u
            LEFT JOIN sales s ON u.id = s.user_id
            LEFT JOIN items i ON s.item_id = i.id
            WHERE u.telegram_id = ?
            GROUP BY u.id
        """, (user_tg_id,)) as cursor:
            row = await cursor.fetchone()
            
    if not row:
        return await callback.answer("Nu am putut găsi profilul tău.", show_alert=True)
        
    username, joined_at, total_orders, total_spent = row
    total_spent = total_spent or 0
    date_joined = joined_at.split()[0] if joined_at else "Nedefinit"
    
    label = (
        f"👤 <b>PROFILUL TĂU</b>\n\n"
        f"🆔 ID: <code>{user_tg_id}</code>\n"
        f"👤 Username: @{username or 'Fara_Username'}\n"
        f"📅 Membru din: <b>{date_joined}</b>\n\n"
        f"🛍️ Comenzi inițiate: <b>{total_orders}</b>\n"
        f"💸 Total cumpărături achitate: <b>{int(total_spent)} RON</b>\n\n"
        f"<i>Ultimele 10 comenzi finalizate:</i>"
    )

    kb_buttons = []
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT s.id, i.name, r.id
            FROM sales s
            JOIN items i ON s.item_id = i.id
            LEFT JOIN reviews r ON s.id = r.sale_id
            WHERE s.user_id = (SELECT id FROM users WHERE telegram_id = ?) 
              AND s.status IN ('completed', 'paid')
            ORDER BY s.id DESC LIMIT 10
        """, (user_tg_id,)) as cursor:
            recent_sales = await cursor.fetchall()
            
    for sid, iname, rev_id in recent_sales:
        # View content button first
        kb_buttons.append([InlineKeyboardButton(text=f"👁 Vezi Conținut #{sid} ({iname})", callback_data=f"view_secret_{sid}")])
        
        if rev_id:
            kb_buttons.append([InlineKeyboardButton(text=f"✅ {iname} (Recenzat)", callback_data="noop")])
        else:
            kb_buttons.append([InlineKeyboardButton(text=f"⭐ Lasă Recenzie - {iname}", callback_data=f"write_rev_{sid}")])
            
    kb_buttons.append([InlineKeyboardButton(text="🔙 Înapoi la meniu", callback_data="back_to_menu")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)

    if callback.message.photo:
        await callback.message.edit_caption(caption=label, reply_markup=kb)
    else:
        await callback.message.edit_text(label, reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("view_secret_"))
async def cb_view_order_secret(callback: CallbackQuery):
    sale_id = int(callback.data.split("_")[2])
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT i.name, s.user_id, u.telegram_id, img.secret_group, img.image_url, img.media_type
            FROM sales s
            JOIN items i ON s.item_id = i.id
            JOIN users u ON s.user_id = u.id
            JOIN item_images img ON s.image_id = img.id
            WHERE s.id = ? AND s.status IN ('completed', 'paid')
        """, (sale_id,)) as cursor:
            data = await cursor.fetchone()
            
    if not data or data[2] != callback.from_user.id:
        await callback.answer("Comandă neautorizată sau inexistentă.", show_alert=True)
        return
        
    name, _, user_tg_id, group_id, first_url, first_type = data
    
    async with aiosqlite.connect(DB_PATH) as db:
        if group_id:
            async with db.execute("SELECT image_url, media_type FROM item_images WHERE secret_group = ?", (group_id,)) as cursor:
                contents = await cursor.fetchall()
        else:
            contents = [(first_url, first_type)]

    msg_text = f"📦 <b>Conținut Comandă #{sale_id}</b>\nProdus: <b>{name}</b>"
    await callback.bot.send_message(user_tg_id, msg_text)

    for val, m_type in contents:
        try:
            if m_type == 'photo':
                await callback.bot.send_photo(user_tg_id, photo=val if not os.path.exists(val) else FSInputFile(val))
            elif m_type == 'video':
                await callback.bot.send_video(user_tg_id, video=val if not os.path.exists(val) else FSInputFile(val))
            else:
                await callback.bot.send_message(user_tg_id, f"<code>{val}</code>")
        except:
            await callback.bot.send_message(user_tg_id, f"<code>{val}</code>")
        
    await callback.answer("Ți-am retrimis mesajele cu stocul!", show_alert=True)

@router.callback_query(F.data.startswith("show_reviews_"))
async def show_reviews(callback: CallbackQuery):
    parts = callback.data.split("_")
    offset = int(parts[2]) if len(parts) > 2 else 0
    limit = 5  # Reviews per page
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT r.rating, r.comment, u.username, i.name, r.created_at, c.name
            FROM reviews r
            JOIN sales s ON r.sale_id = s.id
            JOIN items i ON s.item_id = i.id
            JOIN categories c ON i.category_id = c.id
            JOIN users u ON r.user_id = u.id
            ORDER BY r.id DESC LIMIT ? OFFSET ?
        """, (limit, offset)) as cursor:
            reviews = await cursor.fetchall()

        async with db.execute("SELECT AVG(rating), COUNT(*) FROM reviews") as cursor:
            avg_data = await cursor.fetchone()
            
    avg_rating = round(avg_data[0] or 0, 1)
    total_reviews = avg_data[1] or 0

    if total_reviews == 0:
        text = "⭐ <b>RECENZII</b>\n\nNu există recenzii momentan. Fii primul care lasă una după o achiziție!"
        kb_buttons = [[InlineKeyboardButton(text="🔙 Înapoi la meniu", callback_data="back_to_menu")]]
    else:
        text = f"⭐ <b>RECENZII CLIENȚI</b>\n\n📊 Notă medie: <b>{avg_rating}/5.0</b> ({total_reviews} recenzii)\n\n"
        for rating, comment, uname, iname, created_at, cname in reviews:
            stars = "⭐" * rating
            uname_disp = f"@{uname}" if uname else "Anonim"
            date_disp = created_at.split()[0] if created_at else ""
            
            # Extract emoji and display name of category 
            # (assuming category name has emoji first)
            cat_display = cname.split(" ")[0] if cname else ""
            
            text += f"{stars} <b>{cat_display} {iname}</b> - {uname_disp}\n"
            text += f"<i>\"{comment}\"</i>\n📅 {date_disp}\n\n"
            
        nav_buttons = []
        if offset > 0:
            nav_buttons.append(InlineKeyboardButton(text="⬅️ Mai noi", callback_data=f"show_reviews_{max(0, offset - limit)}"))
        if offset + limit < total_reviews:
            nav_buttons.append(InlineKeyboardButton(text="Mai vechi ➡️", callback_data=f"show_reviews_{offset + limit}"))
            
        kb_buttons = []
        if nav_buttons:
            kb_buttons.append(nav_buttons)
        kb_buttons.append([InlineKeyboardButton(text="🔙 Înapoi la meniu", callback_data="back_to_menu")])

    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=kb)
    else:
        await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("write_rev_"))
async def write_review_start(callback: CallbackQuery, state: FSMContext):
    sale_id = int(callback.data.split("_")[2])
    
    # Check if already reviewed
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id FROM reviews WHERE sale_id = ?", (sale_id,)) as cursor:
            if await cursor.fetchone():
                return await callback.answer("Ai lăsat deja o recenzie pentru această comandă!", show_alert=True)
                
    await state.update_data(sale_id=sale_id)
    await state.set_state(ReviewState.wait_rating)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐⭐⭐⭐⭐ 5 (Excelent)", callback_data="rev_rate_5")],
        [InlineKeyboardButton(text="⭐⭐⭐⭐ 4 (Foarte Bun)", callback_data="rev_rate_4")],
        [InlineKeyboardButton(text="⭐⭐⭐ 3 (Bun)", callback_data="rev_rate_3")],
        [InlineKeyboardButton(text="⭐⭐ 2 (Slab)", callback_data="rev_rate_2")],
        [InlineKeyboardButton(text="⭐ 1 (Foarte Slab)", callback_data="rev_rate_1")],
        [InlineKeyboardButton(text="❌ Anulează", callback_data="back_to_menu")]
    ])
    
    text = f"⭐ <b>LĂSARE RECENZIE</b> (# {sale_id})\n\nCe notă acorzi experienței tale?"
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=kb)
    else:
        await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@router.callback_query(ReviewState.wait_rating, F.data.startswith("rev_rate_"))
async def process_rating(callback: CallbackQuery, state: FSMContext):
    rating = int(callback.data.split("_")[2])
    data = await state.get_data()
    sale_id = data['sale_id']
    
    await state.update_data(rating=rating)
    await state.set_state(ReviewState.wait_comment)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Anulează", callback_data="back_to_menu")]])
    text = (
        f"⭐ Ai selectat nota: <b>{rating}</b>\n\n"
        f"Te rugăm să scrii un scurt comentariu despre produs/experiență (dă-ne un reply direct cu mesajul tău)."
    )
    
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=kb)
    else:
        await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@router.message(ReviewState.wait_comment, F.text)
async def process_comment(message: Message, state: FSMContext):
    comment = message.text[:500] # Limit to 500 chars
    data = await state.get_data()
    rating = data['rating']
    sale_id = data['sale_id']
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id FROM users WHERE telegram_id = ?", (message.from_user.id,)) as cursor:
            u_row = await cursor.fetchone()
            if not u_row:
                await state.clear()
                return await message.answer("⚠️ Eroare de utilizator.")
            user_id = u_row[0]
            
        try:
            await db.execute(
                "INSERT INTO reviews (user_id, sale_id, rating, comment) VALUES (?, ?, ?, ?)",
                (user_id, sale_id, rating, comment)
            )
            await db.commit()
            
            await message.answer("✅ <b>Recenzia ta a fost salvată!</b> Îți mulțumim pentru feedback-ul acordat.", reply_markup=get_main_menu(message.from_user.id))
        except Exception as e:
            logging.error(f"Error saving review: {e}")
            await message.answer("⚠️ O eroare a apărut. Probabil ai recenzat deja comanda.", reply_markup=get_main_menu(message.from_user.id))
            
    await state.clear()

@router.callback_query(F.data.startswith("view_preorder_"))
async def view_preorder(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    item_id = int(parts[2])
    sector_num = int(parts[3]) if len(parts) > 3 else 0
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT i.name, i.price_ron, c.name, c.display_image, c.id 
            FROM items i
            JOIN categories c ON i.category_id = c.id
            WHERE i.id = ?
        """, (item_id,)) as cursor:
            item = await cursor.fetchone()
            
    if not item: return await callback.answer("Produs inexistent.")
    name, price, cat_name, cat_img, cat_id = item
    emoji = cat_name.split()[0] if cat_name else "💎"
    
    text = (
        f"⏳ <b>PRECOMANDĂ: {name.replace('X', 'x')}{emoji}</b>\n\n"
        f"Stocul este momentan epuizat, dar poți plasa o precomandă.\n"
        f"Admin-ul va verifica cererea și te va contacta în bot.\n\n"
        f"💰 Preț: <b>{int(price)} RON</b>"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Trimite Precomandă", callback_data=f"do_preorder_{item_id}")],
        [InlineKeyboardButton(text="🔙 Înapoi", callback_data=f"user_cat_{cat_id}_{sector_num}")]
    ])
    
    if cat_img and os.path.exists(cat_img):
        await callback.message.edit_media(media=InputMediaPhoto(media=FSInputFile(cat_img), caption=text), reply_markup=kb)
    else:
        if callback.message.photo: await callback.message.edit_caption(caption=text, reply_markup=kb)
        else: await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("do_preorder_"))
async def do_preorder_finish(callback: types.CallbackQuery):
    item_id = int(callback.data.split("_")[2])
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id FROM users WHERE telegram_id = ?", (callback.from_user.id,)) as cursor:
            user_row = await cursor.fetchone()
            if not user_row: return await callback.answer("User error.")
            user_db_id = user_row[0]

        # Check for existing active preorder
        async with db.execute("SELECT id FROM preorders WHERE user_id = ? AND status = 'pending'", (user_db_id,)) as cursor:
            if await cursor.fetchone():
                return await callback.answer("⚠️ Ai deja o precomandă în curs de procesare. Te rugăm să aștepți aprobarea admin-ului.", show_alert=True)
            
        async with db.execute("SELECT name FROM items WHERE id = ?", (item_id,)) as cursor:
            it_name = (await cursor.fetchone())[0]

        cursor = await db.execute("INSERT INTO preorders (user_id, item_id) VALUES (?, ?)", (user_db_id, item_id))
        preo_id = cursor.lastrowid
        await db.commit()
        
    await callback.message.answer(f"✅ <b>PRECOMANDĂ TRIMISĂ (# {preo_id})</b>\nS-a solicitat: <b>{it_name}</b>.\nVei primi o notificare aici când admin-ul procesează cererea.")
    await callback.message.delete()

    # Notify Admins
    from config import ADMIN_IDS
    admin_msg = (
        f"🔔 <b>PRECOMANDĂ NOUĂ! (# {preo_id})</b>\n\n"
        f"Produs: <b>{it_name}</b>\n"
        f"Client: @{callback.from_user.username or 'Fara_Username'} (ID: {callback.from_user.id})\n"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Acceptă", callback_data=f"adm_preo_ok_{preo_id}"),
            InlineKeyboardButton(text="❌ Refuză", callback_data=f"adm_preo_no_{preo_id}")
        ]
    ])
    
    for admin_id in ADMIN_IDS:
        try: await callback.bot.send_message(admin_id, admin_msg, reply_markup=kb)
        except: pass
    await callback.answer()

@router.callback_query(F.data.startswith("adm_preo_"))
async def admin_handle_preorder(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    parts = callback.data.split("_")
    action = parts[2] # ok or no
    preo_id = int(parts[3])
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT p.user_id, i.name, u.telegram_id 
            FROM preorders p
            JOIN items i ON p.item_id = i.id
            JOIN users u ON p.user_id = u.id
            WHERE p.id = ?
        """, (preo_id,)) as cursor:
            preo = await cursor.fetchone()
            
    if not preo: return await callback.answer("Precomandă inexistentă.")
    u_db_id, it_name, u_tg_id = preo
    
    if action == "ok":
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE preorders SET status = 'accepted' WHERE id = ?", (preo_id,))
            await db.commit()
        
        user_text = f"✅ <b>PRECOMANDĂ ACCEPTATĂ! (# {preo_id})</b>\nAdmin-ul a aprobat cererea ta pentru <b>{it_name}</b>.\nTe va contacta în scurt timp!"
        await callback.bot.send_message(u_tg_id, user_text)
        await callback.message.edit_text(callback.message.text + "\n\n✅ <b>STARE: ACCEPTATĂ</b>")
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE preorders SET status = 'declined' WHERE id = ?", (preo_id,))
            await db.commit()
            
        user_text = f"❌ <b>PRECOMANDĂ REFUZATĂ (# {preo_id})</b>\nCererea ta pentru <b>{it_name}</b> nu a putut fi onorată momentan."
        await callback.bot.send_message(u_tg_id, user_text)
        await callback.message.edit_text(callback.message.text + "\n\n❌ <b>STARE: REFUZATĂ</b>")
    
    await callback.answer()
