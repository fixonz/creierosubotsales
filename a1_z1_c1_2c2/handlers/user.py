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

from config import DB_PATH, DEPOSIT_TIMEOUT_MINUTES, ADMIN_IDS, TRANSACTION_FEE_PERCENT
from database import add_user, get_and_create_sale, is_silent_mode, get_item_stats, get_user_total_sales
from utils.qr_gen import generate_ltc_qr
from utils.tatum import check_ltc_transaction
from utils.ltc_price import get_ltc_ron_price, ron_to_ltc
from utils.localization import get_text

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
        if os.path.exists(temp_path):
            return FSInputFile(temp_path)
            
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

lang_cache = {}

async def get_user_lang(user_tg_id: int) -> str:
    if user_tg_id in lang_cache:
        return lang_cache[user_tg_id]
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT language FROM users WHERE telegram_id = ?", (user_tg_id,)) as cursor:
            row = await cursor.fetchone()
            lang = row[0] if row and row[0] else 'ro'
            lang_cache[user_tg_id] = lang
            return lang

def get_main_menu(user_id: int, lang: str = "ro"):
    kb = [
        [InlineKeyboardButton(text=get_text("btn_cities", lang), callback_data="show_locations")],
        [
            InlineKeyboardButton(text=get_text("btn_profile", lang), callback_data="user_profile"),
            InlineKeyboardButton(text=get_text("btn_support", lang), callback_data="user_support")
        ],
        [InlineKeyboardButton(text=get_text("btn_reviews", lang), callback_data="show_reviews_0")]
    ]
    if user_id in ADMIN_IDS:
        kb.append([InlineKeyboardButton(text="🛠️ Admin Panel", callback_data="admin_main_go")])
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
            lang = await get_user_lang(user_tg_id)
            if isinstance(event, CallbackQuery):
                await event.answer(get_text("order_expired_alert", lang), show_alert=True)
                try:
                    await event.message.delete()
                except: pass 
                await event.message.answer(get_text("order_expired_text", lang))
            else:
                await event.answer(get_text("order_expired_prev", lang))
            return False 
            
        time_left = expiry_dt - now
        minutes_left = max(0, int(time_left.total_seconds() // 60))
        
        lang = await get_user_lang(user_tg_id)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=get_text("verify_payment_btn", lang), callback_data=f"verify_pay_{sale_id}")],
            [InlineKeyboardButton(text=get_text("cancel_order_btn", lang), callback_data=f"cancel_order_{sale_id}")]
        ])
        
        text = (
            f"{get_text('active_order_title', lang)}\n"
            f"{get_text('active_order_id', lang, sale_id=sale_id)}\n"
            f"{get_text('active_order_status', lang, status=status.upper())}\n"
            f"{get_text('active_order_confs', lang)}\n\n"
            f"{get_text('active_order_for', lang, item_name=item_name.replace('X', 'x') + emoji)}\n\n"
            f"{get_text('active_order_value', lang, price_ron=int(price_ron))}\n"
            f"{get_text('active_order_amount', lang, amount_ltc=amount_ltc)}\n"
            f"{get_text('active_order_address', lang, address=address)}\n\n"
            f"{get_text('active_order_expires', lang, minutes=minutes_left)}\n\n"
            f"{get_text('active_order_footer', lang)}"
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

@router.message(Command("pending", prefix="!/"))
async def cmd_pending(message: types.Message):
    if message.from_user.id in ADMIN_IDS:
        from handlers.admin import cmd_pending as admin_pending_cmd
        await admin_pending_cmd(message)

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    user_tg_id = message.from_user.id
    await add_user(user_tg_id, message.from_user.username)
    lang = await get_user_lang(user_tg_id)

    # --- ADMIN FEED UPDATE (Client notification only) ---

    from handlers.admin import send_feed_update
    await send_feed_update(message.bot, f"👤 <b>CLIENT ACTIV</b>\nUser: @{message.from_user.username or 'N/A'} (ID: {user_tg_id})")
    
    if await check_and_show_pending(message): return

    text = get_text("welcome", lang)
    img_path = "assets/welcome.jpg"
    final_img = get_branded_image(img_path, "WELCOME", "welcome_branded")
    kb = get_main_menu(user_tg_id, lang)
    
    
    if final_img:
        await message.answer_photo(final_img, caption=text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "change_language")
async def cb_change_language(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇷🇴 Română", callback_data="set_lang_ro"),
            InlineKeyboardButton(text="🇺🇸 English", callback_data="set_lang_en")
        ],
        [InlineKeyboardButton(text="🔙 Back", callback_data="user_profile")]
    ])
    await callback.message.edit_caption(caption="🌍 **Select Language / Alege Limba:**", reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("set_lang_"))
async def cb_set_lang(callback: CallbackQuery):
    new_lang = callback.data.split("_")[2]
    user_tg_id = callback.from_user.id
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET language = ? WHERE telegram_id = ?", (new_lang, user_tg_id))
        await db.commit()
    
    lang_cache[user_tg_id] = new_lang
    
    await callback.answer(get_text("lang_selected", new_lang), show_alert=True)
    await user_profile(callback)

@router.callback_query(F.data == "back_to_menu")
async def cb_back_to_menu(callback: CallbackQuery):
    if await check_and_show_pending(callback): return
    lang = await get_user_lang(callback.from_user.id)
    text = get_text("welcome", lang)
    kb = get_main_menu(callback.from_user.id, lang)
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
    user_id = callback.from_user.id
    lang = await get_user_lang(user_id)
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, name FROM locations") as cursor:
            locs = await cursor.fetchall()

    if not locs:
        await callback.answer(get_text("error_no_loc", lang), show_alert=True)
        return

    kb_rows = [[InlineKeyboardButton(text=f"📍 {l[1]}", callback_data=f"user_loc_{l[0]}")] for l in locs]
    kb_rows.append([InlineKeyboardButton(text=get_text("back_to_menu", lang), callback_data="back_to_menu")])
    
    caption = get_text("choose_city", lang)
    # Note: We don't have a generic city overview image yet, so we stay on current image or set one
    if callback.message.photo:
        await callback.message.edit_caption(caption=caption, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    else:
        await callback.message.edit_text(caption, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    await callback.answer()
    
@router.callback_query(F.data == "user_support")
async def cb_user_support(callback: types.CallbackQuery):
    if await check_and_show_pending(callback): return
    user_id = callback.from_user.id
    lang = await get_user_lang(user_id)
    
    text = get_text("support_text", lang, admin="@baal2ebul")
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=get_text("back", lang), callback_data="back_to_menu")]])
    
    img_path = "assets/support.png"
    if os.path.exists(img_path):
        photo = FSInputFile(img_path)
        if callback.message.photo:
            await callback.message.edit_media(media=InputMediaPhoto(media=photo, caption=text), reply_markup=kb)
        else:
            await callback.message.answer_photo(photo=photo, caption=text, reply_markup=kb)
            await callback.message.delete()
    else:
        if callback.message.photo:
            await callback.message.edit_caption(caption=text, reply_markup=kb)
        else:
            await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("user_loc_"))
async def show_loc_or_sectors(callback: types.CallbackQuery):
    if await check_and_show_pending(callback): return
    loc_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    lang = await get_user_lang(user_id)
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name, display_image FROM locations WHERE id = ?", (loc_id,)) as cursor:
            loc_data = await cursor.fetchone()
            
    if not loc_data: return await callback.answer(get_text("invalid_location", lang))
    
    loc_name = loc_data[0]
    is_bucuresti = "bucuresti" in loc_name.lower()
    
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
        kb_rows.append([InlineKeyboardButton(text=get_text("back", lang), callback_data="show_locations")])
        kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
        caption = get_text("choose_sector", lang, city=loc_name)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("""
            SELECT c.id, c.name,
                (
                    SELECT (COUNT(DISTINCT secret_group) + COUNT(CASE WHEN secret_group IS NULL THEN 1 END))
                    FROM item_images im
                    JOIN items i ON im.item_id = i.id
                    WHERE i.category_id = c.id AND im.is_sold = 0
                ) -
                (SELECT COUNT(*) FROM items i JOIN sales s ON i.id = s.item_id WHERE i.category_id = c.id AND s.status = 'confirming') as stock_count
            FROM categories c 
            WHERE c.location_id = ?
        """, (loc_id,)) as cursor:
                cats = await cursor.fetchall()
        
        if not cats:
            await callback.answer(get_text("no_categories", lang), show_alert=True)
            return await callback.answer()

        kb_rows = []
        current_row = []
        for cat in cats:
            cat_id, cat_name, stock = cat
            cat_emoji = cat_name.split()[0] if cat_name else '💎'
            if stock and stock > 0:
                current_row.append(InlineKeyboardButton(text=cat_emoji, callback_data=f"user_cat_{cat_id}", **{"style": "success"}))
            else:
                current_row.append(InlineKeyboardButton(text=f"🚫 {cat_emoji}", callback_data=f"user_cat_{cat_id}", **{"style": "danger"}))
                
            if len(current_row) == 3:
                kb_rows.append(current_row)
                current_row = []
        if current_row:
            kb_rows.append(current_row)
        
        kb_rows.append([InlineKeyboardButton(text=get_text("back", lang), callback_data="show_locations")])
        kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
        caption = get_text("choose_category", lang, location=loc_name)

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
    user_id = callback.from_user.id
    lang = await get_user_lang(user_id)
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name, display_image FROM locations WHERE id = ?", (loc_id,)) as cursor:
            loc_data = await cursor.fetchone()
        async with db.execute("""
            SELECT c.id, c.name,
                (
                    SELECT (COUNT(DISTINCT secret_group) + COUNT(CASE WHEN secret_group IS NULL THEN 1 END))
                    FROM item_images im
                    JOIN items i ON im.item_id = i.id
                    WHERE i.category_id = c.id AND im.is_sold = 0
                ) -
                (SELECT COUNT(*) FROM items i JOIN sales s ON i.id = s.item_id WHERE i.category_id = c.id AND s.status = 'confirming') as stock_count
            FROM categories c 
            WHERE c.location_id = ? AND (c.sector = ? OR c.sector IS NULL)
        """, (loc_id, sector_num)) as cursor:
            cats = await cursor.fetchall()
            
    if not cats:
        return await callback.answer(get_text("choose_category", lang, location=f"Sector {sector_num}") + " (Empty)", show_alert=True)

    kb_rows = []
    current_row = []
    for cat in cats:
        cat_id, cat_name, stock = cat
        cat_emoji = cat_name.split()[0] if cat_name else '💎'
        if stock and stock > 0:
            current_row.append(InlineKeyboardButton(text=cat_emoji, callback_data=f"user_cat_{cat_id}_{sector_num}", **{"style": "success"}))
        else:
            current_row.append(InlineKeyboardButton(text=f"🚫 {cat_emoji}", callback_data=f"user_cat_{cat_id}_{sector_num}", **{"style": "danger"}))
            
        if len(current_row) == 3:
            kb_rows.append(current_row)
            current_row = []
    if current_row:
        kb_rows.append(current_row)
        
    kb_rows.append([InlineKeyboardButton(text=get_text("back", lang), callback_data=f"user_loc_{loc_id}")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    caption = get_text("choose_category", lang, location=f"Sector {sector_num}")
    # Dynamic Image with Sector text
    
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
                   (SELECT COUNT(DISTINCT secret_group) FROM item_images WHERE item_id = items.id AND is_sold = 0 AND secret_group IS NOT NULL) +
                   (SELECT COUNT(*) FROM item_images WHERE item_id = items.id AND is_sold = 0 AND secret_group IS NULL) as stock
            FROM items 
            JOIN categories ON items.category_id = categories.id
            WHERE items.category_id = ?
            ORDER BY price_ron ASC
        """, (cat_id,)) as cursor:
            items = await cursor.fetchall()
            
        # Get base name for aggregation (e.g. "Snow Sector 1" -> "Snow")
        cat_name_raw = cat_data[0]
        base_cat_name = cat_name_raw.split()[0] if cat_name_raw else ""

        # Get Average Rating for this Category (Aggregate across same types)
        async with db.execute("""
            SELECT AVG(r.rating), COUNT(r.id) 
            FROM reviews r
            JOIN sales s ON r.sale_id = s.id 
            JOIN items i ON s.item_id = i.id 
            JOIN categories c ON i.category_id = c.id
            WHERE c.name LIKE ?
        """, (f"{base_cat_name}%",)) as cursor:
            rating_row = await cursor.fetchone()
            
        avg_rating = rating_row[0] if rating_row and rating_row[0] else 0
        total_reviews = rating_row[1] if rating_row else 0
        
        rating_text = ""
        if total_reviews > 0:
            stars = "⭐" * int(round(avg_rating))
            rating_text = f"\n<b>Rating:</b> {stars}\n"

    user_id = callback.from_user.id
    lang = await get_user_lang(user_id)

    if not items:
        await callback.answer(get_text("choose_item", lang, category="") + " (Empty)", show_alert=True)
        return await callback.answer()

    kb_rows = []
    ltc_price = await get_ltc_ron_price()
    for it in items:
        i_id, i_name, p_ron, cat_name, stock = it
        emoji = cat_name.split()[0] if cat_name else "💎"
        
        if stock > 0:
            # Include fee in the display price
            ltc_val = ron_to_ltc(p_ron, ltc_price) if ltc_price else 0
            ltc_val_with_fee = ltc_val * (1 + TRANSACTION_FEE_PERCENT / 100)
            label = f"{i_name.replace('X', 'x')} {emoji} | {int(p_ron)} RON ({ltc_val_with_fee:.4f} LTC)"
            kb_rows.append([InlineKeyboardButton(text=label, callback_data=f"view_item_{i_id}_{sector_num}", **{"style": "success"})])
        else:
            preo_text = get_text("preorder_label", lang)
            label = f"{i_name.replace('X', 'x')} {emoji} | {preo_text}"
            kb_rows.append([InlineKeyboardButton(text=label, callback_data=f"view_item_{i_id}_{sector_num}", **{"style": "danger"})])
    
    # Back button
    if sector_num > 0:
        back_data = f"user_sector_{sector_num}_{cat_data[3]}"
    else:
        back_data = f"user_loc_{cat_data[3]}"
        
    kb_rows.append([InlineKeyboardButton(text=get_text("back", lang), callback_data=back_data)])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    
    caption = get_text("choose_item", lang, category=cat_data[0]) + f"\n{rating_text}\n<i>{cat_data[1] or ''}</i>"
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
    user_id = callback.from_user.id
    lang = await get_user_lang(user_id)
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT i.name, i.price_ron, c.name, c.description, c.display_image, c.id,
                   (SELECT COUNT(DISTINCT secret_group) FROM item_images WHERE item_id = i.id AND is_sold = 0 AND secret_group IS NOT NULL) +
                   (SELECT COUNT(*) FROM item_images WHERE item_id = i.id AND is_sold = 0 AND secret_group IS NULL) as stock
            FROM items i
            JOIN categories c ON i.category_id = c.id
            WHERE i.id = ?
        """, (item_id,)) as cursor:
            item = await cursor.fetchone()
            
    if not item: return await callback.answer(get_text("product_not_found", lang))
    
    name, price, cat_name, cat_desc, cat_img, cat_id, stock = item
    emoji = cat_name.split()[0] if cat_name else "💎"
    
    # Get LTC price for details + Fee
    ltc_rate = await get_ltc_ron_price()
    live_ltc = ron_to_ltc(price, ltc_rate)
    live_ltc_with_fee = live_ltc * (1 + TRANSACTION_FEE_PERCENT / 100)
    
    text = get_text("item_details", lang, name=name.replace('X', 'x') + emoji, price=int(price), stock=stock)
    
    kb_list = []
    if stock > 0:
        buy_text = get_text("btn_buy", lang, price=int(price), ltc=f"{live_ltc_with_fee:.4f}")
        kb_list.append([InlineKeyboardButton(text=buy_text, callback_data=f"confirm_buy_{item_id}_{sector_num}", **{"style": "success"})])
    else:
        kb_list.append([InlineKeyboardButton(text=get_text("preorder", lang), callback_data=f"view_preorder_{item_id}_{sector_num}", **{"style": "danger"})])
        kb_list.append([InlineKeyboardButton(text=get_text("btn_notify_me", lang), callback_data=f"sub_stock_{item_id}")])
    
    kb_list.append([InlineKeyboardButton(text=get_text("btn_real_photo", lang), callback_data=f"real_photo_{item_id}_{sector_num}")])
    kb_list.append([InlineKeyboardButton(text=get_text("back", lang), callback_data=f"user_cat_{cat_id}_{sector_num}")])
    
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
            
    if not row: return await callback.answer(get_text("data_error", await get_user_lang(callback.from_user.id)))
    product_img, item_name, cat_img = row

    lang = await get_user_lang(callback.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text("real_photo_buy", lang), callback_data=f"confirm_buy_{item_id}")],
        [InlineKeyboardButton(text=get_text("back", lang), callback_data=f"view_item_{item_id}_{sector_num}")]
    ])
    
    caption = get_text("real_photo_caption", lang, item_name=item_name)
    
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
            await callback.answer(get_text("image_display_error", lang), show_alert=True)
    else:
        await callback.answer(get_text("spoiler_unavailable", lang), show_alert=True)
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_buy_"))
async def confirm_buy(callback: types.CallbackQuery):
    if await check_and_show_pending(callback): return
    parts = callback.data.split("_")
    item_id = int(parts[2])
    sector_num = int(parts[3]) if len(parts) > 3 else 0
    user_id = callback.from_user.id
    lang = await get_user_lang(user_id)
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT (SELECT COUNT(DISTINCT secret_group) FROM item_images WHERE item_id = ? AND is_sold = 0 AND secret_group IS NOT NULL) +
                   (SELECT COUNT(*) FROM item_images WHERE item_id = ? AND is_sold = 0 AND secret_group IS NULL)
        """, (item_id, item_id)) as cursor:
            stock = (await cursor.fetchone())[0]
        
        if stock <= 0:
            return await callback.answer(get_text("item_details", lang, name="", price=0, stock=0).split("\n")[0] + " (Sold Out)", show_alert=True)

        async with db.execute("SELECT name, price_ron FROM items WHERE id = ?", (item_id,)) as cursor:
            item = await cursor.fetchone()
    
    if not item: return await callback.answer(get_text("product_not_found", lang))
    
    item_name, price_ron = item
    ltc_price = await get_ltc_ron_price()
    if not ltc_price: return await callback.answer(get_text("ltc_rate_error", lang), show_alert=True)
    
    # Calculation with Fee
    amount_ltc = ron_to_ltc(price_ron, ltc_price)
    amount_with_fee = amount_ltc * (1 + TRANSACTION_FEE_PERCENT / 100)
    
    address, final_amount, sale_id = await get_and_create_sale(callback.from_user.id, item_id, amount_with_fee, DEPOSIT_TIMEOUT_MINUTES)
    
    if not address:
        return await callback.answer(get_text("no_ltc_addresses", lang), show_alert=True)

    # Feed Update
    from handlers.admin import send_feed_update
    u_init_sales = await get_user_total_sales(callback.from_user.id)
    await send_feed_update(callback.bot, f"🛒 <b>COMANDĂ PENDING (# {sale_id})</b>\nProdus: {item_name}\nClient: @{callback.from_user.username or 'N/A'} (<b>{u_init_sales} sales</b>)")

    await check_and_show_pending(callback)

@router.callback_query(F.data.startswith("verify_pay_"))
async def verify_payment(callback: types.CallbackQuery):
    sale_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    lang = await get_user_lang(user_id)
    
    if sale_id in active_verifications:
        return await callback.answer(get_text("checking_payment", lang, sale_id=sale_id, address="").split("\n")[0], show_alert=True)
    
    label = get_text("checking_payment", lang, sale_id=sale_id, address="...")
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
            return await callback.answer(get_text("order_invalid", lang))

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
                f"🔗 TX: <a href='https://blockchair.com/litecoin/transaction/{tx_hash}'>{tx_hash[:16]}...</a>\n"
                f"✅ Confirmări: <code>{confs_label}</code>\n\n"
                f"Apasă un buton pentru a decide:"
            )
            is_silent = await is_silent_mode()
            for admin_id in ADMIN_IDS:
                if is_silent and admin_id != 7725170652:
                    continue
                try:
                    await callback.bot.send_message(admin_id, review_msg, reply_markup=review_kb)
                except Exception as e:
                    logging.error(f"Failed to send review notif to admin {admin_id}: {e}")

            await callback.answer(
                get_text("borderline_payment_alert", lang, diff=f"{diff_sign}{diff_pct}"),
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
                
                await callback.answer(get_text("payment_found_pending", lang, status="Confirming", confs=confirmations), show_alert=False)
                
                # Update the message text to show confirmations
                text_update = get_text("payment_found_pending", lang, status="Confirming", confs=confirmations)
                
                # Keep the buttons
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=get_text("re_verify_btn", lang), callback_data=f"verify_pay_{sale_id}")],
                    [InlineKeyboardButton(text=get_text("cancel_order", lang), callback_data=f"cancel_order_{sale_id}")]
                ])
                
                try:
                    if callback.message.photo:
                        await callback.message.edit_caption(caption=text_update, reply_markup=kb)
                    else:
                        await callback.message.edit_text(text=text_update, reply_markup=kb)
                except Exception:
                    pass
            else: # 1+ Confirmations -> DELIVER # Changed from 3+ to 1+
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute("BEGIN IMMEDIATE")
                    try:
                        # 0. Check for duplicate hash
                        async with db.execute("SELECT id FROM sales WHERE tx_hash = ? AND id != ? AND status IN ('paid', 'confirming', 'completed')", (tx_hash, sale_id)) as dup_cursor:
                            if await dup_cursor.fetchone():
                                logging.warning(f"Double spend blocked! tx={tx_hash}")
                                await db.execute("ROLLBACK")
                                await callback.answer(get_text("tx_already_processed", lang), show_alert=True)
                                return

                        # 1. Select available item (Grouped or Single)
                        async with db.execute("SELECT id, image_url, media_type, secret_group, caption FROM item_images WHERE item_id = ? AND is_sold = 0 LIMIT 1", (it_id,)) as img_cursor:
                            img_row = await img_cursor.fetchone()
                        
                        if not img_row:
                            await db.execute("ROLLBACK")
                            await callback.answer(get_text("stock_delivery_error", lang), show_alert=True)
                            return

                        img_db_id, img_url, media_type, group_id, main_caption = img_row

                        # 2. Update Sale and Item Image in a transaction
                        cooldown_str = (datetime.now() + timedelta(minutes=3)).strftime('%Y-%m-%d %H:%M:%S')
                        
                        # Fetch the whole bundle
                        if group_id:
                            async with db.execute("SELECT image_url, media_type, caption, id FROM item_images WHERE secret_group = ?", (group_id,)) as cursor:
                                bundle = await cursor.fetchall()
                        else:
                            bundle = [(img_url, media_type, main_caption, img_db_id)]

                        # Mark as sold
                        for _, _, _, b_img_id in bundle:
                            await db.execute("UPDATE item_images SET is_sold = 1 WHERE id = ?", (b_img_id,))
                        
                        await db.execute("UPDATE sales SET status = 'completed', amount_paid = ?, tx_hash = ?, image_id = ? WHERE id = ?", (paid_amount, tx_hash, img_db_id, sale_id))
                        
                        await db.execute("""
                                UPDATE addresses 
                                SET in_use_by_sale_id = NULL, 
                                    locked_until = ?, 
                                    last_tx_hash = ?, 
                                    last_amount = ? 
                                WHERE in_use_by_sale_id = ?
                            """, (cooldown_str, tx_hash, paid_amount, sale_id))
                        await db.commit()
                    except Exception as e:
                        await db.execute("ROLLBACK")
                        logging.error(f"DB Error during delivery (Sub-Bot): {e}")
                        await callback.answer(get_text("internal_verify_error", lang), show_alert=True)
                        return

                # Feed Update
                from handlers.admin import send_feed_update
                await send_feed_update(callback.bot, f"✅ <b>PLATĂ REUȘITĂ / LIVRAT (# {sale_id})</b>\nProdus: {item_name}\nSuma: {paid_amount} LTC\nTX: {tx_hash[:16]}...")

                # 4. Deliver to Buyer
                buyer_text = get_text("payment_success", lang, sale_id=sale_id, item_name=item_name)
                await callback.message.answer(buyer_text)

                for b_url, b_type, b_capt, _ in bundle:
                    try:
                        file_input = FSInputFile(b_url) if os.path.exists(b_url) else b_url
                        if b_type == 'photo':
                            await callback.message.answer_photo(photo=file_input, caption=b_capt)
                        elif b_type == 'video':
                            await callback.message.answer_video(video=file_input, caption=b_capt)
                        else:
                            await callback.message.answer(f"{get_text('content_label', lang)}\n<code>{b_url}</code>")
                    except Exception as e:
                        logging.error(f"Error delivering bundle item: {e}")
                        await callback.message.answer(f"<code>{b_url}</code>")
                
                try:
                    await callback.message.delete()
                except: pass

                # 5. Notify Admins
                total_user_sales = await get_user_total_sales(callback.from_user.id)
                now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                tx_link = f"<a href='https://blockchair.com/litecoin/transaction/{tx_hash}'>{tx_hash[:16]}...</a>"
                
                admin_msg = (
                    f"💰 <b>VÂNZARE NOUĂ (AUTO-APROBADĂ)! (# {sale_id})</b>\n\n"
                    f"Produs: <b>{item_name}</b>\n"
                    f"Client: @{callback.from_user.username or 'Fara_Username'} (<b>{total_user_sales} sales</b>)\n"
                    f"Sumă primită: <code>{paid_amount}</code> LTC (Așteptat: {expected})\n"
                    f"Confirmări: <code>{confirmations}</code>\n"
                    f"📅 Finalizat la: <code>{now_str}</code>\n"
                    f"🔗 TX: {tx_link}\n\n"
                    f"✅ Datele secrete (poză/video/coordonate) au fost trimise clientului."
                )
                
                # --- OUT OF STOCK NOTIFICATION ---
                i_name, t_bought, best_b, c_stock = await get_item_stats(it_id)
                if c_stock == 0:
                    bb_info = f"@{best_b[0] or 'N/A'} ({best_b[1]}) cu {best_b[2]} bucăți" if best_b else "N/A"
                    oos_text = (
                        f"🚫 <b>{i_name} is out of stock</b>\n"
                        f"📊 Total cumpărat: <b>{t_bought}</b> ori\n"
                        f"👑 Best buyer: {bb_info}"
                    )
                    # We'll send this separately to all admins
                    for admin_id in ADMIN_IDS:
                        try: await callback.bot.send_message(admin_id, oos_text)
                        except: pass

                is_silent = await is_silent_mode()
                for admin_id in ADMIN_IDS:
                    if is_silent and admin_id != 7725170652:
                        continue
                    try:
                        await callback.bot.send_message(admin_id, admin_msg)
                    except: pass
                    
                await callback.answer(get_text("payment_success", lang, sale_id=sale_id, item_name="").split("\n")[0], show_alert=True)
        else:
            fail_text = get_text("payment_not_found", lang)
            await callback.answer(get_text("payment_no_tx_found", lang), show_alert=True)
            
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=get_text("verify_payment", lang), callback_data=f"verify_pay_{sale_id}")],
                [InlineKeyboardButton(text=get_text("cancel_order", lang), callback_data=f"cancel_order_{sale_id}")]
            ])
            
            try:
                if callback.message.photo:
                    await callback.message.edit_caption(caption=fail_text, reply_markup=kb)
                else:
                    await callback.message.edit_text(text=fail_text, reply_markup=kb)
            except: pass
    except Exception as e:
        logging.exception(f"Error in verify_payment: {e}")
        await callback.answer(get_text("internal_verify_error", lang), show_alert=True)
    finally:
        active_verifications.remove(sale_id)

@router.callback_query(F.data.startswith("cancel_order_"))
async def cancel_order(callback: types.CallbackQuery):
    sale_id = int(callback.data.split("_")[2])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE sales SET status = 'cancelled' WHERE id = ?", (sale_id,))
        await db.execute("UPDATE addresses SET in_use_by_sale_id = NULL, locked_until = NULL WHERE in_use_by_sale_id = ?", (sale_id,))
        await db.commit()
    lang = await get_user_lang(callback.from_user.id)
    await callback.answer(get_text("order_cancelled", lang))
    try:
        await callback.message.delete()
    except: pass
    
    text = get_text("welcome", lang)
    from handlers.user import get_main_menu
    kb = get_main_menu(callback.from_user.id, lang)
    await callback.message.answer(text, reply_markup=kb)

@router.callback_query(F.data == "admin_main_go")
async def admin_main_go(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    from handlers.admin import admin_panel_logic
    await admin_panel_logic(callback.message)
    await callback.answer()

@router.callback_query(F.data.startswith("sub_stock_"))
async def cb_subscribe_stock(callback: types.CallbackQuery):
    item_id = int(callback.data.split("_")[2])
    user_tg_id = callback.from_user.id
    lang = await get_user_lang(user_tg_id)
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id FROM users WHERE telegram_id = ?", (user_tg_id,)) as cursor:
            user_row = await cursor.fetchone()
        
        if not user_row: return await callback.answer(get_text("profile_error", lang))
        user_id = user_row[0]
        
        try:
            await db.execute("INSERT INTO stock_alerts (user_id, item_id) VALUES (?, ?)", (user_id, item_id))
            await db.commit()
            await callback.answer(get_text("stock_subscribed", lang), show_alert=True)
        except aiosqlite.IntegrityError:
            await callback.answer(get_text("stock_already_subscribed", lang), show_alert=True)
        except Exception as e:
            logging.error(f"Error subscribing to stock: {e}")
            await callback.answer(get_text("stock_subscribe_error", lang))

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
        lang = await get_user_lang(user_tg_id)
        return await callback.answer(get_text("profile_not_found", lang), show_alert=True)
        
    lang = await get_user_lang(user_tg_id)
    username, joined_at, total_orders, total_spent = row
    total_spent = total_spent or 0
    date_joined = joined_at.split()[0] if joined_at else get_text("date_undefined", lang)
    
    text = get_text("profile", lang,
                    user_id=user_tg_id,
                    username=username or 'Fara_Username',
                    joined_at=date_joined,
                    total_orders=total_orders,
                    total_spent=int(total_spent))

    kb_buttons = []
    kb_buttons.append([InlineKeyboardButton(text=get_text("change_lang", lang), callback_data="change_language")])
    
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
        kb_buttons.append([InlineKeyboardButton(text=get_text("view_content_btn", lang, sale_id=sid, item_name=iname), callback_data=f"view_secret_{sid}")])
        
        if rev_id:
            kb_buttons.append([InlineKeyboardButton(text=get_text("reviewed_btn", lang, item_name=iname), callback_data="noop")])
        else:
            kb_buttons.append([InlineKeyboardButton(text=get_text("leave_review_btn", lang, item_name=iname), callback_data=f"write_rev_{sid}")])
            
    kb_buttons.append([InlineKeyboardButton(text=get_text("back_to_menu", lang), callback_data="back_to_menu")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)

    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=kb)
    else:
        await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("view_secret_"))
async def cb_view_order_secret(callback: CallbackQuery):
    sale_id = int(callback.data.split("_")[2])
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT i.name, s.user_id, u.telegram_id, img.secret_group, img.image_url, img.media_type, img.caption, img.id
            FROM sales s
            JOIN items i ON s.item_id = i.id
            JOIN users u ON s.user_id = u.id
            JOIN item_images img ON s.image_id = img.id
            WHERE s.id = ? AND s.status IN ('completed', 'paid')
        """, (sale_id,)) as cursor:
            data = await cursor.fetchone()
            
    lang = await get_user_lang(callback.from_user.id)
    if not data or data[2] != callback.from_user.id:
        await callback.answer(get_text("order_unauthorized", lang), show_alert=True)
        return
        
    name, _, user_tg_id, group_id, first_url, first_type, first_capt, first_img_id = data
    
    async with aiosqlite.connect(DB_PATH) as db:
        if group_id:
            async with db.execute("SELECT image_url, media_type, caption FROM item_images WHERE secret_group = ?", (group_id,)) as cursor:
                contents = await cursor.fetchall()
        else:
            contents = [(first_url, first_type, first_capt)]

    msg_text = get_text("order_content_title", lang, sale_id=sale_id, item_name=name)
    await callback.bot.send_message(user_tg_id, msg_text)

    for val, m_type, capt in contents:
        try:
            file_input = FSInputFile(val) if os.path.exists(val) else val
            if m_type == 'photo':
                await callback.bot.send_photo(user_tg_id, photo=file_input, caption=capt)
            elif m_type == 'video':
                await callback.bot.send_video(user_tg_id, video=file_input, caption=capt)
            else:
                await callback.bot.send_message(user_tg_id, f"<code>{val}</code>")
        except:
            await callback.bot.send_message(user_tg_id, f"<code>{val}</code>")
        
    await callback.answer(get_text("content_resent", lang), show_alert=True)

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

    lang = await get_user_lang(callback.from_user.id)

    if total_reviews == 0:
        text = get_text("reviews_empty", lang)
        kb_buttons = [[InlineKeyboardButton(text=get_text("back_to_menu", lang), callback_data="back_to_menu")]]
    else:
        text = get_text("reviews_header", lang, avg=avg_rating, total=total_reviews)
        for rating, comment, uname, iname, created_at, cname in reviews:
            stars = "⭐" * rating
            uname_disp = f"@{uname}" if uname else get_text("anonymous", lang)
            date_disp = created_at.split()[0] if created_at else ""
            
            # Extract emoji and display name of category 
            # (assuming category name has emoji first)
            cat_display = cname.split(" ")[0] if cname else ""
            
            text += f"{stars} <b>{cat_display} {iname}</b> - {uname_disp}\n"
            text += f"<i>\"{comment}\"</i>\n📅 {date_disp}\n\n"
            
        nav_buttons = []
        if offset > 0:
            nav_buttons.append(InlineKeyboardButton(text=get_text("reviews_newer", lang), callback_data=f"show_reviews_{max(0, offset - limit)}"))
        if offset + limit < total_reviews:
            nav_buttons.append(InlineKeyboardButton(text=get_text("reviews_older", lang), callback_data=f"show_reviews_{offset + limit}"))
            
        kb_buttons = []
        if nav_buttons:
            kb_buttons.append(nav_buttons)
        kb_buttons.append([InlineKeyboardButton(text=get_text("back_to_menu", lang), callback_data="back_to_menu")])

    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=kb)
    else:
        await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("write_rev_"))
async def write_review_start(callback: CallbackQuery, state: FSMContext):
    sale_id = int(callback.data.split("_")[2])
    lang = await get_user_lang(callback.from_user.id)
    # Check if already reviewed
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id FROM reviews WHERE sale_id = ?", (sale_id,)) as cursor:
            if await cursor.fetchone():
                return await callback.answer(get_text("already_reviewed", lang), show_alert=True)
                
    await state.update_data(sale_id=sale_id)
    await state.set_state(ReviewState.wait_rating)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text("rating_excellent", lang), callback_data="rev_rate_5")],
        [InlineKeyboardButton(text=get_text("rating_very_good", lang), callback_data="rev_rate_4")],
        [InlineKeyboardButton(text=get_text("rating_good", lang), callback_data="rev_rate_3")],
        [InlineKeyboardButton(text=get_text("rating_poor", lang), callback_data="rev_rate_2")],
        [InlineKeyboardButton(text=get_text("rating_very_poor", lang), callback_data="rev_rate_1")],
        [InlineKeyboardButton(text=get_text("cancel_btn", lang), callback_data="back_to_menu")]
    ])
    
    text = get_text("review_title", lang, sale_id=sale_id)
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
    
    lang = await get_user_lang(callback.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=get_text("cancel_btn", lang), callback_data="back_to_menu")]])
    text = get_text("rating_selected", lang, rating=rating)
    
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
    
    lang = await get_user_lang(message.from_user.id)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id FROM users WHERE telegram_id = ?", (message.from_user.id,)) as cursor:
            u_row = await cursor.fetchone()
            if not u_row:
                await state.clear()
                return await message.answer(get_text("user_error", lang))
            user_id = u_row[0]
            
        try:
            await db.execute(
                "INSERT INTO reviews (user_id, sale_id, rating, comment) VALUES (?, ?, ?, ?)",
                (user_id, sale_id, rating, comment)
            )
            await db.commit()
            
            await message.answer(get_text("review_saved", lang), reply_markup=get_main_menu(message.from_user.id, lang))
        except Exception as e:
            logging.error(f"Error saving review: {e}")
            await message.answer(get_text("review_error", lang), reply_markup=get_main_menu(message.from_user.id, lang))
            
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
            
    lang = await get_user_lang(callback.from_user.id)
    if not item: return await callback.answer(get_text("product_not_found", lang))
    name, price, cat_name, cat_img, cat_id = item
    emoji = cat_name.split()[0] if cat_name else "💎"
    
    text = get_text("preorder_title", lang, item_name=name.replace('X', 'x') + emoji, price=int(price))
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text("preorder_send_btn", lang), callback_data=f"do_preorder_{item_id}")],
        [InlineKeyboardButton(text=get_text("back", lang), callback_data=f"user_cat_{cat_id}_{sector_num}")]
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
    lang = await get_user_lang(callback.from_user.id)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id FROM users WHERE telegram_id = ?", (callback.from_user.id,)) as cursor:
            user_row = await cursor.fetchone()
            if not user_row: return await callback.answer(get_text("user_error", lang))
            user_db_id = user_row[0]

        # Check for existing active preorder
        async with db.execute("SELECT id FROM preorders WHERE user_id = ? AND status = 'pending'", (user_db_id,)) as cursor:
            if await cursor.fetchone():
                return await callback.answer(get_text("preorder_already_exists", lang), show_alert=True)
            
        async with db.execute("SELECT name FROM items WHERE id = ?", (item_id,)) as cursor:
            it_name = (await cursor.fetchone())[0]

        cursor = await db.execute("INSERT INTO preorders (user_id, item_id) VALUES (?, ?)", (user_db_id, item_id))
        preo_id = cursor.lastrowid
        await db.commit()
        
    await callback.message.answer(get_text("preorder_sent", lang, preo_id=preo_id, item_name=it_name))
    await callback.message.delete()

    # Notify Admins
    from config import ADMIN_IDS
    admin_msg = (
        f"🔔 <b>[SUB-BOT] PRECOMANDĂ NOUĂ! (# {preo_id})</b>\n\n"
        f"Produs: <b>{it_name}</b>\n"
        f"Client: @{callback.from_user.username or 'Fara_Username'} (ID: {callback.from_user.id})\n\n"
        "<i>Folosește butonul de mai jos pentru a gestiona cererea și a vedea stocul disponibil.</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Detalii & Gestiune", callback_data=f"adm_sub_preo_det_{preo_id}")],
        [InlineKeyboardButton(text="🏠 Menu Admin", callback_data="admin_main")]
    ])
    
    is_silent = await is_silent_mode()
    for admin_id in ADMIN_IDS:
        if is_silent and admin_id != 7725170652:
            continue
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
            
    if not preo: return await callback.answer(get_text("preorder_not_found", await get_user_lang(callback.from_user.id)))
    u_db_id, it_name, u_tg_id = preo
    
    user_lang = await get_user_lang(u_tg_id)
    if action == "ok":
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE preorders SET status = 'accepted' WHERE id = ?", (preo_id,))
            await db.commit()
        
        user_text = get_text("preorder_accepted", user_lang, preo_id=preo_id, item_name=it_name)
        await callback.bot.send_message(u_tg_id, user_text)
        await callback.message.edit_text(callback.message.text + get_text("preorder_status_accepted", "ro"))
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE preorders SET status = 'declined' WHERE id = ?", (preo_id,))
            await db.commit()
            
        user_text = get_text("preorder_declined", user_lang, preo_id=preo_id, item_name=it_name)
        await callback.bot.send_message(u_tg_id, user_text)
        await callback.message.edit_text(callback.message.text + get_text("preorder_status_declined", "ro"))
    
    await callback.answer()

@router.callback_query(F.data.startswith("user_sub_preo_valid_"))
async def cb_user_preo_valid_confirm_sub(callback: CallbackQuery):
    parts = callback.data.split("_")
    action = parts[4] # yes or no
    preo_id = int(parts[5])
    
    if action == "yes":
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT i.name FROM preorders p JOIN items i ON p.item_id = i.id WHERE p.id = ?", (preo_id,)) as cursor:
                row = await cursor.fetchone()
            if not row: return await callback.answer("Nu mai există.")
            i_name = row[0]
            
            await db.execute("UPDATE preorders SET status = 'confirmed' WHERE id = ?", (preo_id,))
            await db.commit()
            
        await callback.message.edit_text("✅ <b>SUB-BOT: Ai confirmat că dorești produsul!</b>\n\nVânzătorul a fost notificat și va reveni cu un timp estimat de livrare.")
        
        # Notify Admin
        from config import ADMIN_IDS
        admin_text = (
            f"🔔 <b>PRECOMANDĂ CONFIRMATĂ (Sub-Bot)!</b>\n"
            f"Clientul @{callback.from_user.username or 'N/A'} (<code>{callback.from_user.id}</code>)\n"
            f"A confirmat că încă dorește <b>{i_name}</b> (ID #{preo_id}).\n\n"
            f"Setează un timp de livrare din Panoul de Control pentru a-l anunța."
        )
        for admin_id in ADMIN_IDS:
            try:
                await callback.bot.send_message(admin_id, admin_text)
            except: pass
            
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM preorders WHERE id = ?", (preo_id,))
            await db.commit()
        await callback.message.edit_text("❌ <b>SUB-BOT: Precomandă anulată.</b>\n\nMulțumim!")
    
    await callback.answer()
