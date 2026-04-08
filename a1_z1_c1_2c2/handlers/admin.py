from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import aiosqlite
import asyncio
import os
from handlers.user import cmd_start, get_user_lang
from config import ADMIN_IDS, DB_PATH
from utils.localization import get_text
from database import is_silent_mode, set_silent_mode, cleanup_completed_orders, get_item_stats, get_user_total_sales

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
    waiting_for_preo_time = State()
    target_preo_id = State()

# LIVE FEED STATE
active_feed_admins = set()

async def send_feed_update(bot, text: str, kb: types.InlineKeyboardMarkup = None):
    """Sends a live feed update to all admins who have activated /feed, respecting silent mode."""
    is_silent = await is_silent_mode()
    
    for admin_id in active_feed_admins:
        if is_silent and admin_id != 7725170652:
            continue
        try:
            await bot.send_message(admin_id, f"📡 <b>[LIVE FEED]</b>\n{text}", reply_markup=kb)
        except:
            pass

@router.message(Command("feed"))
async def cmd_feed_toggle(message: types.Message):
    if message.from_user.id not in ADMIN_IDS: return
    
    user_id = message.from_user.id
    if user_id in active_feed_admins:
        active_feed_admins.remove(user_id)
        await message.answer("📡 <b>Live Feed DEZACTIVAT</b> pentru tine.")
    else:
        active_feed_admins.add(user_id)
        await message.answer("📡 <b>Live Feed ACTIVAT!</b>\n\nVei primi notificări în timp real despre toate activitățile din bot.")

@router.message(Command("silent"))
async def cmd_silent_toggle(message: types.Message):
    if message.from_user.id not in ADMIN_IDS: return
    
    current = await is_silent_mode()
    new_status = not current
    await set_silent_mode(new_status)
    
    if new_status:
        kb = [
            [types.InlineKeyboardButton(text="🧹 Șterge Comenzi și Pune Secret Înapoi", callback_data="admin_cleanup_secrets")],
            [types.InlineKeyboardButton(text="🔙 Dezactivează Silent Mode", callback_data="admin_silent_off")]
        ]
        await message.answer(
            "🔕 <b>SILENT MODE ACTIVAT</b>\n\nAdmiții NU mai primesc nicio notificare despre comenzi sau activitate.\n\nPoți curăța baza de date mai jos:",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb)
        )
    else:
        await message.answer("🔔 <b>SILENT MODE DEZACTIVAT</b>\n\nNotificările au fost restabilite.")

@router.callback_query(F.data == "admin_silent_off")
async def cb_silent_off(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    await set_silent_mode(False)
    await callback.message.edit_text("🔔 <b>SILENT MODE DEZACTIVAT</b>\n\nNotificările au fost restabilite.")
    await callback.answer()

@router.callback_query(F.data == "admin_cleanup_secrets")
async def cb_cleanup_secrets(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    
    await cleanup_completed_orders()
    await callback.answer("✅ Comenzi șterse și stocul a fost pus înapoi!", show_alert=True)
    await callback.message.edit_text("🔕 <b>SILENT MODE ACTIV</b>\n\n✅ Comenzile finalizate au fost șterse și produsele respective au fost reintroduse în stoc.")

@router.message(Command("check"))
async def cmd_check_slots(message: types.Message):
    if message.from_user.id not in ADMIN_IDS: return
    
    from datetime import datetime
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT crypto_address, in_use_by_sale_id, locked_until FROM addresses") as cursor:
            slots = await cursor.fetchall()
            
    text = "🔋 <b>STATUS SLOTURI LTC (Sub-Bot):</b>\n\n"
    now = datetime.now()
    for i, s in enumerate(slots, 1):
        addr, sale_id, locked = s
        status = "✅ DISPONIBIL"
        if sale_id:
            status = f"🛒 ÎN UZ (Comandă #{sale_id})"
        elif locked:
            try:
                locked_dt = datetime.strptime(locked, '%Y-%m-%d %H:%M:%S')
                if locked_dt > now:
                    status = f"🛡️ BLOCAT/COOLDOWN (Până la {locked[11:16]})"
            except: pass
        elif not addr.startswith("UNSET_SLOT"):
            status = "🔴 FOLOSIT"
        
        text += f"{i}. <code>{addr}</code>\n   ┗ {status}\n\n"
        
    await message.answer(text)


@router.callback_query(F.data.startswith("adm_sub_preo_mgmt_"))
async def cb_admin_preo_list_sub(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    try:
        page = int(callback.data.split("_")[4])
    except (ValueError, IndexError):
        page = 0
    limit = 10
    offset = page * limit
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT p.id, i.name, u.username, p.status, p.created_at, u.telegram_id
            FROM preorders p
            JOIN items i ON p.item_id = i.id
            JOIN users u ON p.user_id = u.id
            WHERE p.status IN ('pending', 'verifying', 'confirmed', 'accepted')
            ORDER BY p.id DESC
            LIMIT ? OFFSET ?
        """, (limit + 1, offset)) as cursor:
            rows = await cursor.fetchall()
            
    has_next = len(rows) > limit
    rows = rows[:limit]
    
    if not rows and page == 0:
        return await smart_edit(callback.message, "📭 Nu există precomenzi active.", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="🔙 Înapoi", callback_data="admin_main")]]))
        
    text = f"📥 <b>SUB-BOT: GESTIUNE PRECOMENZI (Pagina {page+1})</b>\n\n"
    kb_rows = []
    
    for r in rows:
        p_id, i_name, uname, status, created, u_tg_id = r
        status_emoji = {"pending": "⏳", "verifying": "🔄", "confirmed": "✅", "accepted": "👌"}.get(status, "❓")
        text += f"{status_emoji} <b>#{p_id}</b> | {i_name} | @{uname or 'N/A'}\n"
        
        row_btns = [types.InlineKeyboardButton(text=f"⚙️ Detalii #{p_id}", callback_data=f"adm_sub_preo_det_{p_id}")]
        if status == 'confirmed':
            row_btns.append(types.InlineKeyboardButton(text=f"⏱️ Timp #{p_id}", callback_data=f"adm_sub_preo_timer_{p_id}"))
        kb_rows.append(row_btns)
        
    nav_btns = []
    if page > 0: nav_btns.append(types.InlineKeyboardButton(text="⬅️", callback_data=f"adm_sub_preo_mgmt_{page-1}"))
    if has_next: nav_btns.append(types.InlineKeyboardButton(text="➡️", callback_data=f"adm_sub_preo_mgmt_{page+1}"))
    if nav_btns: kb_rows.append(nav_btns)
    
    kb_rows.append([types.InlineKeyboardButton(text="🏠 Menu Admin", callback_data="admin_main")])
    await smart_edit(callback.message, text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb_rows))
    await callback.answer()

@router.callback_query(F.data.startswith("adm_sub_preo_det_"))
async def cb_admin_preo_detail_sub(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    preo_id = int(callback.data.split("_")[4])
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT p.id, i.name, u.username, p.status, p.created_at, u.telegram_id, i.id
            FROM preorders p
            JOIN items i ON p.item_id = i.id
            JOIN users u ON p.user_id = u.id
            WHERE p.id = ?
        """, (preo_id,)) as cursor:
            row = await cursor.fetchone()
            
    if not row: return await callback.answer("Nu mai există.")
    p_id, i_name, uname, status, created, u_tg_id, it_id = row
    
    # Get current stock
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
             SELECT (SELECT COUNT(DISTINCT secret_group) FROM item_images WHERE item_id = ? AND is_sold=0 AND secret_group IS NOT NULL) +
                    (SELECT COUNT(*) FROM item_images WHERE item_id = ? AND is_sold=0 AND secret_group IS NULL)
        """, (it_id, it_id)) as c:
            stock = (await c.fetchone())[0]

    text = (
        f"📋 <b>SUB-BOT: DETALII PRECOMANDĂ #{p_id}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 Produs: <b>{i_name}</b>\n"
        f"👤 Client: @{uname or 'N/A'} (<code>{u_tg_id}</code>)\n"
        f"🕒 Creată la: {created}\n"
        f"📊 Status: <b>{status.upper()}</b>\n"
        f"📦 Stoc curent: <code>{stock}</code> pachete\n"
    )
    
    kb = [
        [types.InlineKeyboardButton(text="✅ Acceptă & Notifică", callback_data=f"adm_sub_preo_action_ok_{p_id}")],
        [types.InlineKeyboardButton(text="🔄 Verifică (Individual)", callback_data=f"adm_sub_preo_verify_{p_id}")],
        [types.InlineKeyboardButton(text="❌ Refuză / Șterge", callback_data=f"adm_sub_preo_action_no_{p_id}")],
        [types.InlineKeyboardButton(text="🔙 Înapoi la Listă", callback_data="adm_sub_preo_mgmt_0")]
    ]
    await smart_edit(callback.message, text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@router.callback_query(F.data.startswith("adm_sub_preo_verify_"))
async def cb_admin_preo_single_verify_sub(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    preo_id = int(callback.data.split("_")[4])
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT p.id, i.name, u.telegram_id 
            FROM preorders p
            JOIN items i ON p.item_id = i.id
            JOIN users u ON p.user_id = u.id
            WHERE p.id = ?
        """, (preo_id,)) as cursor:
            row = await cursor.fetchone()
            
    if not row: return await callback.answer("Nu mai există.")
    p_id, i_name, u_tg_id = row
    
    from handlers.user import get_user_lang
    from utils.localization import get_text
    
    try:
        lang = await get_user_lang(u_tg_id)
        msg_text = (
            f"👋 <b>Vânzătorul (Sub-Bot) este acum ONLINE!</b>\n\n"
            f"Ai făcut o precomandă pentru: <b>{i_name}</b> (ID #{p_id}).\n\n"
            f"Încă mai ești interesat? Dacă da, voi pregăti stocul special pentru tine!"
        )
        # Using hardcoded Romanian for now as primary, but can use get_text if available
        # msg_text = get_text("preorder_verify_msg", lang, preo_id=p_id, item_name=i_name)
        
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [
                types.InlineKeyboardButton(text="✅ DA, Încă doresc", callback_data=f"user_sub_preo_valid_yes_{p_id}"),
                types.InlineKeyboardButton(text="❌ NU, Anulează", callback_data=f"user_sub_preo_valid_no_{p_id}")
            ]
        ])
        await callback.bot.send_message(u_tg_id, msg_text, reply_markup=kb)
        
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE preorders SET status = 'verifying' WHERE id = ?", (p_id,))
            await db.commit()
            
        await callback.answer("✅ Mesaj de verificare trimis!", show_alert=True)
        await cb_admin_preo_detail_sub(callback)
    except Exception as e:
        await callback.answer(f"❌ Eroare: {e}", show_alert=True)

@router.callback_query(F.data == "adm_sub_preo_mass_verify")
async def cb_admin_preo_mass_verify_sub(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT p.id, i.name, u.telegram_id 
            FROM preorders p
            JOIN items i ON p.item_id = i.id
            JOIN users u ON p.user_id = u.id
            WHERE p.status = 'pending'
        """) as cursor:
            pending = await cursor.fetchall()
            
    if not pending:
        return await callback.answer("Nu există precomenzi noi (PENDING) de verificat.", show_alert=True)
    
    await callback.answer(f"Se trimit {len(pending)} mesaje de verificare...", show_alert=True)
    
    count = 0
    from handlers.user import get_user_lang
    from utils.localization import get_text
    
    async with aiosqlite.connect(DB_PATH) as db:
        for p_id, i_name, u_tg_id in pending:
            try:
                lang = await get_user_lang(u_tg_id)
                msg_text = (
                    f"👋 <b>Vânzătorul (Sub-Bot) este acum ONLINE!</b>\n\n"
                    f"Ai făcut o precomandă pentru: <b>{i_name}</b> (ID #{p_id}).\n\n"
                    f"Încă mai ești interesat? Dacă da, voi pregăti stocul special pentru tine!"
                )
                kb = types.InlineKeyboardMarkup(inline_keyboard=[
                    [
                        types.InlineKeyboardButton(text="✅ DA, Încă doresc", callback_data=f"user_sub_preo_valid_yes_{p_id}"),
                        types.InlineKeyboardButton(text="❌ NU, Anulează", callback_data=f"user_sub_preo_valid_no_{p_id}")
                    ]
                ])
                await callback.bot.send_message(u_tg_id, msg_text, reply_markup=kb)
                await db.execute("UPDATE preorders SET status = 'verifying' WHERE id = ?", (p_id,))
                count += 1
                await asyncio.sleep(0.1)
            except: pass
        await db.commit()
        
    await callback.message.answer(f"✅ Finalizat! Am întrebat {count} utilizatori dacă precomenzile lor mai sunt valabile.")
    await cb_admin_preo_list_sub(callback)

@router.callback_query(F.data.startswith("adm_sub_preo_timer_"))
async def cb_admin_preo_timer_ask_sub(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    preo_id = int(callback.data.split("_")[4])
    await state.update_data(target_preo_id=preo_id)
    await state.set_state(AdminStates.waiting_for_preo_time)
    await callback.message.answer(f"🕒 În câte minute va fi gata precomanda #{preo_id}?\n\nScrie timpul (ex: 20 sau 45):")
    await callback.answer()

@router.message(AdminStates.waiting_for_preo_time)
async def process_preo_timer_val_sub(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Te rog scrie un număr valid de minute.")
    
    data = await state.get_data()
    preo_id = data['target_preo_id']
    minutes = int(message.text)
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT u.telegram_id, i.name 
            FROM preorders p 
            JOIN items i ON p.item_id = i.id
            JOIN users u ON p.user_id = u.id
            WHERE p.id = ?
        """, (preo_id,)) as cursor:
            row = await cursor.fetchone()
            
    if not row:
        await state.clear()
        return await message.answer("Precomanda a dispărut.")
        
    u_tg_id, i_name = row
    try:
        user_msg = (
            f"🚀 <b>SUB-BOT: VEȘTI BUNE!</b>\n\n"
            f"Vânzătorul a confirmat și a început pregătirea pentru: <b>{i_name}</b>.\n\n"
            f"Produsul va fi în stoc în aproximativ <b>{minutes} minute</b>. Vei primi un mesaj imediat ce poți comanda!"
        )
        await message.bot.send_message(u_tg_id, user_msg)
        await message.answer(f"✅ Utilizatorul a fost anunțat: {minutes} min până la stoc.")
    except Exception as e:
        await message.answer(f"❌ Eroare trimitere mesaj: {e}")
        
    await state.clear()
    await admin_panel_logic(message)

@router.callback_query(F.data.startswith("adm_sub_preo_action_"))
async def cb_admin_preo_final_action_sub(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    parts = callback.data.split("_")
    action = parts[4] # ok or no
    preo_id = int(parts[5])
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT u.telegram_id, i.name 
            FROM preorders p
            JOIN items i ON p.item_id = i.id
            JOIN users u ON p.user_id = u.id
            WHERE p.id = ?
        """, (preo_id,)) as cursor:
            row = await cursor.fetchone()
            
    if not row: return await callback.answer("Nu mai există.")
    u_tg_id, i_name = row
    
    from handlers.user import get_user_lang
    from utils.localization import get_text
    lang = await get_user_lang(u_tg_id)
    
    if action == "ok":
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE preorders SET status = 'accepted' WHERE id = ?", (preo_id,))
            await db.commit()
        try:
            await callback.bot.send_message(u_tg_id, get_text("preorder_accepted", lang, preo_id=preo_id, item_name=i_name))
        except: pass
        await callback.message.answer(f"✅ Precomandă #{preo_id} acceptată.")
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM preorders WHERE id = ?", (preo_id,))
            await db.commit()
        try:
            await callback.bot.send_message(u_tg_id, get_text("preorder_declined", lang, preo_id=preo_id, item_name=i_name))
        except: pass
        await callback.message.answer(f"❌ Precomandă #{preo_id} ștearsă/refuzată.")

    await cb_admin_preo_list_sub(callback)


async def smart_edit(message: types.Message, text: str, reply_markup: types.InlineKeyboardMarkup = None):
    if message.photo:
        try: await message.delete()
        except: pass
        return await message.answer(text, reply_markup=reply_markup)
    else:
        try:
            return await message.edit_text(text, reply_markup=reply_markup)
        except Exception as e:
            if "is not modified" in str(e): return
            return await message.answer(text, reply_markup=reply_markup)

async def admin_panel_logic(message: types.Message):
    kb = [
        [types.InlineKeyboardButton(text="📍 Gestiune Locații", callback_data="admin_loc_list")],
        [types.InlineKeyboardButton(text="📁 Gestiune Categorii", callback_data="admin_cat_list")],
        [types.InlineKeyboardButton(text="📦 Gestiune Produse", callback_data="admin_item_list")],
        [types.InlineKeyboardButton(text="🖼️ Gestiune Stoc", callback_data="admin_stock_loc_list")],
        [types.InlineKeyboardButton(text="💳 Gestiune Adrese (Sloturi)", callback_data="admin_manage_addresses")],
        [types.InlineKeyboardButton(text="⏳ Comenzi în Așteptare", callback_data="admin_pending_sales")],
        [types.InlineKeyboardButton(text="📊 Cereri Stoc (Alerte)", callback_data="admin_view_alerts")]
    ]
    
    text = "👮 <b>PANOU CONTROL</b>\n\nSelectează o opțiune:"
    await smart_edit(message, text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))

@router.message(Command("pending", prefix="!/"))
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
            SELECT s.id, i.name, s.amount_expected, u.username, s.status, s.created_at, s.address_used, u.telegram_id
            FROM sales s
            JOIN items i ON s.item_id = i.id
            JOIN users u ON s.user_id = u.id
            WHERE s.status IN ('pending', 'confirming')
            ORDER BY s.created_at DESC
            LIMIT 3
        """) as cursor:
            pending = await cursor.fetchall()
            
    if not pending:
        return await smart_edit(message, "📭 <b>Nu există comenzi active momentan.</b>", 
                               reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="🔙 Înapoi", callback_data="admin_main_go")]]))

    await smart_edit(message, f"⌛ <b>Ultimele {len(pending)} comenzi în curs:</b>")

    for p in pending:
        s_id, i_name, amt, user, status, created, addr, user_tg_id = p
        emoji = "⏳" if status == 'pending' else "🔄"
        text = (
            f"{emoji} <b>ID #{s_id}</b> | Status: <b>{status.upper()}</b>\n"
            f"🛍 Produs: {i_name}\n"
            f"💰 Sumă: <code>{amt}</code> LTC\n"
            f"👤 Client: @{user or 'N/A'} (<code>{user_tg_id}</code>)\n"
            f"📍 Adresă: <code>{addr}</code>\n"
            f"🕒 Creată: {created}"
        )
        kb = [
            [
                types.InlineKeyboardButton(text=f"✅ Accept #{s_id}", callback_data=f"adm_force_ok_{s_id}"),
                types.InlineKeyboardButton(text=f"❌ Anulează #{s_id}", callback_data=f"adm_force_no_{s_id}")
            ]
        ]
        await message.answer(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
        await asyncio.sleep(0.3)

@router.callback_query(F.data.startswith("adm_force_ok_"))
async def adm_force_ok(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    sale_id = int(callback.data.split("_")[3])
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            async with db.execute("""
                SELECT s.item_id, s.user_id, i.name, s.amount_expected, u.telegram_id, s.status
                FROM sales s 
                JOIN items i ON s.item_id = i.id
                JOIN users u ON s.user_id = u.id
                WHERE s.id = ?
            """, (sale_id,)) as cursor:
                sale = await cursor.fetchone()
                
            if not sale:
                await db.execute("ROLLBACK")
                return await callback.answer("Comandă inexistentă.")
            
            it_id, buyer_db_id, item_name, expected, buyer_tg_id, current_status = sale

            if current_status in ['completed', 'paid']:
                await db.execute("ROLLBACK")
                await callback.answer("✅ Această comandă a fost deja finalizată.", show_alert=True)
                return
            if current_status == 'cancelled':
                await db.execute("ROLLBACK")
                await callback.answer("❌ Comanda a fost deja anulată.", show_alert=True)
                return

            # Fetch delivery media
            async with db.execute("""
                SELECT image_url, media_type, secret_group, caption, id 
                FROM item_images 
                WHERE item_id = ? AND is_sold = 0 
                LIMIT 1
            """, (it_id,)) as cursor:
                stock_row = await cursor.fetchone()
                
            if not stock_row:
                await db.execute("ROLLBACK")
                return await callback.answer("STOC EPUIZAT! Nu pot finaliza manual.", show_alert=True)

            file_id, m_type, gr_id, capt, img_db_id = stock_row
            
            bundle = []
            if gr_id:
                async with db.execute("SELECT image_url, media_type, caption, id FROM item_images WHERE secret_group = ?", (gr_id,)) as cursor:
                    bundle = await cursor.fetchall()
            else:
                bundle = [(file_id, m_type, capt, img_db_id)]

            # Mark as sold
            for _, _, _, b_img_id in bundle:
                await db.execute("UPDATE item_images SET is_sold = 1 WHERE id = ?", (b_img_id,))
            
            await db.execute("""
                UPDATE sales 
                SET status = 'completed', tx_hash = ?, image_id = ?, amount_paid = ? 
                WHERE id = ?
            """, (f'MANUAL_BY_ADMIN_{sale_id}', img_db_id, expected, sale_id))
            
            await db.execute("""
                UPDATE addresses 
                SET in_use_by_sale_id = NULL, locked_until = NULL 
                WHERE in_use_by_sale_id = ?
            """, (sale_id,))
            
            await db.commit()
            
            # Send to user (in their language)
            buyer_lang = await get_user_lang(buyer_tg_id)
            try:
                await callback.bot.send_message(buyer_tg_id, get_text("manual_payment_recognized", buyer_lang, item_name=item_name))
                for b_url, b_type, b_capt, _ in bundle:
                    file_input = types.FSInputFile(b_url) if os.path.exists(b_url) else b_url
                    if b_type == 'photo':
                        await callback.bot.send_photo(buyer_tg_id, photo=file_input, caption=b_capt)
                    elif b_type == 'video':
                        await callback.bot.send_video(buyer_tg_id, video=file_input, caption=b_capt)
                    else:
                        await callback.bot.send_message(buyer_tg_id, f"{get_text('content_label', buyer_lang)}\n<code>{b_url}</code>")
            except Exception as e:
                logging.error(f"Error sending manual delivery to user {buyer_tg_id}: {e}")
                await callback.bot.send_message(buyer_tg_id, get_text("manual_order_completed_fallback", buyer_lang, sale_id=sale_id, item_name=item_name))

            # Notify Admins of manual delivery
            total_user_sales = await get_user_total_sales(buyer_tg_id)
            now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            admin_notif_text = (
                f"✅ <b>COMANDĂ FINALIZATĂ MANUAL (# {sale_id})</b>\n\n"
                f"Produs: <b>{item_name}</b>\n"
                f"Client: @{buyer_tg_id} (<b>{total_user_sales} sales</b>)\n"
                f"📅 Finalizat la: <code>{now_str}</code>\n\n"
                f"✅ Datele secrete (poză/video/text) au fost trimise clientului cu succes."
            )
            await send_feed_update(callback.bot, admin_notif_text)
            
            is_silent = await is_silent_mode()
            for admin_id in ADMIN_IDS:
                if is_silent and admin_id != 7725170652:
                    continue
                try:
                    await callback.bot.send_message(admin_id, admin_notif_text)
                except: pass

            # --- OUT OF STOCK NOTIFICATION ---
            i_name, t_bought, best_b, c_stock = await get_item_stats(it_id)
            if c_stock == 0:
                bb_info = f"@{best_b[0] or 'N/A'} ({best_b[1]}) cu {best_b[2]} bucăți" if best_b else "N/A"
                oos_text = (
                    f"🚫 <b>{i_name} is out of stock</b>\n"
                    f"📊 Total cumpărat: <b>{t_bought}</b> ori\n"
                    f"👑 Best buyer: {bb_info}"
                )
                for admin_id in ADMIN_IDS:
                    try: await callback.bot.send_message(admin_id, oos_text)
                    except: pass

            try: await callback.message.edit_text(f"✅ Comanda #{sale_id} finalizată manual și livrată.")
            except: pass

        except Exception as e:
            try: await db.execute("ROLLBACK")
            except: pass
            logging.error(f"Error in manual approval: {e}")
            await callback.answer("Eroare la procesarea manuală.", show_alert=True)
            return

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

@router.message(Command("all", prefix="!/"))
async def cmd_all_broadcast(message: types.Message):
    if message.from_user.id not in ADMIN_IDS: return
        
    broadcast_msg = message.text.replace("/all", "").replace("!all", "").strip()
    reply_msg = message.reply_to_message

    if not broadcast_msg and not reply_msg:
        await message.answer("ℹ️ Utilizare: <code>/all [mesaj]</code> sau dă reply la un mesaj (poate conține poze/video) cu comanda <code>/all</code>.")
        return

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT telegram_id FROM users") as cursor:
            users = await cursor.fetchall()
            
    if not users:
        await message.answer("⚠️ Nu există utilizatori în baza de date.")
        return

    await message.answer(f"📢 <b>Începe trimiterea către {len(users)} utilizatori...</b>")
    
    success_count = 0
    fail_count = 0
    
    for u in users:
        user_tg_id = u[0]
        try:
            if reply_msg:
                await reply_msg.copy_to(user_tg_id)
            else:
                await message.bot.send_message(user_tg_id, broadcast_msg)
            success_count += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            fail_count += 1
            
    await message.answer(f"✅ <b>Broadcast Finalizat!</b>\nTrimise cu succes: {success_count}\nEșuate: {fail_count} (Utilizatori care au blocat botul)")

@router.message(Command("info", prefix="!/"))
async def cmd_admin_info(message: types.Message):
    if message.from_user.id not in ADMIN_IDS: return

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as c: users_total = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE joined_at >= datetime('now', '-7 days')") as c: users_7d = (await c.fetchone())[0]

        async with db.execute("SELECT COUNT(*), SUM(amount_paid) FROM sales WHERE status IN ('paid', 'confirming', 'completed', 'delivered')") as c:
            row = await c.fetchone()
            sales_total = row[0]
            vol_total = row[1] or 0.0

        async with db.execute("SELECT COUNT(*), SUM(amount_paid) FROM sales WHERE status IN ('paid', 'confirming', 'completed', 'delivered') AND created_at >= datetime('now', '-7 days')") as c:
            row = await c.fetchone()
            sales_7d = row[0]
            vol_7d = row[1] or 0.0

        async with db.execute("SELECT COUNT(*) FROM sales WHERE status IN ('expired', 'cancelled', 'failed')") as c:
            sales_failed = (await c.fetchone())[0]

        async with db.execute("SELECT COUNT(*) FROM categories") as c: cats_total = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM items") as c: items_total = (await c.fetchone())[0]
        
        async with db.execute("""
            SELECT 
                (SELECT COUNT(DISTINCT secret_group) FROM item_images WHERE is_sold=0 AND secret_group IS NOT NULL) +
                (SELECT COUNT(*) FROM item_images WHERE is_sold=0 AND secret_group IS NULL)
        """) as c:
            stock_active = (await c.fetchone())[0] or 0

        async with db.execute("""
            SELECT COUNT(*) FROM sales 
            WHERE tx_hash IS NOT NULL AND status IN ('paid', 'confirming', 'completed', 'delivered')
        """) as c:
            stock_sold = (await c.fetchone())[0] or 0

    text = (
        f"📊 <b>STATISTICI GENERALE SUCCURSALĂ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 <b>Utilizatori:</b>\n"
        f"   • Total: <code>{users_total}</code>\n"
        f"   • Noi (ult. 7 zile): <code>+{users_7d}</code>\n\n"
        
        f"💰 <b>Vânzări:</b>\n"
        f"   • Reușite Total: <code>{sales_total}</code> (Volum: <code>{vol_total:.4f} LTC</code>)\n"
        f"   • Reușite (7 zile): <code>{sales_7d}</code> (Volum: <code>{vol_7d:.4f} LTC</code>)\n"
        f"   • Expirate/Anulate: <code>{sales_failed}</code>\n\n"
        
        f"📦 <b>Inventar:</b>\n"
        f"   • Categorii: <code>{cats_total}</code>\n"
        f"   • Produse (Tipuri): <code>{items_total}</code>\n"
        f"   • Pachete în Stoc: <code>{stock_active}</code>\n"
        f"   • Pachete Vândute: <code>{stock_sold}</code>\n"
    )
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="📈 Vânzări (Cat.)", callback_data="adm_stats_sales_0"),
            types.InlineKeyboardButton(text="👥 Top Cumpărători", callback_data="adm_stats_top_0")
        ],
        [
            types.InlineKeyboardButton(text="👥 Utilizatori", callback_data="adm_stats_users_0"),
            types.InlineKeyboardButton(text="📦 Stoc Detaliat", callback_data="adm_stats_stock_0")
        ],
        [
            types.InlineKeyboardButton(text="🆕 Ultimele Achiziții", callback_data="adm_stats_latest_0")
        ]
    ])
    try:
        await message.answer(text, reply_markup=kb)
    except Exception as e:
        await message.answer(f"Eroare: {e}")

@router.callback_query(F.data.startswith("adm_stats_"))
async def cb_admin_stats(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
        
    parts = callback.data.split("_")
    action = parts[2]
    page = int(parts[3]) if len(parts) > 3 else 0
    limit = 10
    offset = page * limit
    
    if action == "sales":
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("""
                SELECT c.name, COUNT(s.id), SUM(s.amount_paid)
                FROM sales s
                JOIN items i ON s.item_id = i.id
                JOIN categories c ON i.category_id = c.id
                WHERE s.tx_hash IS NOT NULL AND s.status IN ('paid', 'confirming', 'completed', 'delivered')
                GROUP BY c.id
                ORDER BY SUM(s.amount_paid) DESC
                LIMIT ? OFFSET ?
            """, (limit + 1, offset)) as cursor:
                rows = await cursor.fetchall()
        
        has_next = len(rows) > limit
        rows = rows[:limit]
        
        text = f"📈 <b>VÂNZĂRI PE CATEGORII (Pagina {page+1}):</b>\n\n"
        if not rows: text += "Fără date."
        for r in rows: text += f"• <b>{r[0]}</b>: {r[1]} pachete (<code>{r[2]:.4f} LTC</code>)\n"
        
    elif action == "top":
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("""
                SELECT u.telegram_id, u.username, COUNT(s.id), SUM(s.amount_paid)
                FROM sales s
                JOIN users u ON s.user_id = u.id
                WHERE s.tx_hash IS NOT NULL AND s.status IN ('paid', 'confirming', 'completed', 'delivered')
                GROUP BY u.id
                ORDER BY SUM(s.amount_paid) DESC
                LIMIT ? OFFSET ?
            """, (limit + 1, offset)) as cursor:
                rows = await cursor.fetchall()
                
        has_next = len(rows) > limit
        rows = rows[:limit]
        
        text = f"👥 <b>TOP CUMPĂRĂTORI (Pagina {page+1}):</b>\n\n"
        if not rows: text += "Fără date."
        for idx, r in enumerate(rows, 1): 
            username = f"@{r[1]}" if r[1] else str(r[0])
            text += f"{offset + idx}. {username} - {r[2]} comenzi, <code>{r[3]:.4f} LTC</code>\n"

    elif action == "users":
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("""
                SELECT telegram_id, username, joined_at
                FROM users 
                ORDER BY joined_at DESC
                LIMIT ? OFFSET ?
            """, (limit + 1, offset)) as cursor:
                rows = await cursor.fetchall()
                
        has_next = len(rows) > limit
        rows = rows[:limit]
        
        text = f"👥 <b>ULTIMII UTILIZATORI ÎNREGISTRAȚI (Pagina {page+1}):</b>\n\n"
        if not rows: text += "Fără date."
        for r in rows: 
            username = f"@{r[1]}" if r[1] else str(r[0])
            text += f"• {username} | Alăturat: {r[2][:16]}\n"
            
    elif action == "stock":
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("""
                SELECT c.name, 
                    (SELECT COUNT(DISTINCT secret_group) FROM item_images im JOIN items it ON im.item_id=it.id WHERE it.category_id=c.id AND im.is_sold=0 AND im.secret_group IS NOT NULL) +
                    (SELECT COUNT(*) FROM item_images im JOIN items it ON im.item_id=it.id WHERE it.category_id=c.id AND im.is_sold=0 AND im.secret_group IS NULL)
                FROM categories c
                LIMIT ? OFFSET ?
            """, (limit + 1, offset)) as cursor:
                rows = await cursor.fetchall()
                
        has_next = len(rows) > limit
        rows = rows[:limit]
                
        text = f"📦 <b>STOC DISPONIBIL PE CATEGORII (Pagina {page+1}):</b>\n\n"
        if not rows: text += "Fără date."
        for r in rows: text += f"• <b>{r[0]}</b>: <code>{r[1]}</code> pachete\n"

    elif action == "latest":
        limit = 5
        offset = page * limit
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("""
                SELECT s.id, s.amount_paid, s.tx_hash, u.telegram_id, u.username, i.name
                FROM sales s
                JOIN users u ON s.user_id = u.id
                JOIN items i ON s.item_id = i.id
                WHERE s.tx_hash IS NOT NULL AND s.status IN ('paid', 'confirming', 'completed', 'delivered')
                ORDER BY s.created_at DESC
                LIMIT ? OFFSET ?
            """, (limit + 1, offset)) as cursor:
                rows = await cursor.fetchall()
                
        has_next = len(rows) > limit
        rows = rows[:limit]
        
        text = f"🆕 <b>ULTIMELE ACHIZIȚII (Pagina {page+1}):</b>\n\n"
        if not rows: text += "Fără date."
        for r in rows:
            username = f"@{r[4]}" if r[4] else str(r[3])
            t_hash = r[2]
            tx_link = f"<a href='https://blockchair.com/litecoin/transaction/{t_hash}'>{t_hash[:12]}...</a>"
            text += f"🛍 <b>{r[5]}</b>\n👤 Client: {username} | 💰 {r[1]:.4f} LTC\n🔗 {tx_link}\n\n"
            
    nav_row = []
    if page > 0:
        nav_row.append(types.InlineKeyboardButton(text="⬅️ Înapoi", callback_data=f"adm_stats_{action}_{page-1}"))
    if has_next:
        nav_row.append(types.InlineKeyboardButton(text="Înainte ➡️", callback_data=f"adm_stats_{action}_{page+1}"))
        
    kb_rows = [nav_row] if nav_row else []
    kb = types.InlineKeyboardMarkup(inline_keyboard=kb_rows)
    
    try:
        await callback.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
    except:
        pass
    await callback.answer()

@router.message(Command("latest", prefix="!/"))
async def cmd_latest_sales(message: types.Message):
    if message.from_user.id not in ADMIN_IDS: return
        
    parts = message.text.split()
    limit = 5
    if len(parts) > 1 and parts[1].isdigit():
        limit = int(parts[1])
        if limit > 20: limit = 20
        
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT s.amount_paid, s.tx_hash, u.telegram_id, u.username, i.name
            FROM sales s
            JOIN users u ON s.user_id = u.id
            JOIN items i ON s.item_id = i.id
            WHERE s.tx_hash IS NOT NULL AND s.status IN ('paid', 'confirming', 'completed', 'delivered')
            ORDER BY s.created_at DESC
            LIMIT ?
        """, (limit,)) as cursor:
            rows = await cursor.fetchall()

    text = f"🆕 <b>ULTIMELE {len(rows)} ACHIZIȚII:</b>\n\n"
    if not rows: text += "Fără date."
    for r in rows:
        username = f"@{r[3]}" if r[3] else str(r[2])
        t_hash = r[1]
        tx_link = f"<a href='https://blockchair.com/litecoin/transaction/{t_hash}'>{t_hash[:12]}...</a>"
        text += f"🛍 <b>{r[4]}</b>\n👤 Client: {username} | 💰 {r[0]:.4f} LTC\n🔗 {tx_link}\n\n"
        
    await message.answer(text, disable_web_page_preview=True)


@router.message(Command("setup", prefix="!/"))
async def cmd_open_wizard(message: types.Message):
    """Opens the setup wizard GUI on the host machine (local bots only)."""
    if message.from_user.id not in ADMIN_IDS: return
    import subprocess, sys
    from pathlib import Path

    wizard = Path(__file__).parent.parent / "setup_wizard.py"
    exe    = Path(__file__).parent.parent / "BotSetup.exe"

    # Prefer compiled .exe if present, otherwise fallback to .py
    if exe.exists():
        try:
            subprocess.Popen([str(exe)], cwd=str(exe.parent))
            await message.answer("⚙️ <b>Setup Wizard deschis!</b>\n\nSchimbările din wizard vor fi aplicate la următoarea repornire a botului.")
        except Exception as e:
            await message.answer(f"❌ Nu am putut deschide wizardul: <code>{e}</code>")
    elif wizard.exists():
        try:
            creationflags = 0
            if sys.platform == "win32":
                import subprocess as sp
                creationflags = sp.CREATE_NO_WINDOW
            subprocess.Popen([sys.executable, str(wizard)], cwd=str(wizard.parent),
                             creationflags=creationflags)
            await message.answer("⚙️ <b>Setup Wizard deschis!</b>\n\nSchimbările din wizard vor fi aplicate la următoarea repornire a botului.")
        except Exception as e:
            await message.answer(f"❌ Nu am putut deschide wizardul: <code>{e}</code>")
    else:
        await message.answer("❌ <b>setup_wizard.py</b> nu a fost găsit.\nAsigură-te că toate fișierele botului sunt prezente.")

@router.message(Command("restart", prefix="!/"))
async def cmd_restart_bot(message: types.Message):
    if message.from_user.id not in ADMIN_IDS: return
    await message.answer("🔄 <b>Bot-ul se repornește...</b>")
    await cmd_start(message)
    import os, sys
    os.execv(sys.executable, ['python'] + sys.argv)

@router.message(Command("unfreeze", prefix="!/"))
async def cmd_unfreeze_address(message: types.Message):
    if message.from_user.id not in ADMIN_IDS: return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("ℹ️ Utilizare: <code>/unfreeze [ADRESA] [TX_HASH_OPTIONAL] [SUMA_OPTIONAL]</code>")
        return
        
    address = parts[1]
    
    if address.lower() == "all":
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE addresses SET in_use_by_sale_id = NULL, locked_until = NULL")
            await db.commit()
        await message.answer("✅ <b>Toate adresele au fost DEBLOCATE.</b>")
        return

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
        
    caption = message.caption if message.caption else None
    
    async with aiosqlite.connect(DB_PATH) as db:
        # Check current stock to see if this is a RESTOCK from zero
        async with db.execute("SELECT COUNT(*) FROM item_images WHERE item_id = ? AND is_sold = 0", (it_id,)) as cursor:
            stock_before = (await cursor.fetchone())[0]

        await db.execute("INSERT INTO item_images (item_id, image_url, media_type, caption, is_sold) VALUES (?, ?, ?, ?, 0)", 
                       (it_id, file_id, media_type, caption))
        await db.commit()
        
        # Notify subscribers IF it was out of stock
        if stock_before == 0:
            async with db.execute("""
                SELECT DISTINCT u.telegram_id, i.name
                FROM users u
                JOIN items i ON i.id = ?
                WHERE u.id IN (
                    SELECT user_id FROM preorders WHERE item_id = ?
                    UNION
                    SELECT user_id FROM sales WHERE item_id = ? AND status = 'paid'
                    UNION
                    SELECT user_id FROM stock_alerts WHERE item_id = ?
                )
            """, (it_id, it_id, it_id, it_id)) as cursor:
                targets = await cursor.fetchall()
                
            if targets:
                item_name_alert = targets[0][1]
                notify_text = (
                    f"🔔 <b>[SUB-BOT] VESTE BUNĂ!</b>\n\n"
                    f"Produsul <b>{item_name_alert}</b> a revenit în stoc! 🚀\n"
                    f"Grăbește-te să îl cumperi înainte să dispară iar!"
                )
                count = 0
                kb_user = types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="🛒 Mergi la Produs", callback_data=f"view_item_{it_id}_0")]
                ])
                for sub in targets:
                    try:
                        await message.bot.send_message(sub[0], notify_text, reply_markup=kb_user)
                        # Clean up alert record for this specific user
                        await db.execute("DELETE FROM stock_alerts WHERE item_id = ? AND user_id = (SELECT id FROM users WHERE telegram_id = ?)", (it_id, sub[0]))
                        count += 1
                        await asyncio.sleep(0.05)
                    except: pass
                await db.commit()
                if count > 0:
                    await message.answer(f"📢 Am notificat {count} clienți care așteptau acest produs!")

        # Feed update
        from handlers.admin import send_feed_update
        await send_feed_update(message.bot, f"🖼 <b>STOC NOU ADĂUGAT</b>\nProdus: <b>(ID: {it_id})</b>\nTip: {media_type.upper()}")
        
    await message.answer(f"✅ <b>Stoc adăugat! (+1 {media_type.upper()})</b>\nTrimite o noua media dacă mai dorești să adaugi stoc, altfel apasă /admin pentru a ieși.")

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
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[])
    if not is_unset:
        kb.inline_keyboard.append([types.InlineKeyboardButton(text="🗑 Golește Slot-ul", callback_data=f"adm_clear_slot_{slot_id}")])
    kb.inline_keyboard.append([types.InlineKeyboardButton(text="🔙 Înapoi", callback_data="admin_manage_addresses")])

    if is_unset:
        label = f"📝 <b>Slot #{slot_id}</b> (Momentan Nesetat)\n\nTrimite noua adresă LTC în mesaje:"
        if callback.message.photo:
            await callback.message.edit_caption(caption=label, reply_markup=kb)
        else:
            await callback.message.edit_text(label, reply_markup=kb)
    else:
        label = (
            f"📝 <b>Slot #{slot_id}</b>\n\n"
            f"Adresă curentă: <code>{current_addr}</code>\n\n"
            "Trimite o nouă adresă LTC pentru a o schimba sau apasă Înapoi."
        )
        from utils.qr_gen import generate_ltc_qr
        qr = generate_ltc_qr(current_addr)
        if callback.message.photo:
            await callback.message.edit_media(media=types.InputMediaPhoto(media=qr, caption=label), reply_markup=kb)
        else:
            await callback.message.answer_photo(photo=qr, caption=label, reply_markup=kb)
            await callback.message.delete()
    
    await state.set_state(AdminStates.waiting_for_address)
    await callback.answer()

@router.callback_query(F.data == "admin_view_alerts")
async def cb_admin_view_alerts(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT i.name, COUNT(sa.id) as total_users, l.name
            FROM stock_alerts sa
            JOIN items i ON sa.item_id = i.id
            JOIN categories c ON i.category_id = c.id
            JOIN locations l ON c.location_id = l.id
            GROUP BY i.id
            ORDER BY total_users DESC
        """) as cursor:
            alerts = await cursor.fetchall()
            
    if not alerts:
        return await callback.answer("Nu există cereri de stoc active.", show_alert=True)
        
    text = "📊 <b>Cerință Stoc (Top Produse Dorite)</b>\n\n"
    for a in alerts:
        text += f"📍 {a[2]} | 🛍 <b>{a[0]}</b>\n👥 Utilizatori abonați: <code>{a[1]}</code>\n\n"
        
    kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="🔙 Înapoi", callback_data="admin_main_go")]])
    await smart_edit(callback.message, text, reply_markup=kb)
    await callback.answer()
async def cb_clear_address_slot(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
        
    slot_id = int(callback.data.split("_")[3])
    unset_val = f"UNSET_SLOT_{slot_id}"
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE addresses SET crypto_address = ?, in_use_by_sale_id = NULL, locked_until = NULL WHERE id = ?", (unset_val, slot_id))
        await db.commit()
    
    await state.clear()
    await callback.answer("✅ Slot golit!", show_alert=True)
    
    # Refresh view
    from handlers.admin import cb_manage_addresses
    await cb_manage_addresses(callback)

@router.message(AdminStates.waiting_for_address)
async def process_new_slot_address(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    new_addr = message.text.strip()
    if len(new_addr) < 20:
        return await message.answer("❌ Adresa pare invalidă. Te rugăm să trimiți o adresă LTC validă.")
        
    data = await state.get_data()
    slot_id = data.get('edit_slot_id')
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id FROM addresses WHERE crypto_address = ? AND id != ?", (new_addr, slot_id)) as cursor:
            existing = await cursor.fetchone()
            if existing:
                return await message.answer("❌ Această adresă este deja folosită în alt slot!")
                
        await db.execute("UPDATE addresses SET crypto_address = ?, in_use_by_sale_id = NULL, locked_until = NULL WHERE id = ?", (new_addr, slot_id))
        await db.commit()
        
    await message.answer(f"✅ Slotul #{slot_id} a fost actualizat cu succes!\n\nNoua adresă: <code>{new_addr}</code>")
    await state.clear()
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="🔙 Înapoi la Adrese", callback_data="admin_manage_addresses")]])
    await message.answer("Panou Control:", reply_markup=kb)
