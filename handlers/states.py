from aiogram.fsm.state import State, StatesGroup

class AdminCategory(StatesGroup):
    waiting_for_name = State()
    waiting_for_image = State()

class AdminItem(StatesGroup):
    waiting_for_category = State()
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_price_ron = State()
    waiting_for_image = State()

class AdminStock(StatesGroup):
    waiting_for_item = State()
    waiting_for_image = State()
    waiting_for_bundle = State()

class AdminRemoval(StatesGroup):
    waiting_for_cat_confirm = State()
    waiting_for_item_confirm = State()
    waiting_for_stock_confirm = State()

class AdminAddress(StatesGroup):
    waiting_for_address = State()

class ReviewState(StatesGroup):
    wait_rating = State()
    wait_comment = State()

class AdminPreorder(StatesGroup):
    waiting_for_time = State()
    target_id = State()

class SupportTicketState(StatesGroup):
    waiting_for_message = State()
    sale_id = State()

class AdminReplyState(StatesGroup):
    waiting_for_reply = State()
    target_user_id = State()
    sale_id = State()
