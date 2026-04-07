from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 MAGAZIN", callback_data="menu_shop")],
        [
            InlineKeyboardButton(text="👤 PROFIL", callback_data="menu_profile"),
            InlineKeyboardButton(text="💬 SUPORT", callback_data="menu_support")
        ],
        [InlineKeyboardButton(text="⭐ RECENZII", callback_data="show_reviews_0")]
    ])
    return markup

def admin_main_menu() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📁 Categorii / Produse / Stoc", callback_data="adm_cats")
        ],
        [
            InlineKeyboardButton(text="📈 Statistici & Istoric", callback_data="adm_stats_info"),
            InlineKeyboardButton(text="⏳ Pending", callback_data="adm_pending_link")
        ],
        [
            InlineKeyboardButton(text="⏳ Precomenzi active", callback_data="adm_preo_mgmt_0"),
            InlineKeyboardButton(text="💳 Adrese LTC Root", callback_data="adm_addresses_link")
        ],
        [InlineKeyboardButton(text="🔙 Ieșire", callback_data="menu_start")]
    ])
    return markup



