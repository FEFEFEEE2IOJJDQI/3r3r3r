"""
Модуль клавиатур
Все inline и reply клавиатуры бота
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from config import WEBAPP_URL

def _feed_button(text: str = "📱 Лента заказов") -> InlineKeyboardButton:
    """Создает кнопку для открытия мини‑приложения ленты заказов."""
    return InlineKeyboardButton(text=text, web_app=WebAppInfo(url=f"{WEBAPP_URL}/orders"))

def get_main_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Богдан", callback_data="bogdan1")],
        [InlineKeyboardButton(text="Богдан", callback_data="bogdan2")],
        [InlineKeyboardButton(text="Богдан", callback_data="bogdan3")],
        [InlineKeyboardButton(text="Богдан", callback_data="bogdan4")],
        [InlineKeyboardButton(text="Богдан", callback_data="bogdan5")]
    ])
    return keyboard

async def get_main_menu_with_role(user_id: int, db):
    """Главное меню с кнопкой текущей роли пользователя"""
    user = await db.get_user(user_id)
    
    # Определяем текст и emoji кнопки роли
    if user and user.get('user_role') == 'executor':
        role_button_text = "⚡ Исполнитель"
    else:
        role_button_text = "👤 Заказчик"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=role_button_text, callback_data="show_current_role")],
        [InlineKeyboardButton(text="🔍 Пробив", callback_data="probiv"),
         InlineKeyboardButton(text="📞 Поддержка", callback_data="support_center")]
    ])
    return keyboard

def get_support_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚠️ Жалоба на объявление", callback_data="complaint_order")],
        [InlineKeyboardButton(text="🚫 Жалоба на пользователя", callback_data="complaint_user")],
        [InlineKeyboardButton(text="💡 Предложить идею", callback_data="suggest_idea")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])
    return keyboard

def get_customer_menu(orders_count=0):
    orders_badge = f" ({orders_count})" if orders_count > 0 else ""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать заказ", callback_data="create_order")],
        [InlineKeyboardButton(text=f"📋 Мои заказы{orders_badge}", callback_data="my_orders"),
         InlineKeyboardButton(text="🏆 Топ", callback_data="top_executors")],
        [InlineKeyboardButton(text="🏠 Меню", callback_data="main_menu")]
    ])
    return keyboard

def get_customer_orders_menu(active_count=0, deleted_count=0):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🗑️ Удалить все ({active_count})", callback_data="delete_all_orders")],
        [InlineKeyboardButton(text=f"♻️ Корзина ({deleted_count})", callback_data="deleted_orders"),
         InlineKeyboardButton(text="✅ Завершенные", callback_data="completed_orders")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_customer")]
    ])
    return keyboard

def get_executor_menu(feed_count=0, my_orders_count=0):
    feed_badge = f" ({feed_count})" if feed_count > 0 else ""
    orders_badge = f" ({my_orders_count})" if my_orders_count > 0 else ""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [_feed_button(text=f"📱 Лента заказов{feed_badge}"),
         InlineKeyboardButton(text=f"📋 Мои заказы{orders_badge}", callback_data="executor_my_orders")],
        [InlineKeyboardButton(text="👤 Профиль", callback_data="my_profile"),
         InlineKeyboardButton(text="🏆 Топ", callback_data="leaderboard")],
        [InlineKeyboardButton(text="🏠 Меню", callback_data="main_menu")]
    ])
    return keyboard

def get_admin_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users"),
         InlineKeyboardButton(text="📦 Заказы", callback_data="admin_orders")],
        [InlineKeyboardButton(text="🚨 Подозрительные", callback_data="admin_suspicious"),
         InlineKeyboardButton(text="⚠️ Жалобы", callback_data="admin_complaints")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin_settings"),
         InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📝 Логи", callback_data="admin_logs"),
         InlineKeyboardButton(text="🚪 Выход", callback_data="admin_exit")]
    ])
    return keyboard

def get_admin_settings_keyboard(suspicious_enabled, complaints_enabled, quiet_mode, moderation_sensitivity='medium'):
    suspicious_status = "✅" if suspicious_enabled else "❌"
    complaints_status = "✅" if complaints_enabled else "❌"
    
    if quiet_mode:
        quiet_button_text = "🔔 Выкл. режим тишины"
    else:
        quiet_button_text = "🔕 Вкл. режим тишины"
    
    sensitivity_text = {
        'off': '⚪ Выкл',
        'low': '🟢 Низкая',
        'medium': '🟡 Средняя',
        'high': '🔴 Высокая'
    }.get(moderation_sensitivity, '🟡 Средняя')
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=quiet_button_text, callback_data="toggle_quiet_mode")],
        [InlineKeyboardButton(text=f"🛡️ ИИ-защита: {sensitivity_text}", callback_data="change_moderation_sensitivity")],
        [InlineKeyboardButton(text=f"{suspicious_status} Подозрительные", callback_data="toggle_suspicious_notif"),
         InlineKeyboardButton(text=f"{complaints_status} Жалобы", callback_data="toggle_complaints_notif")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_settings_back")]
    ])
    return keyboard

def get_moderation_sensitivity_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚪ Выключена", callback_data="sensitivity_off")],
        [InlineKeyboardButton(text="🟢 Низкая", callback_data="sensitivity_low")],
        [InlineKeyboardButton(text="🟡 Средняя (рекомендуется)", callback_data="sensitivity_medium")],
        [InlineKeyboardButton(text="🔴 Высокая", callback_data="sensitivity_high")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="sensitivity_back")]
    ])
    return keyboard

def get_suspicious_order_actions(order_id):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚫 Заблокировать", callback_data=f"block_order_{order_id}"),
         InlineKeyboardButton(text="✅ Пропустить", callback_data="suspicious_back")]
    ])
    return keyboard

def get_admin_users_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Найти", callback_data="admin_find_user"),
         InlineKeyboardButton(text="🚫 Бан/Разбан", callback_data="admin_ban_menu")],
        [InlineKeyboardButton(text="⚡ Исполнители", callback_data="admin_list_executors"),
         InlineKeyboardButton(text="👤 Заказчики", callback_data="admin_list_customers")],
        [InlineKeyboardButton(text="⭐ Рейтинги", callback_data="admin_edit_ratings"),
         InlineKeyboardButton(text="🔄 Сброс заказа", callback_data="admin_reset_order")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]
    ])
    return keyboard

def get_admin_orders_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Активные", callback_data="admin_all_active_orders"),
         InlineKeyboardButton(text="🔍 По ID", callback_data="admin_search_order")],
        [InlineKeyboardButton(text="⏸️ Остановить набор", callback_data="admin_stop_recruiting")],
        [InlineKeyboardButton(text="📝 Статус", callback_data="admin_change_status"),
         InlineKeyboardButton(text="✏️ Редактировать", callback_data="admin_edit_order")],
        [InlineKeyboardButton(text="⚠️ Удалить", callback_data="admin_delete_order")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]
    ])
    return keyboard

def get_admin_complaints_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🆕 Новые", callback_data="admin_new_complaints"),
         InlineKeyboardButton(text="✅ Решенные", callback_data="admin_resolved_complaints")],
        [InlineKeyboardButton(text="📜 Все жалобы", callback_data="admin_all_complaints")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]
    ])
    return keyboard

def get_admin_settings_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Комиссия", callback_data="admin_commission"),
         InlineKeyboardButton(text="💵 Мин. цена", callback_data="admin_min_price")],
        [InlineKeyboardButton(text="👥 Лимит исполн.", callback_data="admin_executor_limit"),
         InlineKeyboardButton(text="📦 Автоархив", callback_data="admin_auto_archive")],
        [InlineKeyboardButton(text="🗑️ Автоочистка", callback_data="admin_auto_clean")],
        [InlineKeyboardButton(text="👋 Приветствие", callback_data="admin_welcome_text"),
         InlineKeyboardButton(text="❓ FAQ", callback_data="admin_faq")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]
    ])
    return keyboard

def get_cancel_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])
    return keyboard

def get_skip_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="skip"),
         InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])
    return keyboard

def get_confirm_order_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Опубликовать", callback_data="confirm_order_publish")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="confirm_order_cancel")]
    ])
    return keyboard

def get_work_types():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏗️ Стройка", callback_data="work_construction"),
         InlineKeyboardButton(text="🔨 Разнорабочий", callback_data="work_handyman")],
        [InlineKeyboardButton(text="📦 Грузчики", callback_data="work_movers"),
         InlineKeyboardButton(text="🚚 Доставка", callback_data="work_delivery")],
        [InlineKeyboardButton(text="🔧 Ремонт", callback_data="work_repair"),
         InlineKeyboardButton(text="🧹 Уборка", callback_data="work_cleaning")],
        [InlineKeyboardButton(text="🔨 Другое", callback_data="work_other")]
    ])
    return keyboard

def get_order_actions(order_id, order_status='open'):
    buttons = [[InlineKeyboardButton(text="👥 Отклики", callback_data=f"view_responses_{order_id}")]]
    
    if order_status in ['assigned', 'in_progress']:
        buttons.append([InlineKeyboardButton(text="✅ Выполнен", callback_data=f"mark_complete_{order_id}"),
                       InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete_order_{order_id}")])
    else:
        buttons.append([InlineKeyboardButton(text="🗑️ Удалить заказ", callback_data=f"delete_order_{order_id}")])
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="my_orders")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard

def get_customer_order_card_keyboard(order_id, order_status, current_page, total_pages, responses_count=0):
    buttons = []
    
    nav_row = []
    if current_page > 0:
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"cust_order_prev_{current_page}"))
    nav_row.append(InlineKeyboardButton(text=f"{current_page + 1}/{total_pages}", callback_data="noop"))
    if current_page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"cust_order_next_{current_page}"))
    buttons.append(nav_row)
    
    responses_text = f"👥 Отклики ({responses_count})" if responses_count > 0 else "👥 Отклики"
    buttons.append([InlineKeyboardButton(text=responses_text, callback_data=f"view_responses_{order_id}")])
    
    if order_status in ['assigned', 'in_progress']:
        buttons.append([
            InlineKeyboardButton(text="✅ Выполнен", callback_data=f"mark_complete_{order_id}"),
            InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete_order_{order_id}")
        ])
    else:
        buttons.append([InlineKeyboardButton(text="🗑️ Удалить заказ", callback_data=f"delete_order_{order_id}")])
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_customer")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_complete_confirmation(order_id):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_complete_{order_id}"),
         InlineKeyboardButton(text="❌ Нет", callback_data=f"cancel_complete_{order_id}")]
    ])
    return keyboard

def get_complete_final_confirmation(order_id):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, выполнен", callback_data=f"final_complete_{order_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_complete_{order_id}")]
    ])
    return keyboard

def get_delete_confirmation(order_id):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Удалить", callback_data=f"confirm_delete_{order_id}"),
         InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_delete_{order_id}")]
    ])
    return keyboard

def get_delete_all_confirmation():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить все", callback_data="confirm_delete_all_orders")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete_all_orders")]
    ])
    return keyboard

def get_restore_order_keyboard(order_id):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="♻️ Восстановить", callback_data=f"restore_order_{order_id}"),
         InlineKeyboardButton(text="🗑️ Удалить навсегда", callback_data=f"permanent_delete_{order_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="deleted_orders")]
    ])
    return keyboard

def get_decline_confirmation(order_id):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отказаться", callback_data=f"confirm_decline_{order_id}"),
         InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_decline_{order_id}")]
    ])
    return keyboard

def get_executor_actions(response_id, executor_id, order_id):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять", callback_data=f"accept_executor_{order_id}_{executor_id}"),
         InlineKeyboardButton(text="👤 Профиль", callback_data=f"view_profile_{executor_id}_{order_id}")]
    ])
    return keyboard

def get_order_card(order_id):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✋ Откликнуться", callback_data=f"take_order_{order_id}")]
    ])
    return keyboard

def get_new_order_notification_keyboard(order_id):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✋ Беру", callback_data=f"notify_take_{order_id}"),
         InlineKeyboardButton(text="🙈 Скрыть", callback_data=f"notify_hide_{order_id}")]
    ])
    return keyboard

def get_confirm_take_order_keyboard(order_id):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, взять заказ", callback_data=f"confirm_notify_take_{order_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_notify_take_{order_id}")]
    ])
    return keyboard

def get_confirm_hide_order_keyboard(order_id):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, скрыть", callback_data=f"confirm_notify_hide_{order_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_notify_hide_{order_id}")]
    ])
    return keyboard

def get_back_to_feed_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [_feed_button(text="📱 Вернуться к ленте")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_executor_menu")]
    ])
    return keyboard

def get_action_result_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [_feed_button(text="📱 К ленте заказов")],
        [InlineKeyboardButton(text="📦 Мои заказы", callback_data="executor_my_orders")],
        [InlineKeyboardButton(text="🏠 Меню", callback_data="back_to_executor_menu")]
    ])
    return keyboard

def get_executor_order_actions(order_id, order_status='assigned'):
    buttons = []
    buttons.append([InlineKeyboardButton(text="✅ Завершить", callback_data=f"executor_complete_{order_id}"),
                   InlineKeyboardButton(text="❌ Отказаться", callback_data=f"decline_order_{order_id}")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="executor_my_orders")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard

def get_executor_complete_confirmation(order_id):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, завершить", callback_data=f"confirm_executor_complete_{order_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_executor_complete_{order_id}")]
    ])
    return keyboard

def get_rating_keyboard(order_id):
    buttons = [InlineKeyboardButton(text=f"{i}", callback_data=f"rate_{order_id}_{i}") for i in range(1, 6)]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        buttons,
        [InlineKeyboardButton(text="⏭️ Пропустить оценку", callback_data=f"skip_rate_{order_id}")]
    ])
    return keyboard

def get_my_orders_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 История заказов", callback_data="executor_history")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_executor_menu")]
    ])
    return keyboard

def get_order_details_keyboard(order_id):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="executor_history")]
    ])
    return keyboard

def get_filters_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Тип работы", callback_data="filter_type"),
         InlineKeyboardButton(text="📍 Локация", callback_data="filter_location")],
        [InlineKeyboardButton(text="💰 Цена", callback_data="filter_price"),
         InlineKeyboardButton(text="⭐ Рейтинг", callback_data="filter_rating")],
        [InlineKeyboardButton(text="❌ Сбросить", callback_data="clear_filters")]
    ])
    return keyboard

def get_user_actions(user_id):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Профиль", callback_data=f"admin_view_{user_id}"),
         InlineKeyboardButton(text="📢 Написать", callback_data=f"admin_msg_{user_id}")],
        [InlineKeyboardButton(text="🚫 Бан", callback_data=f"admin_ban_{user_id}"),
         InlineKeyboardButton(text="✅ Разбан", callback_data=f"admin_unban_{user_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back_to_users")]
    ])
    return keyboard

def get_pagination(current_page, total_pages, prefix):
    buttons = []
    if current_page > 0:
        buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"{prefix}_{current_page-1}"))
    buttons.append(InlineKeyboardButton(text=f"{current_page+1}/{total_pages}", callback_data="noop"))
    if current_page < total_pages - 1:
        buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"{prefix}_{current_page+1}"))
    keyboard = InlineKeyboardMarkup(inline_keyboard=[buttons])
    return keyboard

def get_order_feed_keyboard(order_id, current_page, total_pages):
    buttons = []
    nav_row = []
    if current_page > 0:
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"feed_page_{current_page-1}"))
    nav_row.append(InlineKeyboardButton(text=f"{current_page+1}/{total_pages}", callback_data="noop"))
    if current_page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"feed_page_{current_page+1}"))
    
    buttons.append([InlineKeyboardButton(text="✋ Откликнуться", callback_data=f"take_order_{order_id}")])
    buttons.append(nav_row)
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_executor_menu")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard

def get_profile_keyboard(user_id):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Все отзывы", callback_data=f"show_reviews_{user_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_executor_menu")]
    ])
    return keyboard

def get_comment_question_keyboard(order_id):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да", callback_data=f"comment_yes_{order_id}"),
         InlineKeyboardButton(text="❌ Нет", callback_data=f"comment_no_{order_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
    ])
    return keyboard

def get_complaint_actions(complaint_id):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Решить", callback_data=f"resolve_complaint_{complaint_id}"),
         InlineKeyboardButton(text="🔙 Назад", callback_data="complaints_back")]
    ])
    return keyboard

def get_admin_complaint_notification_keyboard(complaint_id=None):
    buttons = []
    if complaint_id:
        buttons.append([InlineKeyboardButton(text="✅ Решено", callback_data=f"resolve_complaint_{complaint_id}")])
    buttons.append([InlineKeyboardButton(text="🔐 Админ панель", callback_data="go_to_admin_panel")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard

def get_admin_suspicious_notification_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚨 Подозрительные", callback_data="go_to_suspicious_orders")]
    ])
    return keyboard

def get_suspicious_order_keyboard(order_id):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔨 Забанить", callback_data=f"ban_user_susp_{order_id}"),
         InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete_order_susp_{order_id}")],
        [InlineKeyboardButton(text="📵 Бан ленты", callback_data=f"feed_ban_susp_{order_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="go_to_suspicious_orders")]
    ])
    return keyboard

def get_back_keyboard(callback_data="main_menu"):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data=callback_data)]
    ])
    return keyboard

def get_empty_feed_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [_feed_button(text="🔄 Открыть ленту")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_executor_menu")]
    ])
    return keyboard

def get_response_card_keyboard(order_id, executor_id, current_idx, total_count):
    buttons = []
    
    buttons.append([
        InlineKeyboardButton(text="✅ Принять", callback_data=f"accept_executor_{order_id}_{executor_id}"),
        InlineKeyboardButton(text="👤 Профиль", callback_data=f"view_profile_{executor_id}_{order_id}")
    ])
    
    nav_row = []
    if current_idx > 0:
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"resp_prev_{order_id}_{current_idx}"))
    nav_row.append(InlineKeyboardButton(text=f"{current_idx + 1}/{total_count}", callback_data="noop"))
    if current_idx < total_count - 1:
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"resp_next_{order_id}_{current_idx}"))
    buttons.append(nav_row)
    
    buttons.append([InlineKeyboardButton(text="🔙 К заказу", callback_data=f"back_to_order_{order_id}")])
    buttons.append([InlineKeyboardButton(text="📋 К заказам", callback_data="view_my_orders")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard

def get_no_responses_keyboard(order_id):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"view_responses_{order_id}")],
        [InlineKeyboardButton(text="🔙 К заказу", callback_data=f"back_to_order_{order_id}")],
        [InlineKeyboardButton(text="📋 К заказам", callback_data="view_my_orders")]
    ])
    return keyboard
