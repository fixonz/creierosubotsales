# Localization data for the bot

STRINGS = {
    "ro": {
        "welcome": (
            "🏙 <b>New Simple Crypto Bot</b>\n\n"
            "Bun venit în cel mai securizat magazin digital. "
            "Plăți LTC verificate cu livrare instantanee.\n\n"
            "🛒 <b>Alege orașul de mai jos pentru a începe.</b>"
        ),
        "choose_city": "🏘️ <b>SELECTEAZĂ ORAȘUL:</b>",
        "choose_sector": "🏘️ <b>ALEGE SECTORUL DIN {city}:</b>",
        "choose_category": "📂 <b>ALEGE CATEGORIA ({location}):</b>",
        "choose_item": "💎 <b>PRODUSE DISPONIBILE ({category}):</b>",
        "item_details": (
            "💎 <b>{name}</b>\n\n"
            "💰 Preț: <b>{price} RON</b>\n"
            "📦 Stoc: <b>{stock} bucăți</b>\n\n"
            "<i>Livrare instantă după confirmarea plății.</i>"
        ),
        "back": "🔙 Înapoi",
        "back_to_menu": "🔙 Înapoi la meniu",
        "buy_now": "🛒 Cumpără Acum",
        "preorder": "⏳ Precomandă",
        "buy_confirm": (
            "⚠️ <b>CONFIRMARE ACHIZIȚIE</b>\n\n"
            "Produs: <b>{name}</b>\n"
            "Sursă: <b>{location}</b>\n"
            "Preț: <b>{price_ron} RON</b> (aprox. <code>{price_ltc}</code> LTC)\n\n"
            "Ești sigur că vrei să generezi o adresă de plată?"
        ),
        "yes_continue": "✅ Da, continuă",
        "payment_info": (
            "💳 <b>INSTRUCȚIUNI PLATĂ</b>\n\n"
            "Pentru a primi <b>{item_name}</b>, te rugăm să trimiți <b>EXACT</b> suma de mai jos:\n\n"
            "💰 Sumă: <code>{amount}</code> LTC\n"
            "📍 Adresă: <code>{address}</code>\n\n"
            "🕒 Valabilitate: {timeout} minute\n\n"
            "⚠️ <i>Trimite exact suma afișată. După ce trimiți, apasă butonul Verify Payment.</i>"
        ),
        "verify_payment": "🔄 Verify Payment",
        "cancel_order": "❌ Anulează Comanda",
        "checking_payment": (
            "🔍 <b>VERIFICARE PLATĂ...</b>\n\n"
            "Căutăm tranzacția ta în blockchain.\n"
            "ID Comandă: #<code>{sale_id}</code>\n"
            "Adresă: <code>{address}</code>\n\n"
            "🔄 <i>Se verifică automat...</i>"
        ),
        "payment_not_found": (
            "❌ <b>PLATA NU A FOST GĂSITĂ</b>\n\n"
            "Dacă ai trimis deja banii, mai așteaptă puțin. Tranzacția este <b>PENDING</b> până apare în blockchain."
        ),
        "payment_found_pending": (
            "⏳ <b>PLATĂ DETECTATĂ (Confirmare în curs)</b>\n\n"
            "Am găsit tranzacția ta! Status: <b>{status}</b>\n"
            "Confirmări: <code>{confs}/1</code>\n\n"
            "🚀 <i>Livrarea se va face automat la prima confirmare.</i>"
        ),
        "payment_success": (
            "✅ <b>PLATA RECONOȘCUTĂ (# {sale_id})</b>\n\n"
            "Produs: <b>{item_name}</b>\n"
            "Iată pachetul tău mai jos.\n\n"
            "<i>Îți mulțumim pentru achiziție!</i>"
        ),
        "profile": (
            "👤 <b>PROFILUL TĂU</b>\n\n"
            "🆔 ID: <code>{user_id}</code>\n"
            "👤 Username: @{username}\n"
            "📅 Membru din: <b>{joined_at}</b>\n\n"
            "🛍️ Comenzi inițiate: <b>{total_orders}</b>\n"
            "💸 Total achitat: <b>{total_spent} RON</b>\n\n"
            "<i>Ultimele 10 comenzi:</i>"
        ),
        "change_lang": "🌍 Schimbă Limba / Change Language",
        "lang_selected": "✅ Limba a fost schimbată în Română!",
        "support": "💬 Centru de Suport",
        "support_text": (
            "💬 <b>Centru de Suport</b>\n\n"
            "👤 Contact Admin: {admin}\n"
            "🕒 Program: NON-STOP (24/7)"
        ),
        "error_no_loc": "Nicio locație configurată încă.",
        "pending_order_exists": "⚠️ Ai deja o comandă pending!",
        # --- Main menu buttons ---
        "btn_cities": "🏘️ Orașe",
        "btn_profile": "👤 Profil",
        "btn_support": "💬 Suport",
        "btn_reviews": "⭐ Recenzii",
        # --- Pending order ---
        "order_expired_alert": "⚠️ Comanda ta a expirat și a fost anulată.",
        "order_expired_text": "Comanda a expirat. Te rugăm să folosești /start pentru o nouă comandă.",
        "order_expired_prev": "⚠️ Comanda anterioară a expirat. Folosește /start pentru a începe una nouă.",
        "verify_payment_btn": "✅ Verifică Plata",
        "cancel_order_btn": "❌ Anulează Comanda",
        "active_order_title": "⏳ <b>COMANDĂ ACTIVĂ</b>",
        "active_order_id": "🆔 <b>ID Comandă:</b> <code>#{sale_id}</code>",
        "active_order_status": "Status: <code>{status}</code>",
        "active_order_confs": "Confirmări: <code>0/1</code>",
        "active_order_for": "Ai o comandă activă pentru: <b>{item_name}</b>",
        "active_order_value": "💵 <b>Valoare:</b> <code>{price_ron}</code> RON",
        "active_order_amount": "💰 <b>Sumă de plată:</b> <code>{amount_ltc}</code> LTC",
        "active_order_address": "📍 <b>Adresă LTC:</b> <code>{address}</code>",
        "active_order_expires": "⏰ <b>Expiră în:</b> <code>{minutes} minute</code>",
        "active_order_footer": "<i>Botul verifică automat rețeaua. Livrarea se face INSTANT după prima confirmare.</i>",
        # --- Location / Category ---
        "invalid_location": "Locație invalidă.",
        "no_categories": "✖️ Nicio categorie disponibilă aici.",
        # --- Item details ---
        "btn_buy": "💳 Cumpără: {price} RON ({ltc} LTC)",
        "btn_notify_me": "🔔 Anunță-mă",
        "btn_real_photo": "📸 VEZI POZA REALĂ (SPOILER)",
        "product_not_found": "Produs inexistent.",
        "ltc_rate_error": "Eroare curs LTC.",
        "no_ltc_addresses": "Nu există adrese LTC.",
        # --- Real photo ---
        "real_photo_caption": "📸 <b>POZĂ REALĂ: {item_name}</b>\n<i>Produsul este sub spoiler pentru discreție.</i>",
        "real_photo_buy": "💳 Cumpără",
        "data_error": "Eroare date.",
        "image_display_error": "Imaginea nu a putut fi afișată.",
        "spoiler_unavailable": "Imaginea spoiler nu este disponibilă.",
        # --- Verify payment ---
        "re_verify_btn": "🔄 Re-verifică",
        "order_invalid": "❌ Comandă invalidă sau deja procesată.",
        "tx_already_processed": "❌ Această tranzacție a fost deja procesată.",
        "stock_delivery_error": "⚠️ Eroare: Stoc epuizat în momentul livrării. Contactează suportul.",
        "content_label": "📦 <b>Conținut:</b>",
        "payment_no_tx_found": "❌ Nu am găsit nicio tranzacție.",
        "internal_verify_error": "⚠️ Eroare internă la verificare.",
        "borderline_payment_alert": "⏳ Plată detectată dar în afara limitei automate ({diff}%). Adminul va decide în scurt timp.",
        # --- Cancel order ---
        "order_cancelled": "❌ Comandă anulată.",
        # --- Stock alerts ---
        "profile_error": "Eroare profil.",
        "stock_subscribed": "🔔 Te vom anunța imediat ce produsul revine în stoc!",
        "stock_already_subscribed": "ℹ️ Ești deja abonat la alertele pentru acest produs.",
        "stock_subscribe_error": "Eroare la abonare.",
        # --- Profile ---
        "profile_not_found": "Nu am putut găsi profilul tău.",
        "date_undefined": "Nedefinit",
        "view_content_btn": "👁 Vezi Conținut #{sale_id} ({item_name})",
        "reviewed_btn": "✅ {item_name} (Recenzat)",
        "leave_review_btn": "⭐ Lasă Recenzie - {item_name}",
        # --- View Secret ---
        "order_content_title": "📦 <b>Conținut Comandă #{sale_id}</b>\nProdus: <b>{item_name}</b>",
        "order_unauthorized": "Comandă neautorizată sau inexistentă.",
        "content_resent": "Ți-am retrimis mesajele cu stocul!",
        # --- Reviews ---
        "reviews_title": "⭐ <b>RECENZII</b>",
        "reviews_empty": "⭐ <b>RECENZII</b>\n\nNu există recenzii momentan. Fii primul care lasă una după o achiziție!",
        "reviews_header": "⭐ <b>RECENZII CLIENȚI</b>\n\n📊 Notă medie: <b>{avg}/5.0</b> ({total} recenzii)\n\n",
        "reviews_newer": "⬅️ Mai noi",
        "reviews_older": "Mai vechi ➡️",
        "anonymous": "Anonim",
        # --- Write review ---
        "already_reviewed": "Ai lăsat deja o recenzie pentru această comandă!",
        "review_title": "⭐ <b>LĂSARE RECENZIE</b> (# {sale_id})\n\nCe notă acorzi experienței tale?",
        "rating_excellent": "⭐⭐⭐⭐⭐ 5 (Excelent)",
        "rating_very_good": "⭐⭐⭐⭐ 4 (Foarte Bun)",
        "rating_good": "⭐⭐⭐ 3 (Bun)",
        "rating_poor": "⭐⭐ 2 (Slab)",
        "rating_very_poor": "⭐ 1 (Foarte Slab)",
        "cancel_btn": "❌ Anulează",
        "rating_selected": "⭐ Ai selectat nota: <b>{rating}</b>\n\nTe rugăm să scrii un scurt comentariu despre produs/experiență (dă-ne un reply direct cu mesajul tău).",
        "review_saved": "✅ <b>Recenzia ta a fost salvată!</b> Îți mulțumim pentru feedback-ul acordat.",
        "review_error": "⚠️ O eroare a apărut. Probabil ai recenzat deja comanda.",
        "user_error": "⚠️ Eroare de utilizator.",
        # --- Preorder ---
        "preorder_title": "⏳ <b>PRECOMANDĂ: {item_name}</b>\n\nStocul este momentan epuizat, dar poți plasa o precomandă.\nAdmin-ul va verifica cererea și te va contacta în bot.\n\n💰 Preț: <b>{price} RON</b>",
        "preorder_send_btn": "📥 Trimite Precomandă",
        "preorder_already_exists": "⚠️ Ai deja o precomandă în curs de procesare. Te rugăm să aștepți aprobarea admin-ului.",
        "preorder_sent": "✅ <b>PRECOMANDĂ TRIMISĂ (# {preo_id})</b>\nS-a solicitat: <b>{item_name}</b>.\nVei primi o notificare aici când admin-ul procesează cererea.",
        "preorder_not_found": "Precomandă inexistentă.",
        "preorder_accepted": "✅ <b>PRECOMANDĂ ACCEPTATĂ! (# {preo_id})</b>\nAdmin-ul a aprobat cererea ta pentru <b>{item_name}</b>.\nTe va contacta în scurt timp!",
        "preorder_declined": "❌ <b>PRECOMANDĂ REFUZATĂ (# {preo_id})</b>\nCererea ta pentru <b>{item_name}</b> nu a putut fi onorată momentan.",
        "preorder_status_accepted": "\n\n✅ <b>STARE: ACCEPTATĂ</b>",
        "preorder_status_declined": "\n\n❌ <b>STARE: REFUZATĂ</b>",
        # --- Preorder text ---
        "preorder_label": "Precomandă",
        # --- Manual payment (admin-triggered, sent to buyer) ---
        "manual_payment_recognized": "🎉 <b>PLATA RECONOȘCUTĂ (Manual)</b>\n\n🛍 <b>{item_name}</b>\n\nIată conținutul pachetului tău:",
        "manual_order_completed_fallback": "✅ <b>COMANDĂ FINALIZATĂ MANUAL (# {sale_id})</b>\n\nProdus: <b>{item_name}</b>\nAdmin-ul a aprobat plata ta.\n\n<i>Îți mulțumim pentru achiziție!</i>\n\n⚠️ Eroare livrare media, dar comanda e validă.",
    },
    "en": {
        "welcome": (
            "🏙 <b>New Simple Crypto Bot</b>\n\n"
            "Welcome to the most secure digital store. Verified LTC payments with instant delivery.\n\n"
            "🛒 <b>Choose a city below to begin.</b>"
        ),
        "choose_city": "🏘️ <b>SELECT CITY:</b>",
        "choose_sector": "🏘️ <b>CHOOSE SECTOR IN {city}:</b>",
        "choose_category": "📂 <b>CHOOSE CATEGORY ({location}):</b>",
        "choose_item": "💎 <b>AVAILABLE PRODUCTS ({category}):</b>",
        "error_no_loc": "No locations configured yet.",
        "pending_order_exists": "⚠️ You already have a pending order!",
        "item_details": (
            "💎 <b>{name}</b>\n\n"
            "💰 Price: <b>{price} RON</b>\n"
            "📦 Stock: <b>{stock} pieces</b>\n\n"
            "<i>Instant delivery after payment confirmation.</i>"
        ),
        "back": "🔙 Back",
        "back_to_menu": "🔙 Back to Menu",
        "buy_now": "🛒 Buy Now",
        "preorder": "⏳ Preorder",
        "buy_confirm": (
            "⚠️ <b>PURCHASE CONFIRMATION</b>\n\n"
            "Product: <b>{name}</b>\n"
            "Source: <b>{location}</b>\n"
            "Price: <b>{price_ron} RON</b> (approx. <code>{price_ltc}</code> LTC)\n\n"
            "Are you sure you want to generate a payment address?"
        ),
        "yes_continue": "✅ Yes, continue",
        "payment_info": (
            "💳 <b>PAYMENT INSTRUCTIONS</b>\n\n"
            "To receive <b>{item_name}</b>, please send <b>EXACTLY</b> the amount below:\n\n"
            "💰 Amount: <code>{amount}</code> LTC\n"
            "📍 Address: <code>{address}</code>\n\n"
            "🕒 Validity: {timeout} minutes\n\n"
            "⚠️ <i>Send the exact amount shown. After sending, press Verify Payment.</i>"
        ),
        "verify_payment": "🔄 Verify Payment",
        "cancel_order": "❌ Cancel Order",
        "checking_payment": (
            "🔍 <b>VERIFYING PAYMENT...</b>\n\n"
            "Searching for your transaction on the blockchain.\n"
            "Order ID: #<code>{sale_id}</code>\n"
            "Address: <code>{address}</code>\n\n"
            "🔄 <i>Checking automatically...</i>"
        ),
        "payment_not_found": (
            "❌ <b>PAYMENT NOT FOUND</b>\n\n"
            "If you have already sent the funds, please wait a moment. The transaction is <b>PENDING</b> until it appears on the blockchain."
        ),
        "payment_found_pending": (
            "⏳ <b>PAYMENT DETECTED (Confirming)</b>\n\n"
            "We found your transaction! Status: <b>{status}</b>\n"
            "Confirmations: <code>{confs}/1</code>\n\n"
            "🚀 <i>Delivery will be automatic at the first confirmation.</i>"
        ),
        "payment_success": (
            "✅ <b>PAYMENT RECOGNIZED (# {sale_id})</b>\n\n"
            "Product: <b>{item_name}</b>\n"
            "Here is your package below:\n\n"
            "<i>Thank you for your purchase!</i>"
        ),
        "profile": (
            "👤 <b>YOUR PROFILE</b>\n\n"
            "🆔 ID: <code>{user_id}</code>\n"
            "👤 Username: @{username}\n"
            "📅 Member since: <b>{joined_at}</b>\n\n"
            "🛍️ Orders initiated: <b>{total_orders}</b>\n"
            "💸 Total paid: <b>{total_spent} RON</b>\n\n"
            "<i>Last 10 orders:</i>"
        ),
        "change_lang": "🌍 Schimbă Limba / Change Language",
        "lang_selected": "✅ Language has been changed to English!",
        "support": "💬 Support Center",
        "support_text": (
            "💬 <b>Support Center</b>\n\n"
            "👤 Admin Contact: {admin}\n"
            "🕒 Schedule: NON-STOP (24/7)"
        ),
        # --- Main menu buttons ---
        "btn_cities": "🏘️ Cities",
        "btn_profile": "👤 Profile",
        "btn_support": "💬 Support",
        "btn_reviews": "⭐ Reviews",
        # --- Pending order ---
        "order_expired_alert": "⚠️ Your order has expired and been cancelled.",
        "order_expired_text": "The order has expired. Please use /start for a new order.",
        "order_expired_prev": "⚠️ The previous order has expired. Use /start to begin a new one.",
        "verify_payment_btn": "✅ Verify Payment",
        "cancel_order_btn": "❌ Cancel Order",
        "active_order_title": "⏳ <b>ACTIVE ORDER</b>",
        "active_order_id": "🆔 <b>Order ID:</b> <code>#{sale_id}</code>",
        "active_order_status": "Status: <code>{status}</code>",
        "active_order_confs": "Confirmations: <code>0/1</code>",
        "active_order_for": "You have an active order for: <b>{item_name}</b>",
        "active_order_value": "💵 <b>Value:</b> <code>{price_ron}</code> RON",
        "active_order_amount": "💰 <b>Amount to pay:</b> <code>{amount_ltc}</code> LTC",
        "active_order_address": "📍 <b>LTC Address:</b> <code>{address}</code>",
        "active_order_expires": "⏰ <b>Expires in:</b> <code>{minutes} minutes</code>",
        "active_order_footer": "<i>The bot checks the network automatically. Delivery is INSTANT after the first confirmation.</i>",
        # --- Location / Category ---
        "invalid_location": "Invalid location.",
        "no_categories": "✖️ No categories available here.",
        # --- Item details ---
        "btn_buy": "💳 Buy: {price} RON ({ltc} LTC)",
        "btn_notify_me": "🔔 Notify me",
        "btn_real_photo": "📸 VIEW REAL PHOTO (SPOILER)",
        "product_not_found": "Product not found.",
        "ltc_rate_error": "LTC rate error.",
        "no_ltc_addresses": "No LTC addresses available.",
        # --- Real photo ---
        "real_photo_caption": "📸 <b>REAL PHOTO: {item_name}</b>\n<i>The product is under spoiler for discretion.</i>",
        "real_photo_buy": "💳 Buy",
        "data_error": "Data error.",
        "image_display_error": "The image could not be displayed.",
        "spoiler_unavailable": "The spoiler image is not available.",
        # --- Verify payment ---
        "re_verify_btn": "🔄 Re-verify",
        "order_invalid": "❌ Invalid or already processed order.",
        "tx_already_processed": "❌ This transaction has already been processed.",
        "stock_delivery_error": "⚠️ Error: Stock depleted at time of delivery. Contact support.",
        "content_label": "📦 <b>Content:</b>",
        "payment_no_tx_found": "❌ No transaction found.",
        "internal_verify_error": "⚠️ Internal verification error.",
        "borderline_payment_alert": "⏳ Payment detected but outside automatic limit ({diff}%). Admin will decide shortly.",
        # --- Cancel order ---
        "order_cancelled": "❌ Order cancelled.",
        # --- Stock alerts ---
        "profile_error": "Profile error.",
        "stock_subscribed": "🔔 We'll notify you as soon as the product is back in stock!",
        "stock_already_subscribed": "ℹ️ You are already subscribed to alerts for this product.",
        "stock_subscribe_error": "Subscription error.",
        # --- Profile ---
        "profile_not_found": "Could not find your profile.",
        "date_undefined": "Undefined",
        "view_content_btn": "👁 View Content #{sale_id} ({item_name})",
        "reviewed_btn": "✅ {item_name} (Reviewed)",
        "leave_review_btn": "⭐ Leave Review - {item_name}",
        # --- View Secret ---
        "order_content_title": "📦 <b>Order Content #{sale_id}</b>\nProduct: <b>{item_name}</b>",
        "order_unauthorized": "Unauthorized or non-existent order.",
        "content_resent": "We've re-sent the stock messages to you!",
        # --- Reviews ---
        "reviews_title": "⭐ <b>REVIEWS</b>",
        "reviews_empty": "⭐ <b>REVIEWS</b>\n\nNo reviews yet. Be the first to leave one after a purchase!",
        "reviews_header": "⭐ <b>CUSTOMER REVIEWS</b>\n\n📊 Average rating: <b>{avg}/5.0</b> ({total} reviews)\n\n",
        "reviews_newer": "⬅️ Newer",
        "reviews_older": "Older ➡️",
        "anonymous": "Anonymous",
        # --- Write review ---
        "already_reviewed": "You have already reviewed this order!",
        "review_title": "⭐ <b>LEAVE A REVIEW</b> (# {sale_id})\n\nHow would you rate your experience?",
        "rating_excellent": "⭐⭐⭐⭐⭐ 5 (Excellent)",
        "rating_very_good": "⭐⭐⭐⭐ 4 (Very Good)",
        "rating_good": "⭐⭐⭐ 3 (Good)",
        "rating_poor": "⭐⭐ 2 (Poor)",
        "rating_very_poor": "⭐ 1 (Very Poor)",
        "cancel_btn": "❌ Cancel",
        "rating_selected": "⭐ You selected rating: <b>{rating}</b>\n\nPlease write a short comment about the product/experience (reply directly with your message).",
        "review_saved": "✅ <b>Your review has been saved!</b> Thank you for your feedback.",
        "review_error": "⚠️ An error occurred. You may have already reviewed this order.",
        "user_error": "⚠️ User error.",
        # --- Preorder ---
        "preorder_title": "⏳ <b>PREORDER: {item_name}</b>\n\nStock is currently depleted, but you can place a preorder.\nThe admin will review your request and contact you in the bot.\n\n💰 Price: <b>{price} RON</b>",
        "preorder_send_btn": "📥 Send Preorder",
        "preorder_already_exists": "⚠️ You already have a preorder being processed. Please wait for admin approval.",
        "preorder_sent": "✅ <b>PREORDER SENT (# {preo_id})</b>\nRequested: <b>{item_name}</b>.\nYou will receive a notification here when the admin processes your request.",
        "preorder_not_found": "Preorder not found.",
        "preorder_accepted": "✅ <b>PREORDER ACCEPTED! (# {preo_id})</b>\nThe admin has approved your request for <b>{item_name}</b>.\nThey will contact you shortly!",
        "preorder_declined": "❌ <b>PREORDER DECLINED (# {preo_id})</b>\nYour request for <b>{item_name}</b> could not be fulfilled at this time.",
        "preorder_status_accepted": "\n\n✅ <b>STATUS: ACCEPTED</b>",
        "preorder_status_declined": "\n\n❌ <b>STATUS: DECLINED</b>",
        # --- Preorder text ---
        "preorder_label": "Preorder",
        # --- Manual payment (admin-triggered, sent to buyer) ---
        "manual_payment_recognized": "🎉 <b>PAYMENT RECOGNIZED (Manual)</b>\n\n🛍 <b>{item_name}</b>\n\nHere is your package:",
        "manual_order_completed_fallback": "✅ <b>ORDER COMPLETED MANUALLY (# {sale_id})</b>\n\nProduct: <b>{item_name}</b>\nThe admin has approved your payment.\n\n<i>Thank you for your purchase!</i>\n\n⚠️ Media delivery error, but your order is valid.",
    }
}

def get_text(key, lang="ro", **kwargs):
    text = STRINGS.get(lang, STRINGS["ro"]).get(key, key)
    return text.format(**kwargs)
