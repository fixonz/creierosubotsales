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
            InlineKeyboardButton(text="📦 Gestiune Magazin (Cat/Prod/Stoc)", callback_data="adm_cats")
        ],
        [
            InlineKeyboardButton(text="⏳ Precomenzi", callback_data="adm_preo_mgmt_0"),
            InlineKeyboardButton(text="📈 Statistici & Vânzări", callback_data="adm_stats_info")
        ],
        [
            InlineKeyboardButton(text="🔔 Setări Silent Mode", callback_data="admin_silent_mgmt")
        ],
        [InlineKeyboardButton(text="🔙 Ieșire", callback_data="menu_start")]
    ])
    return markup



