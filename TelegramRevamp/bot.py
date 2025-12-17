import os
import asyncio
import contextlib
from typing import Any, Coroutine, Dict, Optional
from dotenv import load_dotenv
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.enums import ChatAction
from database import Database
try:
    from keyboards import *
except ModuleNotFoundError:
    import importlib
    import sys

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    globals().update(importlib.import_module("TelegramRevamp.keyboards").__dict__)
import logging

load_dotenv()
load_dotenv("telebot.env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
db = Database()

last_command_time: Dict[int, datetime] = {}
running_start_tasks: Dict[int, asyncio.Task] = {}


# Восстановленный обработчик команды /start с инлайн-кнопками
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    # Пример инлайн-клавиатуры (можно заменить на get_main_menu или другую функцию из keyboards.py)
    keyboard = get_main_menu() if 'get_main_menu' in globals() else None
    await message.answer(
        "Добро пожаловать! Выберите действие:",
        reply_markup=keyboard
    )


def _run_background(coro: Coroutine[Any, Any, Any], *, name: str) -> asyncio.Task:
    """Запускает корутину в фоне и логирует исключения."""
    task = asyncio.create_task(coro)

    def _done_callback(done_task: asyncio.Task):
        try:
            exc = done_task.exception()
        except asyncio.CancelledError:
            logger.debug(f"Фоновая задача '{name}' отменена")
            return
        if exc:
            logger.debug(f"Фоновая задача '{name}' завершилась с ошибкой: {exc}")

    task.add_done_callback(_done_callback)
    return task


async def _delete_user_message(chat_id: int, message_id: int):
    """Удаляет исходное сообщение пользователя, не блокируя /start."""
    with contextlib.suppress(asyncio.TimeoutError, Exception):
        await asyncio.wait_for(bot.delete_message(chat_id, message_id), timeout=1.5)


async def _cleanup_previous_bot_message(user_id: int, chat_id: int):
    """Удаляет предыдущее сообщение бота в чате, если оно есть."""
    if not db.is_connected():
        return
    try:
        last_bot_msg = await asyncio.wait_for(db.get_last_bot_message(user_id), timeout=1.0)
    except asyncio.TimeoutError:
        logger.debug("Таймаут при получении предыдущего сообщения бота")
        return
    except Exception as err:
        logger.debug(f"Ошибка получения предыдущего сообщения бота: {err}")
        return

    if not last_bot_msg or last_bot_msg.get('chat_id') != chat_id:
        return

    with contextlib.suppress(asyncio.TimeoutError, Exception):
        await asyncio.wait_for(
            bot.delete_message(chat_id, last_bot_msg['last_bot_message_id']),
            timeout=1.5,
        )

ADMIN_CODE = "4577"


def _days_since(dt: Optional[datetime]) -> int:
    """Безопасно считает количество дней с учётом часовых поясов."""
    if not dt:
        return 0
    if dt.tzinfo is None:
        now = datetime.utcnow()
    else:
        now = datetime.now(dt.tzinfo)
    try:
        diff = now - dt
        return max(diff.days, 0)
    except TypeError:
        # На случай смешения aware/naive дат приводим к UTC
        base = dt.replace(tzinfo=None)
        return max((datetime.utcnow() - base).days, 0)

class CreateOrder(StatesGroup):
    price = State()
    start_time = State()
    address = State()
    workers_count = State()
    comment = State()
    phone_number = State()
    confirmation = State()

class LeaveReview(StatesGroup):
    rating = State()
    comment = State()

class DeclineOrder(StatesGroup):
    reason = State()

class AdminBan(StatesGroup):
    reason = State()

class AdminMessage(StatesGroup):
    message = State()

class Broadcast(StatesGroup):
    message = State()

class AdminSearchUser(StatesGroup):
    waiting_username = State()

class AdminEditRating(StatesGroup):
    user_id = State()
    waiting_rating = State()

class AdminResetOrder(StatesGroup):
    user_id = State()

class Chat(StatesGroup):
    messaging = State()

class OrderFeed(StatesGroup):
    page = State()

class ViewReviews(StatesGroup):
    page = State()
    executor_id = State()

class Probiv(StatesGroup):
    waiting_username = State()

class ComplaintOrder(StatesGroup):
    waiting_order_id = State()
    waiting_description = State()

class ComplaintUser(StatesGroup):
    waiting_username = State()
    waiting_description = State()

class ComplaintIdea(StatesGroup):
    waiting_description = State()

class AdminResolveComplaint(StatesGroup):
    complaint_id = State()
    waiting_note = State()

class AdminSearchOrder(StatesGroup):
    waiting_order_id = State()

class AdminDeleteOrder(StatesGroup):
    waiting_order_id = State()

class TutorialSlides(StatesGroup):
    slide_number = State()

async def check_banned(user_id: int):
    user = await db.get_user(user_id)
    if user and user['is_banned']:
        return True
    return False

# ============================================
# СЛАЙДЫ ОБУЧЕНИЯ ДЛЯ КАЖДОЙ РОЛИ
# ============================================

def get_executor_slides():
    """Слайды обучения для исполнителей"""
    return [
        {
            "title": "📱 ЛЕНТА ЗАКАЗОВ",
            "description": (
                "Здесь отображаются все доступные заказы\n\n"
                "<b>Что вы видите:</b>\n"
                "💰 Цена заказа\n"
                "📍 Адрес работы\n"
                "📝 Описание задачи\n"
                "⭐ Рейтинг заказчика\n\n"
                "<b>Как использовать:</b>\n"
                "1️⃣ Нажимайте на интересующий заказ\n"
                "2️⃣ Прочитайте полные детали\n"
                "3️⃣ Если нравится - откликнитесь!\n"
                "4️⃣ Ждите ответа от заказчика"
            ),
            "button_highlight": "📱 Лента"
        },
        {
            "title": "📦 МОИ ЗАКАЗЫ",
            "description": (
                "Управляйте заказами, которые вы взяли\n\n"
                "<b>Здесь вы видите:</b>\n"
                "✅ Активные заказы (в процессе)\n"
                "⏳ Статус выполнения\n"
                "💬 Чат с заказчиком\n"
                "📊 Прогресс работы\n\n"
                "<b>Функции:</b>\n"
                "• Общайтесь с заказчиком в чате\n"
                "• Загружайте результаты работы\n"
                "• Отмечайте завершение заказа\n"
                "• Спрашивайте уточнения"
            ),
            "button_highlight": "📦 Мои заказы"
        },
        {
            "title": "👤 ПРОФИЛЬ",
            "description": (
                "Ваша карточка исполнителя для клиентов\n\n"
                "<b>Что показывает профиль:</b>\n"
                "⭐ Ваш рейтинг (0.0 - 5.0)\n"
                "🏆 Уровень (новичок → опытный → топ)\n"
                "📦 Количество выполненных заказов\n"
                "💰 Общий заработок\n"
                "📝 Отзывы от заказчиков\n\n"
                "<b>Совет:</b>\n"
                "Качественная работа → высокий рейтинг → больше заказов!"
            ),
            "button_highlight": "👤 Профиль"
        },
        {
            "title": "🏆 ТОП ИСПОЛНИТЕЛЕЙ",
            "description": (
                "Рейтинг лучших исполнителей платформы\n\n"
                "<b>Здесь вы видите:</b>\n"
                "🔥 Топ активных за последние 24 часа\n"
                "🥇🥈🥉 Топ 10 по рейтингу\n"
                "💪 Количество выполненных заказов\n"
                "⭐ Оценка от заказчиков\n\n"
                "<b>Зачем смотреть:</b>\n"
                "• Видеть, к чему стремиться\n"
                "• Понять требования рынка\n"
                "• Вдохновиться на улучшение"
            ),
            "button_highlight": "🏆 Топ"
        }
    ]

def get_customer_slides():
    """Слайды обучения для заказчиков"""
    return [
        {
            "title": "➕ СОЗДАТЬ ЗАКАЗ",
            "description": (
                "Разместите новый заказ и найдите исполнителя\n\n"
                "<b>Что указать:</b>\n"
                "💰 Бюджет (сумма, которую готовы заплатить)\n"
                "📅 Дата и время выполнения\n"
                "📍 Адрес работы\n"
                "👥 Сколько исполнителей нужно\n"
                "📝 Описание задачи (подробнее = лучше)\n\n"
                "<b>После публикации:</b>\n"
                "📬 Будете получать отклики\n"
                "👀 Выбирайте исполнителей по рейтингу\n"
                "💬 Общайтесь с ними в чате"
            ),
            "button_highlight": "➕ Создать заказ"
        },
        {
            "title": "📋 МОИ ЗАКАЗЫ",
            "description": (
                "Управляйте всеми опубликованными заказами\n\n"
                "<b>Что вы видите:</b>\n"
                "✅ Активные заказы (ищут исполнителей)\n"
                "📩 Список откликов от исполнителей\n"
                "⭐ Рейтинг и отзывы откликнувшихся\n"
                "💬 Чат для общения с исполнителем\n\n"
                "<b>Как выбрать:</b>\n"
                "1️⃣ Прочитайте все отклики\n"
                "2️⃣ Посмотрите рейтинг исполнителя\n"
                "3️⃣ Почитайте отзывы о нем\n"
                "4️⃣ Выберите лучшего"
            ),
            "button_highlight": "📋 Мои заказы"
        },
        {
            "title": "🏆 ТОП ИСПОЛНИТЕЛЕЙ",
            "description": (
                "Найдите лучших исполнителей платформы\n\n"
                "<b>Здесь вы видите:</b>\n"
                "🔥 Топ активных исполнителей за 24ч\n"
                "🥇🥈🥉 Рейтинг всех исполнителей\n"
                "⭐ Их оценка (0-5 звезд)\n"
                "📦 Количество выполненных заказов\n"
                "💬 Отзывы других заказчиков\n\n"
                "<b>Как использовать:</b>\n"
                "• Приглашайте топ исполнителей в свои заказы\n"
                "• Ищите специалистов по отзывам\n"
                "• Доверяйте опытным профессионалам"
            ),
            "button_highlight": "🏆 Топ"
        }
    ]

def get_tutorial_keyboard(current_slide: int, max_slides: int, is_back_button=True):
    """Клавиатура навигации по слайдам"""
    buttons = []
    
    # Кнопки навигации
    nav_buttons = []
    if current_slide > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"slide_prev_{current_slide}"))
    
    slide_indicator = InlineKeyboardButton(text=f"Слайд {current_slide + 1}/{max_slides}", callback_data="noop")
    nav_buttons.append(slide_indicator)
    
    if current_slide < max_slides - 1:
        nav_buttons.append(InlineKeyboardButton(text="Дальше ➡️", callback_data=f"slide_next_{current_slide}"))
    
    buttons.append(nav_buttons)
    buttons.append([InlineKeyboardButton(text="🏠 В меню", callback_data="faq_back_to_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def get_main_menu_text(user_id: int = None):
    """Возвращает текст главного меню в премиальном стиле"""
    current_role = "Заказчик"
    if user_id:
        user = await db.get_user(user_id)
        if user and user.get('user_role') == 'executor':
            current_role = "Исполнитель"
    
    # Дата запуска проекта и дни
    project_start = datetime(2025, 11, 15, tzinfo=ZoneInfo("UTC"))
    days_running = (datetime.now(ZoneInfo("UTC")) - project_start).days
    
    # Получаем количество пользователей
    users_count = 0
    try:
        users = await db.get_all_users(limit=1000)
        users_count = len(users)
    except Exception as e:
        logger.debug(f"Ошибка при получении пользователей: {e}")
        users_count = 0
    
    # Получаем топ лидеров по рейтингу
    leaderboard_text = ""
    try:
        top_rated = await db.get_leaderboard('executor', 2)
        if top_rated:
            for exec in top_rated:
                username = exec['username'] if exec['username'] else exec['first_name'] or 'Пользователь'
                leaderboard_text += f"• @{username} — ★ {exec['rating']:.2f}\n"
    except Exception as e:
        logger.debug(f"Ошибка при получении лидеров: {e}")
    
    return (
        "🎯 <b>Дашборд проекта</b>\n\n"
        f"👤 Роль: <i>{current_role}</i>\n"
        f"📆 Проекту: <code>{days_running} дней</code>\n"
        f"👥 Пользователей: <code>{users_count}</code>\n\n"
        "━━━━━━━━━━\n\n"
        "<b>🏆 Лидеры рейтинга (24ч)</b>\n"
        f"{leaderboard_text}"
            "━━━━━━━━━━\n\n"
            "\n"  # дополнительный отступ для симметрии
        "⚡️ <b>Быстрые действия</b>\n"
        "<i>/s</i> — сменить роль\n"
        "<i>/start</i> — обновить"
    )

async def delete_messages(chat_id: int, message_ids: list):
    """Удаляет список сообщений из чата"""
    for msg_id in message_ids:
        try:
            await bot.delete_message(chat_id, msg_id)
        except Exception as e:
            logger.debug(f"Не удалось удалить сообщение {msg_id}: {e}")
            pass

async def smart_send(user_id: int, chat_id: int, text: str, reply_markup=None, parse_mode="HTML", delete_user_msg_id: int = None):
    """
    Умная отправка сообщения: редактирует предыдущее сообщение бота или отправляет новое.
    Также удаляет сообщение пользователя если указан delete_user_msg_id.
    """
    if delete_user_msg_id:
        try:
            await bot.delete_message(chat_id, delete_user_msg_id)
        except Exception as e:
            logger.debug(f"Не удалось удалить сообщение пользователя {delete_user_msg_id}: {e}")
    
    last_msg = await db.get_last_bot_message(user_id)
    
    if last_msg and last_msg['chat_id'] == chat_id:
        try:
            await bot.edit_message_text(
                text=text,
                chat_id=chat_id,
                message_id=last_msg['last_bot_message_id'],
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
            await db.save_last_bot_message(user_id, last_msg['last_bot_message_id'], chat_id)
            return last_msg['last_bot_message_id']
        except Exception as e:
            logger.debug(f"Не удалось отредактировать сообщение: {e}")
            try:
                await bot.delete_message(chat_id, last_msg['last_bot_message_id'])
            except:
                pass
    
    sent_msg = await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
        parse_mode=parse_mode
    )
    await db.save_last_bot_message(user_id, sent_msg.message_id, chat_id)
    return sent_msg.message_id

async def smart_edit_or_send(callback: types.CallbackQuery, text: str, reply_markup=None, parse_mode="HTML"):
    """
    Для callback-запросов: редактирует текущее сообщение и сохраняет его как последнее.
    """
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
        await db.save_last_bot_message(user_id, callback.message.message_id, chat_id)
        return callback.message.message_id
    except Exception as e:
        logger.debug(f"Не удалось отредактировать сообщение: {e}")
        # Если не удалось отредактировать, просто логируем, но не удаляем сообщение
        return callback.message.message_id

async def delete_and_send(message: types.Message, text: str, reply_markup=None, parse_mode="HTML"):
    """
    Удаляет сообщение пользователя и отправляет/редактирует ответ бота.
    """
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    try:
        await message.delete()
    except Exception as e:
        logger.debug(f"Не удалось удалить сообщение пользователя: {e}")
    
    return await smart_send(user_id, chat_id, text, reply_markup, parse_mode)

async def get_customer_menu_with_counts(user_id: int):
    """Получает меню заказчика с количеством заказов"""
    orders = await db.get_customer_orders(user_id)
    active_orders = [o for o in orders if o['status'] not in ['completed', 'cancelled'] and not o.get('is_deleted', False)]
    return get_customer_menu(orders_count=len(active_orders))

async def get_executor_menu_with_counts(user_id: int):
    """Получает меню исполнителя с количеством заказов в ленте и своих заказов"""
    open_orders = await db.get_open_orders()
    my_orders = await db.get_executor_orders(user_id)
    active_my_orders = [o for o in my_orders if o['status'] not in ['completed', 'cancelled']]
    return get_executor_menu(feed_count=len(open_orders), my_orders_count=len(active_my_orders))

async def get_customer_orders_menu_with_counts(user_id: int):
    """Получает меню 'Мои заказы' заказчика с количеством активных и удалённых заказов"""
    orders = await db.get_customer_orders(user_id)
    deleted_orders = await db.get_deleted_orders(user_id)
    active_orders = [o for o in orders if o['status'] not in ['completed', 'cancelled'] and not o.get('is_deleted', False)]
    return get_customer_orders_menu(active_count=len(active_orders), deleted_count=len(deleted_orders))

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    # Очищаем состояние FSM
    await state.clear()
    
    # Удаляем последнее сообщение бота для очистки чата
    last_msg = await db.get_last_bot_message(message.from_user.id)
    if last_msg and last_msg['chat_id'] == message.chat.id:
        try:
            await bot.delete_message(message.chat.id, last_msg['last_bot_message_id'])
        except Exception as e:
            logger.debug(f"Не удалось удалить предыдущее сообщение бота: {e}")
    
    if await check_banned(message.from_user.id):
        await delete_and_send(message, "❌ Вы заблокированы в системе.")
        return
    
    await db.create_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )
    
    menu = await get_main_menu_with_role(message.from_user.id, db)
    text = await get_main_menu_text(message.from_user.id)
    await delete_and_send(
        message,
        text,
        reply_markup=menu,
        parse_mode="HTML"
    )

@dp.message(Command("s"))
async def switch_role(message: types.Message, state: FSMContext):
    """Команда /s для переключения роли без уведомления"""
    await state.clear()
    
    if await check_banned(message.from_user.id):
        await message.answer("❌ Вы заблокированы в системе.")
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    await db.create_user(user_id, message.from_user.username, message.from_user.first_name)
    
    user = await db.get_user(user_id)
    current_role = user.get('user_role', 'customer')
    
    logger.info(f"Текущая роль пользователя {user_id}: {current_role}")
    
    # Переключаем роль
    new_role = 'executor' if current_role == 'customer' else 'customer'
    await db.update_role(user_id, new_role)
    logger.info(f"Роль изменена на: {new_role}")
    
    # Удаляем команду пользователя
    try:
        await message.delete()
    except Exception as e:
        logger.debug(f"Не удалось удалить команду /s: {e}")
    
    # Получаем обновленное меню с новой ролью
    menu_text = await get_main_menu_text(user_id)
    kb = await get_main_menu_with_role(user_id, db)
    
    try:
        # Сначала пытаемся найти последнее сохраненное сообщение и отредактировать его
        last_msg = await db.get_last_bot_message(user_id)
        
        if last_msg:
            logger.info(f"Попытка редактирования сообщения {last_msg['last_bot_message_id']} в чате {last_msg['chat_id']}")
            try:
                await bot.edit_message_text(
                    text=menu_text,
                    chat_id=last_msg['chat_id'],
                    message_id=last_msg['last_bot_message_id'],
                    reply_markup=kb,
                    parse_mode="HTML"
                )
                logger.info(f"✅ Меню успешно отредактировано (ID: {last_msg['last_bot_message_id']})")
                return
            except Exception as edit_error:
                logger.error(f"❌ Не удалось отредактировать сообщение {last_msg['last_bot_message_id']}: {edit_error}")
        
        # Если редактирование не прошло или нет последнего сообщения, отправляем новое
        logger.info(f"Отправляем новое меню пользователю {user_id}")
        msg = await bot.send_message(chat_id, menu_text, reply_markup=kb, parse_mode="HTML")
        await db.save_last_bot_message(user_id, msg.message_id, chat_id)
        logger.info(f"✅ Новое меню отправлено: {msg.message_id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при обновлении меню: {e}", exc_info=True)

# ============================================
# УНИВЕРСАЛЬНЫЕ ОБРАБОТЧИКИ ДЛЯ КНОПОК В СОСТОЯНИЯХ
# ============================================

@dp.callback_query(F.data == "cancel")
async def cancel_handler(callback: types.CallbackQuery, state: FSMContext):
    """Универсальный обработчик для кнопки Отмена в состояниях"""
    current_state = await state.get_state()
    await state.clear()
    
    user = await db.get_user(callback.from_user.id)
    
    admin_states = [
        AdminBan.reason.state,
        AdminMessage.message.state,
        Broadcast.message.state,
        AdminSearchUser.waiting_username.state,
        AdminEditRating.user_id.state,
        AdminEditRating.waiting_rating.state,
        AdminResetOrder.user_id.state,
        AdminResolveComplaint.complaint_id.state,
        AdminResolveComplaint.waiting_note.state,
    ]
    
    complaint_states = [
        ComplaintOrder.waiting_order_id.state,
        ComplaintOrder.waiting_description.state,
        ComplaintUser.waiting_username.state,
        ComplaintUser.waiting_description.state,
        ComplaintIdea.waiting_description.state,
    ]
    
    # Если пользователь в состоянии жалобы - возвращаем в меню поддержки
    if current_state in complaint_states:
        await smart_edit_or_send(callback, "📞 <b>Центр обращений</b>\n\nВыберите тип обращения:", reply_markup=get_support_menu(), parse_mode="HTML")
    # Если пользователь в состоянии пробива - возвращаем в главное меню с полным текстом
    elif current_state == Probiv.waiting_username.state:
        main_menu_text = await get_main_menu_text(callback.from_user.id)
        await smart_edit_or_send(callback, main_menu_text, reply_markup=await get_main_menu_with_role(callback.from_user.id, db), parse_mode="HTML")
    elif user and user['is_admin'] and current_state in admin_states:
        await smart_edit_or_send(callback, "Отменено.", reply_markup=get_admin_menu())
    elif user and user['user_role'] == 'executor':
        await smart_edit_or_send(callback, "Отменено.", reply_markup=await get_executor_menu_with_counts(callback.from_user.id))
    else:
        await smart_edit_or_send(callback, "Отменено.", reply_markup=await get_customer_menu_with_counts(callback.from_user.id))
    
    await callback.answer("Отменено")

@dp.callback_query(F.data == "noop")
async def noop_handler(callback: types.CallbackQuery):
    """Обработчик для кнопок без действия (например, индикатор страницы)"""
    await callback.answer()

@dp.callback_query(F.data == "refresh_chat")
async def refresh_chat_handler(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик для кнопки Обновить чат - удаляет текущее сообщение и отправляет новое главное меню"""
    await state.clear()
    
    try:
        await callback.message.delete()
    except Exception as e:
        logger.debug(f"Не удалось удалить сообщение: {e}")
    
    sent_msg = await bot.send_message(
        callback.message.chat.id,
        await get_main_menu_text(callback.from_user.id),
        reply_markup=await get_main_menu_with_role(callback.from_user.id, db),
        parse_mode="HTML"
    )
    await db.save_last_bot_message(callback.from_user.id, sent_msg.message_id, callback.message.chat.id)
    await callback.answer("Обновлено")

@dp.callback_query(F.data == "skip")
async def skip_handler(callback: types.CallbackQuery, state: FSMContext):
    """Универсальный обработчик для кнопки Пропустить в состояниях"""
    current_state = await state.get_state()
    
    # Для CreateOrder.phone_number - пропускаем номер телефона
    if current_state == CreateOrder.phone_number:
        await state.update_data(phone_number=None)
        data = await state.get_data()
        
        text = f"📝 <b>Новый заказ:</b>\n\n"
        text += f"💰 Цена: {data['price']} ₽\n"
        text += f"⏰ Время: {data['start_time']}\n"
        text += f"📍 Адрес: {data['address']}\n"
        text += f"👥 Количество исполнителей: {data['workers_count']}\n"
        text += f"📝 Комментарий: {data['comment']}\n"
        
        await smart_edit_or_send(callback, text, reply_markup=get_confirm_order_keyboard(), parse_mode="HTML")
        await state.set_state(CreateOrder.confirmation)
        await callback.answer("Пропущено")
    else:
        await callback.answer("Функция 'Пропустить' не доступна на этом шаге", show_alert=True)

@dp.callback_query(F.data == "role_customer")
async def customer_role(callback: types.CallbackQuery, state: FSMContext):
    if await check_banned(callback.from_user.id):
        await callback.answer("❌ Вы заблокированы в системе.", show_alert=True)
        return
    
    await state.clear()
    
    await db.create_user(
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.first_name
    )
    
    await db.update_role(callback.from_user.id, 'customer')
    user = await db.get_user(callback.from_user.id)
    user_id = callback.from_user.id
    await db.ensure_customer_profile(user_id)
    
    days_in_project = _days_since(user['created_at'] if user else None)
    active_orders = await db.get_customer_orders(user_id)
    completed_orders = await db.get_customer_completed_orders(user_id)
    customer_rating = float(await db.get_customer_rating(user_id) or 0.0)
    
    text = "👤 <b>Режим Заказчика</b>\n"
    text += "━━━━━━━━━━━━━━━\n\n"
    text += f"📅 Дней в проекте: <b>{days_in_project}</b>\n"
    text += f"⭐ Ваш рейтинг: <b>{customer_rating:.1f}</b>\n\n"
    text += f"📊 <b>Ваша статистика:</b>\n"
    text += f"├ 📝 Активных заказов: <b>{len(active_orders)}</b>\n"
    text += f"└ ✅ Выполнено заказов: <b>{len(completed_orders)}</b>\n\n"
    text += "━━━━━━━━━━━━━━━\n"
    text += "💡 Создавайте заказы и находите исполнителей!"
    
    message_id = await smart_edit_or_send(
        callback,
        text,
        reply_markup=await get_customer_menu_with_counts(callback.from_user.id),
        parse_mode="HTML"
    )
    await db.save_last_bot_message(callback.from_user.id, message_id, callback.message.chat.id)
    await callback.answer()

@dp.callback_query(F.data == "role_executor")
async def executor_role(callback: types.CallbackQuery, state: FSMContext):
    if await check_banned(callback.from_user.id):
        await callback.answer("❌ Вы заблокированы в системе.", show_alert=True)
        return
    
    await state.clear()
    
    await db.create_user(
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.first_name
    )
    
    await db.update_role(callback.from_user.id, 'executor')
    user = await db.get_user(callback.from_user.id)
    user_id = callback.from_user.id
    await db.ensure_executor_profile(user_id)
    profile = await db.get_executor_profile(user_id)
    created_at = user['created_at'] if user else None
    days_in_project = _days_since(created_at)

    # Обнуляем показатели, если профиль ещё не заполнен
    rating = 0.0
    level = 'новичок'
    completed_total = 0
    if profile:
        rating = float(profile['rating']) if profile['rating'] is not None else 0.0
        level = profile['level'] or 'новичок'
        completed_total = profile['completed_orders'] or 0

    active_orders = await db.get_executor_orders(user_id)
    completed_orders = await db.get_executor_history(user_id)
    completed_only = [o for o in completed_orders if o['status'] == 'completed']

    total_earned = sum(float(order['price']) for order in completed_only if order['price'])

    text = "⚡ <b>Режим Исполнителя</b>\n"
    text += "━━━━━━━━━━━━━━━\n\n"
    text += f"📅 Дней в проекте: <b>{days_in_project}</b>\n"
    text += f"⭐ Ваш рейтинг: <b>{rating:.2f}</b>\n"
    text += f"🏆 Уровень: <b>{level}</b>\n\n"
    text += f"📊 <b>Ваша статистика:</b>\n"
    text += f"├ 📝 Активных заказов: <b>{len(active_orders)}</b>\n"
    text += f"├ ✅ Выполнено заказов: <b>{completed_total}</b>\n"
    text += f"└ 💰 Заработано: <b>{total_earned:,.0f} ₽</b>\n\n"
    text += "━━━━━━━━━━━━━━━\n"
    text += "💡 Берите заказы и зарабатывайте!"

    message_id = await smart_edit_or_send(
        callback,
        text,
        reply_markup=await get_executor_menu_with_counts(callback.from_user.id),
        parse_mode="HTML"
    )
    await db.save_last_bot_message(callback.from_user.id, message_id, callback.message.chat.id)
    await callback.answer()

@dp.callback_query(F.data == "probiv")
async def probiv_menu(callback: types.CallbackQuery, state: FSMContext):
    if await check_banned(callback.from_user.id):
        await callback.answer("❌ Вы заблокированы в системе.", show_alert=True)
        return
    
    await smart_edit_or_send(
        callback,
        "🔍 <b>ПРОБИВ ПОЛЬЗОВАТЕЛЯ</b>\n\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        "<b>Проверьте надежность партнера перед работой</b>\n\n"
        "Вы получите:\n"
        "⭐ Рейтинг (0.0-5.0)\n"
        "📦 Выполненные заказы\n"
        "💬 Все отзывы от других\n"
        "📊 История и уровень\n\n"
        "<i>Помогает избежать проблем и выбрать надежного партнера</i>\n\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        "Введите @username:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    
    await state.set_state(Probiv.waiting_username)
    await callback.answer()

@dp.message(Probiv.waiting_username)
async def probiv_check_user(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        main_menu_text = await get_main_menu_text(message.from_user.id)
        await delete_and_send(message, main_menu_text, reply_markup=await get_main_menu_with_role(message.from_user.id, db), parse_mode="HTML")
        return
    
    username = message.text.strip()
    if not username:
        await delete_and_send(message, "❌ Введите корректный @username")
        return
    
    # Показываем анимацию загрузки
    await message.bot.send_chat_action(message.chat.id, "typing")
    
    # Ищем пользователя
    user = await db.get_user_by_username(username)
    
    if not user:
        main_menu_text = await get_main_menu_text(message.from_user.id)
        error_text = f"❌ Пользователь {username} не найден в системе.\n\n{main_menu_text}"
        await delete_and_send(
            message,
            error_text,
            reply_markup=await get_main_menu_with_role(message.from_user.id, db),
            parse_mode="HTML"
        )
        await state.clear()
        return
    
    # Получаем профили и отзывы
    executor_profile = await db.get_executor_profile(user['user_id'])
    reviews = await db.get_reviews(user['user_id'])
    
    # Формируем информацию
    text = f"🔍 <b>Пробив пользователя @{user['username']}</b>\n\n"
    
    # Статистика исполнителя
    if executor_profile:
        text += f"⚡ <b>Как исполнитель:</b>\n"
        text += f"⭐ Рейтинг: {executor_profile['rating']}\n"
        text += f"📦 Выполнено заказов: {executor_profile['completed_orders']}\n"
        text += f"🏆 Уровень: {executor_profile['level']}\n\n"
    
    # Отзывы
    if reviews:
        text += f"💬 <b>Отзывы ({len(reviews)}):</b>\n\n"
        for review in reviews[:10]:  # Показываем последние 10
            reviewer = f"@{review['username']}" if review['username'] else review['first_name']
            text += f"Оценка: {review['rating']}/5\n"
            text += f"От: {reviewer}\n"
            if review['comment']:
                text += f"💬 {review['comment']}\n"
            review_date = review['created_at'].strftime("%d.%m.%Y")
            text += f"📅 {review_date}\n\n"
        
        if len(reviews) > 10:
            text += f"<i>Показано 10 из {len(reviews)} отзывов</i>\n"
    else:
        text += "💬 <b>Отзывов пока нет</b>\n"
    
    text += "\n" + "━━━━━━━━━━━━━━━━━" + "\n\n"
    main_menu_text = await get_main_menu_text(message.from_user.id)
    text += main_menu_text
    
    await delete_and_send(message, text, reply_markup=await get_main_menu_with_role(message.from_user.id, db), parse_mode="HTML")
    await state.clear()

async def notify_admins_about_complaint(complaint_id, complaint_type, target_id, description, user_id):
    """Отправляет уведомление всем админам о новой жалобе"""
    admins = await db.get_all_admins()
    
    if not admins:
        return
    
    # Получаем информацию о пользователе
    user = await db.get_user(user_id)
    username = f"@{user['username']}" if user and user['username'] else f"ID:{user_id}"
    
    # Форматируем время в МСК
    moscow_tz = ZoneInfo("Europe/Moscow")
    now_msk = datetime.now(moscow_tz)
    time_str = now_msk.strftime("%d.%m.%Y %H:%M МСК")
    
    # Формируем уведомление в зависимости от типа
    if complaint_type == 'idea':
        # Для идей - специальный формат
        notification = f"💡 <b>НОВАЯ ИДЕЯ #{complaint_id}</b>\n\n"
        notification += f"👤 <b>От пользователя:</b> {username}\n"
        notification += f"📅 <b>Дата:</b> {time_str}\n\n"
        notification += f"💬 <b>Текст идеи:</b>\n{description}"
    elif complaint_type == 'order':
        # Для жалоб на объявление
        notification = f"⚠️ <b>НОВАЯ ЖАЛОБА #{complaint_id}</b>\n\n"
        notification += f"📦 <b>Категория:</b> Жалоба на объявление\n\n"
        notification += f"👤 <b>От кого:</b> {username}\n"
        notification += f"📅 <b>Когда:</b> {time_str}\n\n"
        
        if target_id:
            notification += f"📦 <b>Объявление:</b> #{target_id}\n"
            # Получаем информацию о создателе объявления
            try:
                order = await db.get_order(int(target_id))
                if order:
                    customer = await db.get_user(order['customer_id'])
                    customer_username = f"@{customer['username']}" if customer and customer['username'] else f"ID:{order['customer_id']}"
                    notification += f"👤 <b>Создатель объявления:</b> {customer_username}\n\n"
                else:
                    notification += "\n"
            except (ValueError, TypeError):
                notification += "\n"
        
        notification += f"📝 <b>Причина жалобы:</b>\n{description}"
    elif complaint_type == 'user':
        # Для жалоб на пользователя
        notification = f"⚠️ <b>НОВАЯ ЖАЛОБА #{complaint_id}</b>\n\n"
        notification += f"👤 <b>Категория:</b> Жалоба на пользователя\n\n"
        notification += f"👤 <b>От кого:</b> {username}\n"
        notification += f"📅 <b>Когда:</b> {time_str}\n\n"
        
        if target_id:
            target_user = await db.get_user(int(target_id))
            target_username = f"@{target_user['username']}" if target_user and target_user['username'] else f"ID:{target_id}"
            notification += f"🚫 <b>На пользователя:</b> {target_username}\n\n"
        
        notification += f"📝 <b>Причина жалобы:</b>\n{description}"
    else:
        # Общий формат для остальных типов
        notification = f"🔔 <b>НОВОЕ ОБРАЩЕНИЕ #{complaint_id}</b>\n\n"
        notification += f"👤 <b>От кого:</b> {username}\n"
        notification += f"📅 <b>Когда:</b> {time_str}\n\n"
        notification += f"📝 <b>Описание:</b>\n{description}"
    
    # Отправляем уведомления админам с включенными уведомлениями о жалобах
    for admin in admins:
        try:
            settings = await db.get_admin_notification_settings(admin['user_id'])
            # Проверяем режим спокойствия И настройки уведомлений о жалобах
            if settings and not settings['quiet_mode'] and settings['complaints_notifications']:
                await bot.send_message(
                    admin['user_id'],
                    notification,
                    reply_markup=get_admin_complaint_notification_keyboard(complaint_id),
                    parse_mode="HTML"
                )
        except Exception as e:
            logging.error(f"Failed to send complaint notification to admin {admin['user_id']}: {e}")

async def notify_admins_about_suspicious_order(order_id, risk_score, matched_patterns, user_id, order_text):
    """Отправляет уведомление всем админам о подозрительном заказе"""
    admins = await db.get_all_admins()
    
    if not admins:
        return
    
    # Получаем информацию о пользователе
    user = await db.get_user(user_id)
    username = f"@{user['username']}" if user and user['username'] else f"ID:{user_id}"
    
    # Проверяем возраст аккаунта
    user_status = ""
    if user and 'created_at' in user.keys() and user['created_at']:
        from datetime import timedelta
        user_age = datetime.now() - user['created_at']
        if user_age < timedelta(hours=48):
            user_status = " 🆕 <b>НОВЫЙ ПОЛЬЗОВАТЕЛЬ</b> (менее 48 часов)"
        elif user_age < timedelta(hours=168):
            user_status = " ⚠️ <b>Молодой аккаунт</b> (менее 7 дней)"
    
    # Форматируем время в МСК
    moscow_tz = ZoneInfo("Europe/Moscow")
    now_msk = datetime.now(moscow_tz)
    time_str = now_msk.strftime("%d.%m.%Y %H:%M МСК")
    
    notification = f"⚠️ <b>ПОДОЗРИТЕЛЬНОЕ ОБЪЯВЛЕНИЕ #{order_id}</b>\n\n"
    notification += f"🚨 <b>Уровень риска:</b> {risk_score} баллов\n\n"
    notification += f"👤 <b>Автор:</b> {username}{user_status}\n"
    notification += f"📅 <b>Когда:</b> {time_str}\n\n"
    
    if matched_patterns:
        notification += f"🔍 <b>Найденные паттерны:</b>\n"
        for pattern in matched_patterns:
            notification += f"  • {pattern}\n"
        notification += "\n"
    
    notification += f"📝 <b>Текст объявления:</b>\n{order_text[:200]}"
    if len(order_text) > 200:
        notification += "..."
    
    # Отправляем уведомления админам с включенными уведомлениями о подозрительных заказах
    for admin in admins:
        try:
            settings = await db.get_admin_notification_settings(admin['user_id'])
            # Проверяем режим спокойствия И настройки уведомлений о подозрительных заказах
            if settings and not settings['quiet_mode'] and settings['suspicious_orders_notifications']:
                await bot.send_message(
                    admin['user_id'],
                    notification,
                    reply_markup=get_admin_suspicious_notification_keyboard(),
                    parse_mode="HTML"
                )
        except Exception as e:
            logging.error(f"Failed to send suspicious order notification to admin {admin['user_id']}: {e}")

async def notify_executors_about_new_order(order_id, customer_id, price, start_time, address, workers_count, comment):
    """Отправляет уведомление всем исполнителям о новом заказе"""
    executors = await db.get_all_executors()
    
    if not executors:
        return
    
    customer = await db.get_user(customer_id)
    customer_username = f"@{customer['username']}" if customer and customer['username'] else "не указан"
    customer_rating = await db.get_customer_rating(customer_id)
    
    notification = f"🔔 <b>Новый заказ #{order_id}!</b>\n\n"
    notification += f"👤 Заказчик: {customer_username}\n"
    notification += f"⭐ Рейтинг заказчика: {customer_rating:.1f}\n\n"
    notification += f"💰 Оплата: <b>{price} ₽</b>\n"
    notification += f"⏰ Время: {start_time}\n"
    notification += f"📍 Адрес: {address}\n"
    notification += f"👥 Нужно исполнителей: {workers_count}\n"
    notification += f"📝 Описание: {comment[:150]}"
    if len(comment) > 150:
        notification += "..."
    
    for executor in executors:
        if executor['user_id'] == customer_id:
            continue
        try:
            is_hidden = await db.is_order_hidden(executor['user_id'], order_id)
            if not is_hidden:
                await bot.send_message(
                    executor['user_id'],
                    notification,
                    reply_markup=get_new_order_notification_keyboard(order_id),
                    parse_mode="HTML"
                )
        except Exception as e:
            logging.error(f"Failed to send order notification to executor {executor['user_id']}: {e}")

@dp.callback_query(F.data == "go_to_admin_panel")
async def go_to_admin_panel(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or not user['is_admin']:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    new_count = await db.get_complaints_count('new')
    resolved_count = await db.get_complaints_count('resolved')
    
    await smart_edit_or_send(
        callback,
        "⚠️ <b>Жалобы / обращения</b>\n"
        "─────────────\n"
        f"📥 Новых: {new_count}\n"
        f"✅ Решённых: {resolved_count}\n\n"
        "Выберите действие:",
        reply_markup=get_admin_complaints_menu(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "go_to_suspicious_orders")
async def go_to_suspicious_orders(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or not user['is_admin']:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    suspicious = await db.get_suspicious_orders(min_risk_score=4)
    logging.info(f"DEBUG: suspicious = {suspicious}, len = {len(suspicious) if suspicious else 0}")
    
    if not suspicious:
        await smart_edit_or_send(
            callback,
            "📭 <b>Подозрительных объявлений нет</b>",
            reply_markup=get_admin_menu(),
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    text = f"🚨 <b>Подозрительные объявления ({len(suspicious)})</b>\n"
    text += "━━━━━━━━━━━━━━━━━\n\n"
    
    keyboard_buttons = []
    for i, order in enumerate(suspicious[:10]):
        try:
            customer = await db.get_user(order['customer_id'])
            customer_username = f"@{customer['username']}" if customer and customer['username'] else "ID"
            risk_emoji = "🔴" if order['risk_score'] >= 8 else "🟡" if order['risk_score'] >= 5 else "🟢"
            button_text = f"{risk_emoji} #{order['order_id']} | {customer_username} | {order['risk_score']}р"
            keyboard_buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"view_susp_{order['order_id']}")])
            text += f"{risk_emoji} <b>#{order['order_id']}</b> - {customer_username}\n"
        except Exception as e:
            logging.error(f"Error processing order {order.get('order_id')}: {e}")
    
    keyboard_buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="go_to_admin_panel")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    if len(suspicious) > 10:
        text += f"\n<i>Показано 10 из {len(suspicious)}</i>"
    
    text += "\n\nВыберите объявление для действия:"
    
    await smart_edit_or_send(
        callback,
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("view_susp_"))
async def view_suspicious_order(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    order = await db.get_order(order_id)
    
    if not order:
        await callback.answer("❌ Объявление не найдено", show_alert=True)
        return
    
    customer = await db.get_user(order['customer_id'])
    customer_username = f"@{customer['username']}" if customer and customer['username'] else "не указан"
    
    susp = await db.get_suspicious_orders(min_risk_score=0)
    susp_order = next((o for o in susp if o['order_id'] == order_id), None)
    
    text = f"🔍 <b>ПОДОЗРИТЕЛЬНОЕ ОБЪЯВЛЕНИЕ #{order_id}</b>\n\n"
    text += f"━━━━━━━━━━━━━━━━━\n\n"
    text += f"👤 <b>Автор:</b> {customer_username}\n"
    text += f"🚨 <b>Риск:</b> {susp_order['risk_score'] if susp_order else 0} баллов\n"
    text += f"📌 <b>Паттерны:</b> {susp_order['matched_patterns'] if susp_order else 'нет'}\n\n"
    text += f"━━━━━━━━━━━━━━━━━\n\n"
    text += f"💰 <b>Цена:</b> {order['price']} ₽\n"
    text += f"⏰ <b>Время:</b> {order['start_time']}\n"
    text += f"📍 <b>Адрес:</b> {order['address']}\n"
    text += f"👥 <b>Исполнителей:</b> {order['workers_count']}\n\n"
    text += f"📝 <b>Описание:</b>\n{order['comment']}\n\n"
    text += f"━━━━━━━━━━━━━━━━━\n\n"
    text += "<b>Выберите действие:</b>"
    
    await smart_edit_or_send(
        callback,
        text,
        reply_markup=get_suspicious_order_keyboard(order_id),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("ban_user_susp_"))
async def ban_user_suspicious(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[3])
    order = await db.get_order(order_id)
    
    if order:
        await db.ban_user(order['customer_id'], "Подозрительное объявление (автобан)")
        await db.delete_order(order_id)
        await callback.message.edit_text(
            "✅ <b>Пользователь забанен и объявление удалено</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="go_to_suspicious_orders")]]),
            parse_mode="HTML"
        )
    await callback.answer()

@dp.callback_query(F.data.startswith("delete_order_susp_"))
async def delete_order_suspicious(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[3])
    await db.delete_order(order_id)
    
    await callback.message.edit_text(
        "✅ <b>Объявление удалено</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="go_to_suspicious_orders")]]),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("feed_ban_susp_"))
async def feed_ban_suspicious(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[3])
    order = await db.get_order(order_id)
    
    if order:
        await db.ban_user(order['customer_id'], "Запрет выкладываться в ленту (автобан)")
        await db.delete_order(order_id)
        
        await callback.message.edit_text(
            "✅ <b>Пользователь забанен от ленты и объявление удалено</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="go_to_suspicious_orders")]]),
            parse_mode="HTML"
        )
    await callback.answer()

@dp.callback_query(F.data == "support_center")
async def support_center(callback: types.CallbackQuery, state: FSMContext):
    if await check_banned(callback.from_user.id):
        await callback.answer("❌ Вы заблокированы в системе.", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📞 <b>Центр обращений</b>\n\n"
        "Выберите тип обращения:\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>⚠️ Жалоба на объявление</b>\n"
        "Укажите номер заказа, который нарушает правила\n\n"
        "<b>🚫 Жалоба на пользователя</b>\n"
        "Укажите его никнейм и опишите проблему\n\n"
        "<b>💡 Идея</b>\n"
        "Предложите улучшение платформы",
        reply_markup=get_support_menu(),
        parse_mode="HTML"
    )
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer()

@dp.callback_query(F.data == "complaint_order")
async def complaint_order_start(callback: types.CallbackQuery, state: FSMContext):
    if await check_banned(callback.from_user.id):
        await callback.answer("❌ Вы заблокированы в системе.", show_alert=True)
        return
    
    await smart_edit_or_send(
        callback,
        "⚠️ <b>Жалоба на объявление</b>\n\n"
        "Введите номер объявления, на которое хотите пожаловаться:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(ComplaintOrder.waiting_order_id)
    await callback.answer()

@dp.message(ComplaintOrder.waiting_order_id)
async def complaint_order_id(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await delete_and_send(message, "Отменено.", reply_markup=get_support_menu())
        return
    
    try:
        order_id = int(message.text.strip())
    except:
        await delete_and_send(message, "❌ Введите корректный номер объявления (число)")
        return
    
    order = await db.get_order(order_id)
    if not order:
        await delete_and_send(message, "❌ Объявление не найдено")
        return
    
    await state.update_data(order_id=str(order_id))
    await delete_and_send(
        message,
        f"📦 <b>Объявление #{order_id}</b>\n\n"
        f"Опишите причину жалобы:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(ComplaintOrder.waiting_description)

@dp.message(ComplaintOrder.waiting_description)
async def complaint_order_description(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await delete_and_send(message, "Отменено.", reply_markup=get_support_menu())
        return
    
    data = await state.get_data()
    order_id = data['order_id']
    description = message.text.strip()
    
    complaint_id = await db.create_complaint(
        user_id=message.from_user.id,
        complaint_type='order',
        target_id=order_id,
        description=description
    )
    
    # Уведомляем всех админов о новой жалобе
    await notify_admins_about_complaint(
        complaint_id=complaint_id,
        complaint_type='order',
        target_id=order_id,
        description=description,
        user_id=message.from_user.id
    )
    
    await delete_and_send(
        message,
        f"✅ <b>Жалоба #{complaint_id} принята</b>\n\n"
        f"Ваша жалоба на объявление #{order_id} отправлена администрации.\n"
        f"Мы рассмотрим её в ближайшее время.",
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )
    await state.clear()

@dp.callback_query(F.data == "complaint_user")
async def complaint_user_start(callback: types.CallbackQuery, state: FSMContext):
    if await check_banned(callback.from_user.id):
        await callback.answer("❌ Вы заблокированы в системе.", show_alert=True)
        return
    
    await smart_edit_or_send(
        callback,
        "🚫 <b>Жалоба на пользователя</b>\n\n"
        "Введите @username пользователя, на которого хотите пожаловаться:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(ComplaintUser.waiting_username)
    await callback.answer()

@dp.message(ComplaintUser.waiting_username)
async def complaint_user_username(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await delete_and_send(message, "Отменено.", reply_markup=get_support_menu())
        return
    
    username = message.text.strip().replace('@', '')
    user = await db.get_user_by_username(username)
    
    if not user:
        await delete_and_send(message, f"❌ Пользователь @{username} не найден в системе")
        return
    
    await state.update_data(target_user_id=str(user['user_id']))
    await delete_and_send(
        message,
        f"👤 <b>@{username}</b>\n\n"
        f"Опишите причину жалобы:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(ComplaintUser.waiting_description)

@dp.message(ComplaintUser.waiting_description)
async def complaint_user_description(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await delete_and_send(message, "Отменено.", reply_markup=get_support_menu())
        return
    
    data = await state.get_data()
    target_user_id = data['target_user_id']
    description = message.text.strip()
    
    complaint_id = await db.create_complaint(
        user_id=message.from_user.id,
        complaint_type='user',
        target_id=target_user_id,
        description=description
    )
    
    # Уведомляем всех админов о новой жалобе
    await notify_admins_about_complaint(
        complaint_id=complaint_id,
        complaint_type='user',
        target_id=target_user_id,
        description=description,
        user_id=message.from_user.id
    )
    
    await delete_and_send(
        message,
        f"✅ <b>Жалоба #{complaint_id} принята</b>\n\n"
        f"Ваша жалоба на пользователя отправлена администрации.\n"
        f"Мы рассмотрим её в ближайшее время.",
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )
    await state.clear()

@dp.callback_query(F.data == "suggest_idea")
async def complaint_idea_start(callback: types.CallbackQuery, state: FSMContext):
    if await check_banned(callback.from_user.id):
        await callback.answer("❌ Вы заблокированы в системе.", show_alert=True)
        return
    
    await smart_edit_or_send(
        callback,
        "💡 <b>Предложить идею</b>\n\n"
        "Опишите вашу идею по улучшению платформы:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(ComplaintIdea.waiting_description)
    await callback.answer()

@dp.message(ComplaintIdea.waiting_description)
async def complaint_idea_description(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await delete_and_send(message, "Отменено.", reply_markup=get_support_menu())
        return
    
    description = message.text.strip()
    
    complaint_id = await db.create_complaint(
        user_id=message.from_user.id,
        complaint_type='idea',
        target_id=None,
        description=description
    )
    
    # Уведомляем всех админов о новой идее
    await notify_admins_about_complaint(
        complaint_id=complaint_id,
        complaint_type='idea',
        target_id=None,
        description=description,
        user_id=message.from_user.id
    )
    
    await delete_and_send(
        message,
        f"✅ <b>Идея #{complaint_id} принята</b>\n\n"
        f"Спасибо за ваше предложение!\n"
        f"Мы обязательно его рассмотрим.",
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )
    await state.clear()

# REMOVED: Text handler replaced by inline keyboard navigation
# Users can switch roles by going to main menu and selecting a role
# @dp.message(F.text == "🔄 Сменить роль")
# async def switch_role(message: types.Message, state: FSMContext):
#     if await check_banned(message.from_user.id):
#         await message.answer("❌ Вы заблокированы в системе.")
#         return
#     
#     # Удаляем сообщение пользователя
#     try:
#         await message.delete()
#     except:
#         pass
#     
#     # Очищаем сохраненные сообщения при смене роли
#     await state.clear()
#     
#     user = await db.get_user(message.from_user.id)
#     if user['user_role'] == 'customer':
#         await db.update_role(message.from_user.id, 'executor')
#         await message.answer("✅ Роль изменена на Исполнителя", reply_markup=get_executor_menu())
#     else:
#         await db.update_role(message.from_user.id, 'customer')
#         await message.answer("✅ Роль изменена на Заказчика", reply_markup=get_customer_menu())

# REMOVED: Text handler replaced by callback handler "my_profile"
# @dp.message(F.text == "⚙️ Профиль / Настройки")
# async def profile(message: types.Message):
#     if await check_banned(message.from_user.id):
#         await message.answer("❌ Вы заблокированы в системе.")
#         return
#     
#     # Удаляем сообщение пользователя
#     try:
#         await message.delete()
#     except:
#         pass
#     
#     user = await db.get_user(message.from_user.id)
#     profile = await db.get_executor_profile(message.from_user.id)
#     reviews = await db.get_reviews(message.from_user.id)
#     days_in_project = (datetime.now() - user['created_at']).days
#     
#     text = f"👤 <b>Ваш профиль</b>\n\n"
#     text += f"Имя: {user['first_name']}\n"
#     text += f"Username: @{user['username'] or 'нет'}\n"
#     text += f"📅 Дней в проекте: {days_in_project}\n"
#     text += f"Текущая роль: {user['user_role']}\n\n"
#     text += f"⭐ Рейтинг: {profile['rating']}\n"
#     text += f"📦 Выполнено заказов: {profile['completed_orders']}\n"
#     text += f"🏆 Уровень: {profile['level']}\n"
#     text += f"💬 Отзывов: {len(reviews)}"
#     
#     await message.answer(text, parse_mode="HTML")

@dp.callback_query(F.data == "create_order")
async def create_order_start(callback: types.CallbackQuery, state: FSMContext):
    if await check_banned(callback.from_user.id):
        await callback.answer("❌ Вы заблокированы в системе.", show_alert=True)
        return
    
    await smart_edit_or_send(
        callback,
        "📝 <b>Создание заказа</b>\n\n"
        "Введите цену за заказ (в рублях):",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(CreateOrder.price)
    await callback.answer()

@dp.message(CreateOrder.price)
async def create_order_price(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await delete_and_send(message, "Отменено.", reply_markup=await get_customer_menu_with_counts(message.from_user.id))
        return
    
    try:
        price = float(message.text)
        if price <= 0:
            raise ValueError
    except:
        await delete_and_send(message, "❌ Неверный формат. Введите цену числом (например: 500)")
        return
    
    await state.update_data(price=price)
    await delete_and_send(message, "⏰ К какому времени нужно быть на объекте?\n(Например: 10:00, 14:30, Сегодня в 15:00, Завтра к 9:00)")
    await state.set_state(CreateOrder.start_time)

@dp.message(CreateOrder.start_time)
async def create_order_start_time(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await delete_and_send(message, "Отменено.", reply_markup=await get_customer_menu_with_counts(message.from_user.id))
        return
    
    await state.update_data(start_time=message.text)
    await delete_and_send(message, "📍 Введите адрес, где нужно выполнить работу:")
    await state.set_state(CreateOrder.address)

@dp.message(CreateOrder.address)
async def create_order_address(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await delete_and_send(message, "Отменено.", reply_markup=await get_customer_menu_with_counts(message.from_user.id))
        return
    
    await state.update_data(address=message.text)
    await delete_and_send(message, "Сколько исполнителей нужно?")
    await state.set_state(CreateOrder.workers_count)

@dp.message(CreateOrder.workers_count)
async def create_order_workers(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await delete_and_send(message, "Отменено.", reply_markup=await get_customer_menu_with_counts(message.from_user.id))
        return
    
    try:
        workers_count = int(message.text)
        if workers_count < 1:
            raise ValueError
    except:
        await delete_and_send(message, "❌ Неверный формат. Введите число от 1 и выше")
        return
    
    await state.update_data(workers_count=workers_count)
    await delete_and_send(message, "Добавьте комментарий к заказу (что нужно сделать):")
    await state.set_state(CreateOrder.comment)

@dp.message(CreateOrder.comment)
async def create_order_comment(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await delete_and_send(message, "Отменено.", reply_markup=await get_customer_menu_with_counts(message.from_user.id))
        return
    
    await state.update_data(comment=message.text)
    await delete_and_send(
        message,
        "📞 <b>Введите номер телефона для связи</b>\n\n"
        "ℹ️ Номер телефона увидит только тот исполнитель, которого вы примите на заказ.\n\n"
        "Можно пропустить, нажав ⏭️ Пропустить",
        reply_markup=get_skip_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(CreateOrder.phone_number)

@dp.message(CreateOrder.phone_number)
async def create_order_phone(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await delete_and_send(message, "Отменено.", reply_markup=await get_customer_menu_with_counts(message.from_user.id))
        return
    
    if message.text == "⏭️ Пропустить":
        await state.update_data(phone_number=None)
    else:
        await state.update_data(phone_number=message.text)
    
    data = await state.get_data()
    
    text = f"📝 <b>Новый заказ:</b>\n\n"
    text += f"💰 Цена: {data['price']} ₽\n"
    text += f"⏰ Время: {data['start_time']}\n"
    text += f"📍 Адрес: {data['address']}\n"
    text += f"👥 Количество исполнителей: {data['workers_count']}\n"
    text += f"📝 Комментарий: {data['comment']}\n"
    if data.get('phone_number'):
        text += f"📞 Телефон: {data['phone_number']}\n"
    
    await delete_and_send(message, text, reply_markup=get_confirm_order_keyboard(), parse_mode="HTML")
    await state.set_state(CreateOrder.confirmation)

@dp.callback_query(F.data == "confirm_order_publish")
async def publish_order(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    
    order_id = await db.create_order(
        callback.from_user.id,
        data['price'],
        data['start_time'],
        data['address'],
        data['workers_count'],
        data['comment'],
        data.get('phone_number')
    )
    
    await db.update_customer_stats(callback.from_user.id)
    
    # Проверяем контент на подозрительность с УМНОЙ МОДЕРАЦИЕЙ
    check_text = f"{data['comment']} {data['address']}"
    
    # Получаем глобальную настройку чувствительности системы
    sensitivity = await db.get_moderation_sensitivity()
    
    risk_score, matched_patterns, threshold = await db.check_order_content_smart(
        data['comment'], 
        float(data['price']), 
        data['address'],
        callback.from_user.id,
        sensitivity
    )
    
    # Логируем результат модерации
    await db.log_moderation(order_id, risk_score, matched_patterns)
    
    # Если заказ подозрительный (превышает порог чувствительности), уведомляем админов
    if risk_score >= threshold:
        await notify_admins_about_suspicious_order(order_id, risk_score, matched_patterns, callback.from_user.id, check_text)
    
    # Уведомляем всех исполнителей о новом заказе
    await notify_executors_about_new_order(
        order_id,
        callback.from_user.id,
        data['price'],
        data['start_time'],
        data['address'],
        data['workers_count'],
        data['comment']
    )
    
    await callback.message.edit_text(
        f"✅ <b>Заказ #{order_id} опубликован!</b>\n\n"
        f"🔔 Ожидайте откликов от исполнителей!",
        parse_mode="HTML"
    )
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await smart_edit_or_send(callback, "Возвращаю в меню...", reply_markup=await get_customer_menu_with_counts(callback.from_user.id))
    await state.clear()
    await callback.answer()

@dp.callback_query(F.data == "confirm_order_cancel")
async def cancel_order_creation(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Создание заказа отменено.")
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await smart_edit_or_send(callback, "Возвращаю в меню...", reply_markup=await get_customer_menu_with_counts(callback.from_user.id))
    await callback.answer()

@dp.callback_query(F.data.startswith("notify_take_"))
async def notify_take_order(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    order = await db.get_order(order_id)
    
    if not order or order['status'] != 'open':
        await callback.message.edit_text(
            "❌ <b>Этот заказ уже недоступен.</b>\n\n"
            "Возможно, его взял другой исполнитель или заказчик отменил заказ.",
            reply_markup=get_back_to_feed_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    await callback.message.edit_text(
        "❓ <b>Вы действительно хотите взять этот заказ?</b>\n\n"
        "После подтверждения заказчик увидит ваш отклик.",
        reply_markup=get_confirm_take_order_keyboard(order_id),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("confirm_notify_take_"))
async def confirm_notify_take_order(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[3])
    order = await db.get_order(order_id)
    
    if not order or order['status'] != 'open':
        await callback.message.edit_text(
            "❌ <b>Этот заказ уже недоступен.</b>\n\n"
            "Возможно, его взял другой исполнитель или заказчик отменил заказ.",
            reply_markup=get_back_to_feed_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    existing = await db.get_response_by_executor(order_id, callback.from_user.id)
    if existing:
        await callback.message.edit_text(
            "ℹ️ <b>Вы уже откликнулись на этот заказ.</b>\n\n"
            "Ожидайте ответа от заказчика.",
            reply_markup=get_action_result_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    await db.create_response(order_id, callback.from_user.id, "Хочу взять заказ")
    
    executor = await db.get_user(callback.from_user.id)
    executor_profile = await db.get_executor_profile(callback.from_user.id)
    
    customer_text = f"📬 <b>Новый отклик на заказ #{order_id}!</b>\n\n"
    customer_text += f"👷 Исполнитель: @{executor['username'] or 'не указан'}\n"
    customer_text += f"⭐ Рейтинг: {executor_profile['rating'] if executor_profile else 0}\n"
    customer_text += f"📦 Выполнено заказов: {executor_profile['completed_orders'] if executor_profile else 0}\n"
    
    try:
        await bot.send_message(
            order['customer_id'],
            customer_text,
            reply_markup=get_executor_actions(None, callback.from_user.id, order_id),
            parse_mode="HTML"
        )
    except:
        pass
    
    await callback.message.edit_text(
        f"✅ <b>Вы откликнулись на заказ #{order_id}!</b>\n\n"
        "Ожидайте ответа от заказчика.\n\n"
        "Выберите следующее действие:",
        reply_markup=get_action_result_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("cancel_notify_take_"))
async def cancel_notify_take_order(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[3])
    order = await db.get_order(order_id)
    
    if not order:
        await callback.message.edit_text("❌ Заказ не найден.")
        await callback.answer()
        return
    
    customer = await db.get_user(order['customer_id'])
    customer_username = f"@{customer['username']}" if customer and customer['username'] else "не указан"
    customer_rating = await db.get_customer_rating(order['customer_id'])
    
    notification = f"🔔 <b>Заказ #{order_id}</b>\n\n"
    notification += f"👤 Заказчик: {customer_username}\n"
    notification += f"⭐ Рейтинг заказчика: {customer_rating:.1f}\n\n"
    notification += f"💰 Оплата: <b>{order['price']} ₽</b>\n"
    notification += f"⏰ Время: {order['start_time']}\n"
    notification += f"📍 Адрес: {order['address']}\n"
    notification += f"👥 Нужно исполнителей: {order['workers_count']}\n"
    notification += f"📝 Описание: {order['comment'][:150]}"
    if len(order['comment']) > 150:
        notification += "..."
    
    await callback.message.edit_text(
        notification,
        reply_markup=get_new_order_notification_keyboard(order_id),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("notify_hide_"))
async def notify_hide_order(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    
    await callback.message.edit_text(
        "❓ <b>Вы действительно хотите скрыть этот заказ из своей ленты?</b>\n\n"
        "Вы больше не будете видеть этот заказ.",
        reply_markup=get_confirm_hide_order_keyboard(order_id),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("confirm_notify_hide_"))
async def confirm_notify_hide_order(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[3])
    
    await db.hide_order_for_user(callback.from_user.id, order_id)
    
    await callback.message.edit_text(
        "✅ <b>Заказ скрыт!</b>\n\n"
        "Вы больше не будете видеть этот заказ в своей ленте.\n\n"
        "Выберите следующее действие:",
        reply_markup=get_back_to_feed_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("cancel_notify_hide_"))
async def cancel_notify_hide_order(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[3])
    order = await db.get_order(order_id)
    
    if not order:
        await callback.message.edit_text("❌ Заказ не найден.")
        await callback.answer()
        return
    
    customer = await db.get_user(order['customer_id'])
    customer_username = f"@{customer['username']}" if customer and customer['username'] else "не указан"
    customer_rating = await db.get_customer_rating(order['customer_id'])
    
    notification = f"🔔 <b>Заказ #{order_id}</b>\n\n"
    notification += f"👤 Заказчик: {customer_username}\n"
    notification += f"⭐ Рейтинг заказчика: {customer_rating:.1f}\n\n"
    notification += f"💰 Оплата: <b>{order['price']} ₽</b>\n"
    notification += f"⏰ Время: {order['start_time']}\n"
    notification += f"📍 Адрес: {order['address']}\n"
    notification += f"👥 Нужно исполнителей: {order['workers_count']}\n"
    notification += f"📝 Описание: {order['comment'][:150]}"
    if len(order['comment']) > 150:
        notification += "..."
    
    await callback.message.edit_text(
        notification,
        reply_markup=get_new_order_notification_keyboard(order_id),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "my_orders")
async def my_orders_callback(callback: types.CallbackQuery, state: FSMContext):
    if await check_banned(callback.from_user.id):
        await callback.answer("❌ Вы заблокированы в системе.", show_alert=True)
        return
    
    orders = await db.get_customer_orders(callback.from_user.id)
    
    if not orders:
        await callback.message.edit_text("📭 У вас нет активных заказов.", reply_markup=await get_customer_orders_menu_with_counts(callback.from_user.id))
        await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
        await callback.answer()
        return
    
    await state.update_data(customer_orders_page=0)
    await show_customer_order_card(callback.message, callback.from_user.id, 0, orders)
    await callback.answer()

async def show_customer_order_card(message, user_id: int, page: int, orders: list = None):
    if orders is None:
        orders = await db.get_customer_orders(user_id)
    
    if not orders:
        await message.edit_text("📭 У вас нет активных заказов.", reply_markup=await get_customer_orders_menu_with_counts(user_id))
        await db.save_last_bot_message(user_id, message.message_id, message.chat.id)
        return
    
    total_pages = len(orders)
    if page < 0:
        page = 0
    if page >= total_pages:
        page = total_pages - 1
    
    order = orders[page]
    responses = await db.get_responses(order['order_id'])
    
    status_emoji = {"open": "🆕", "assigned": "✅", "in_progress": "⏳", "completed": "✔️"}
    status_text = {"open": "Открыт", "assigned": "Назначен", "in_progress": "В работе", "completed": "Выполнен"}
    
    created_at = order['created_at'].strftime("%d.%m.%Y %H:%M") if order.get('created_at') else "—"
    
    text = "📋 <b>Мои заказы</b>\n"
    text += "━━━━━━━━━━━━━━━\n\n"
    text += f"{status_emoji.get(order['status'], '📋')} <b>Заказ #{order['order_id']}</b>\n\n"
    text += f"💰 Цена: <b>{order['price']} ₽</b>\n"
    text += f"⏰ Время: <b>{order['start_time']}</b>\n"
    text += f"📍 Адрес: {order['address']}\n"
    text += f"👥 Исполнителей: <b>{order['workers_count']}</b>\n"
    text += f"📝 Описание: {order['comment']}\n\n"
    text += f"📊 Статус: <b>{status_text.get(order['status'], order['status'])}</b>\n"
    text += f"👥 Откликов: <b>{len(responses)}</b>\n"
    text += f"📅 Создан: {created_at}\n\n"
    text += "━━━━━━━━━━━━━━━\n"
    text += f"📄 Заказ {page + 1} из {total_pages}"
    
    keyboard = get_customer_order_card_keyboard(
        order['order_id'], 
        order['status'], 
        page, 
        total_pages,
        len(responses)
    )
    
    try:
        await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await db.save_last_bot_message(user_id, message.message_id, message.chat.id)
    except Exception as e:
        logger.debug(f"Error editing message: {e}")

@dp.callback_query(F.data.startswith("cust_order_prev_"))
async def customer_order_prev(callback: types.CallbackQuery, state: FSMContext):
    current_page = int(callback.data.split("_")[3])
    new_page = current_page - 1
    await state.update_data(customer_orders_page=new_page)
    await show_customer_order_card(callback.message, callback.from_user.id, new_page)
    await callback.answer()

@dp.callback_query(F.data.startswith("cust_order_next_"))
async def customer_order_next(callback: types.CallbackQuery, state: FSMContext):
    current_page = int(callback.data.split("_")[3])
    new_page = current_page + 1
    await state.update_data(customer_orders_page=new_page)
    await show_customer_order_card(callback.message, callback.from_user.id, new_page)
    await callback.answer()

@dp.message(F.text.startswith("📋 Мои заказы"))
async def my_orders(message: types.Message, state: FSMContext):
    if await check_banned(message.from_user.id):
        await delete_and_send(message, "❌ Вы заблокированы в системе.")
        return
    
    try:
        await message.delete()
    except:
        pass
    
    orders = await db.get_customer_orders(message.from_user.id)
    
    if not orders:
        await smart_send(message.from_user.id, message.chat.id, "📭 У вас нет активных заказов.", reply_markup=await get_customer_orders_menu_with_counts(message.from_user.id))
        return
    
    await state.update_data(customer_orders_page=0)
    
    sent_msg = await bot.send_message(
        message.chat.id,
        "Загрузка...",
        parse_mode="HTML"
    )
    await show_customer_order_card(sent_msg, message.from_user.id, 0, orders)

@dp.callback_query(F.data.startswith("view_responses_"))
async def view_responses(callback: types.CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split("_")[2])
    responses = await db.get_responses(order_id)
    
    if not responses:
        await smart_edit_or_send(
            callback,
            f"📭 <b>Отклики на заказ #{order_id}</b>\n\n"
            f"Пока никто не откликнулся.\n"
            f"Исполнители увидят ваш заказ в ленте.",
            reply_markup=get_no_responses_keyboard(order_id),
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    await state.update_data(responses_order_id=order_id, responses_idx=0)
    
    await show_response_card(callback, state, order_id, 0, responses)
    await callback.answer()

async def show_response_card(callback, state, order_id, idx, responses=None):
    if responses is None:
        responses = await db.get_responses(order_id)
    
    if not responses or idx >= len(responses):
        return
    
    resp = responses[idx]
    total = len(responses)
    
    reviews = await db.get_reviews(resp['executor_id'])
    reviews_count = len(reviews) if reviews else 0
    
    text = f"👥 <b>Отклики на заказ #{order_id}</b>\n"
    text += f"━━━━━━━━━━━━━━━\n\n"
    
    text += f"⚡ <b>{resp['first_name']}</b>"
    if resp['username']:
        text += f" (@{resp['username']})"
    text += "\n\n"
    
    text += f"⭐ Рейтинг: <b>{resp['rating']}</b>\n"
    text += f"📦 Выполнено: <b>{resp['completed_orders']}</b>\n"
    text += f"🏆 Уровень: <b>{resp['level']}</b>\n"
    text += f"💬 Отзывов: <b>{reviews_count}</b>\n"
    
    if resp['message']:
        text += f"\n📝 <b>Сообщение:</b>\n<i>{resp['message']}</i>"
    
    keyboard = get_response_card_keyboard(order_id, resp['executor_id'], idx, total)
    
    await smart_edit_or_send(callback, text, reply_markup=keyboard, parse_mode="HTML")

@dp.callback_query(F.data.startswith("resp_prev_"))
async def response_prev(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    order_id = int(parts[2])
    current_idx = int(parts[3])
    
    new_idx = max(0, current_idx - 1)
    await state.update_data(responses_idx=new_idx)
    await show_response_card(callback, state, order_id, new_idx)
    await callback.answer()

@dp.callback_query(F.data.startswith("resp_next_"))
async def response_next(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    order_id = int(parts[2])
    current_idx = int(parts[3])
    
    responses = await db.get_responses(order_id)
    new_idx = min(len(responses) - 1, current_idx + 1)
    await state.update_data(responses_idx=new_idx)
    await show_response_card(callback, state, order_id, new_idx, responses)
    await callback.answer()

@dp.callback_query(F.data.startswith("back_to_order_"))
async def back_to_order(callback: types.CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split("_")[3])
    
    order = await db.get_order(order_id)
    responses = await db.get_responses(order_id)
    
    status_emoji = {"open": "🆕", "assigned": "✅", "in_progress": "⏳", "completed": "✔️"}
    
    text = f"{status_emoji.get(order['status'], '📋')} <b>Заказ #{order['order_id']}</b>\n"
    text += f"━━━━━━━━━━━━━━━\n\n"
    text += f"💰 Цена: <b>{order['price']} ₽</b>\n"
    text += f"📍 Адрес: {order['address']}\n"
    text += f"👥 Исполнителей: {order['workers_count']}\n"
    text += f"📝 {order['comment']}\n\n"
    text += f"👥 Откликов: <b>{len(responses)}</b>"
    
    await smart_edit_or_send(
        callback,
        text,
        reply_markup=get_order_actions(order['order_id'], order['status']),
        parse_mode="HTML"
    )
    
    await state.clear()
    await callback.answer()

@dp.callback_query(F.data.startswith("accept_executor_"))
async def accept_executor(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    order_id = int(parts[2])
    executor_id = int(parts[3])
    
    await db.assign_executor(order_id, executor_id)
    
    order = await db.get_order(order_id)
    
    await smart_edit_or_send(callback, "✅ Исполнитель назначен на заказ!")
    
    try:
        customer = await db.get_user(order['customer_id'])
        customer_rating = await db.get_customer_rating(order['customer_id'])
        
        back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_executor_menu")]
        ])
        
        await bot.send_message(
            executor_id,
            f"🎉 <b>Вас выбрали на заказ!</b>\n\n"
            f"📦 <b>Заказ №{order_id}</b>\n\n"
            f"💰 Цена: {order['price']} ₽\n"
            f"⏰ Время: {order['start_time']}\n"
            f"📍 Адрес: {order['address']}\n"
            f"👥 Требуется исполнителей: {order['workers_count']}\n"
            f"📝 Описание: {order['comment']}\n"
            f"👤 Заказчик: @{customer['username'] or 'не указан'} (⭐{customer_rating})\n\n"
            f"Свяжитесь с заказчиком для уточнения деталей.",
            parse_mode="HTML",
            reply_markup=back_keyboard
        )
    except:
        pass
    
    await callback.answer()

@dp.callback_query(F.data.startswith("view_profile_"))
async def view_executor_profile(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    executor_id = int(parts[2])
    order_id = int(parts[3])
    
    await state.update_data(review_executor_id=executor_id, review_order_id=order_id, review_page=0)
    await show_reviews_page(callback.message, executor_id, order_id, 0, state, is_callback=True)
    await callback.answer()

async def show_reviews_page(message: types.Message, executor_id: int, order_id: int, page: int, state: FSMContext, is_callback=False):
    reviews = await db.get_reviews(executor_id)
    executor = await db.get_user(executor_id)
    profile = await db.get_executor_profile(executor_id)
    
    if not reviews:
        text = f"👤 <b>Профиль исполнителя</b>\n\n"
        text += f"@{executor['username'] or 'не указан'}\n"
        text += f"⭐ Рейтинг: {profile['rating']}\n"
        text += f"📦 Выполнено заказов: {profile['completed_orders']}\n"
        text += f"🏆 Уровень: {profile['level']}\n\n"
        text += "💬 <b>Отзывов пока нет</b>"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"back_from_reviews_{order_id}")]
        ])
        
        if is_callback:
            await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        return
    
    page_size = 5
    total_pages = (len(reviews) + page_size - 1) // page_size
    
    if page < 0:
        page = 0
    if page >= total_pages:
        page = total_pages - 1
    
    start_idx = page * page_size
    end_idx = min(start_idx + page_size, len(reviews))
    page_reviews = reviews[start_idx:end_idx]
    
    text = f"👤 <b>Профиль исполнителя</b>\n\n"
    text += f"@{executor['username'] or 'не указан'}\n"
    text += f"⭐ Рейтинг: {profile['rating']}\n"
    text += f"📦 Выполнено заказов: {profile['completed_orders']}\n"
    text += f"🏆 Уровень: {profile['level']}\n\n"
    text += f"💬 <b>Отзывы ({len(reviews)} всего)</b>\n"
    text += f"━━━━━━━━━━━━━━━━━\n\n"
    
    for review in page_reviews:
        date_str = review['created_at'].strftime("%d.%m.%Y")
        text += f"Оценка: {review['rating']}/5 | {date_str}\n"
        text += f"От: @{review['username'] or 'не указан'}\n"
        if review['comment']:
            comment = review['comment'][:100]
            if len(review['comment']) > 100:
                comment += "..."
            text += f"💭 {comment}\n"
        text += f"━━━━━━━━━━━━━━━━━\n"
    
    buttons = []
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"reviews_page_{executor_id}_{order_id}_{page - 1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="➡️ Вперёд", callback_data=f"reviews_page_{executor_id}_{order_id}_{page + 1}"))
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    buttons.append([InlineKeyboardButton(text=f"📄 Страница {page + 1}/{total_pages}", callback_data="page_info")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"back_from_reviews_{order_id}")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    if is_callback:
        await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@dp.callback_query(F.data.startswith("reviews_page_"))
async def navigate_reviews(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    executor_id = int(parts[2])
    order_id = int(parts[3])
    page = int(parts[4])
    
    await state.update_data(review_page=page)
    await show_reviews_page(callback.message, executor_id, order_id, page, state, is_callback=True)
    await callback.answer()

@dp.callback_query(F.data.startswith("back_from_reviews_"))
async def back_from_reviews(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[3])
    await callback.message.delete()
    
    responses = await db.get_responses(order_id)
    
    if not responses:
        await callback.answer("📭 Откликов больше нет", show_alert=True)
        return
    
    await bot.send_message(callback.message.chat.id, f"👥 <b>Отклики на заказ #{order_id}</b>\n\nВсего: {len(responses)}", parse_mode="HTML")
    
    last_msg = None
    for resp in responses:
        text = f"⚡ <b>{resp['first_name']}</b> (@{resp['username'] or 'нет'})\n\n"
        text += f"⭐ Рейтинг: {resp['rating']}\n"
        text += f"📦 Выполнено заказов: {resp['completed_orders']}\n"
        text += f"🏆 Уровень: {resp['level']}\n\n"
        if resp['message']:
            text += f"💬 Сообщение: {resp['message']}"
        
        last_msg = await bot.send_message(
            callback.message.chat.id,
            text,
            reply_markup=get_executor_actions(resp['response_id'], resp['executor_id'], order_id),
            parse_mode="HTML"
        )
    
    if last_msg:
        await db.save_last_bot_message(callback.from_user.id, last_msg.message_id, callback.message.chat.id)
    
    await callback.answer()

@dp.callback_query(F.data == "page_info")
async def page_info(callback: types.CallbackQuery):
    await callback.answer()

@dp.callback_query(F.data.startswith("mark_complete_"))
async def mark_complete_order(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    await smart_edit_or_send(
        callback,
        "Вы уверены, что хотите поменять статус заказа на выполненный?",
        reply_markup=get_complete_confirmation(order_id),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("confirm_complete_"))
async def confirm_complete_order(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    order = await db.get_order(order_id)
    
    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return
    
    if callback.from_user.id != order['customer_id']:
        await callback.answer("❌ Только заказчик может завершить заказ", show_alert=True)
        return
    
    await smart_edit_or_send(
        callback,
        "⚠️ <b>Вы точно хотите сменить статус заказа на выполненный?</b>\n\n"
        "После подтверждения заказ будет закрыт.",
        reply_markup=get_complete_final_confirmation(order_id),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("final_complete_"))
async def final_complete_order(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    order = await db.get_order(order_id)
    
    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return
    
    if callback.from_user.id != order['customer_id']:
        await callback.answer("❌ Только заказчик может завершить заказ", show_alert=True)
        return
    
    await db.complete_order(order_id)
    
    await callback.message.edit_text(
        f"✅ <b>Заказ #{order_id} отмечен как выполненный!</b>\n\n"
        f"Заказ скрыт из общей ленты.",
        parse_mode="HTML"
    )
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    
    responses = await db.get_responses(order_id)
    notified = set()
    
    if order['executor_id']:
        try:
            await db.update_executor_stats(order['executor_id'])
            
            await bot.send_message(
                order['executor_id'],
                f"✅ <b>Заказ завершён!</b>\n\n"
                f"<b>Заказ #{order_id}</b>\n"
                f"💰 Цена: {order['price']} ₽\n"
                f"📍 Адрес: {order['address']}\n"
                f"👥 Исполнителей: {order['workers_count']}\n"
                f"📝 Описание: {order['comment']}\n\n"
                f"Заказчик подтвердил выполнение заказа.\n"
                f"✨ Ваша статистика обновлена! (+1 заказ)\n\n"
                f"Ожидайте оценку.",
                parse_mode="HTML"
            )
            notified.add(order['executor_id'])
        except Exception as e:
            logger.error(f"Failed to notify executor: {e}")
        
        executor = await db.get_user(order['executor_id'])
        await smart_edit_or_send(
            callback,
            f"Оцените исполнителя @{executor['username'] or 'исполнитель'}\n"
            f"Выберите оценку:",
            reply_markup=get_rating_keyboard(order_id),
            parse_mode="HTML"
        )
    
    # Уведомляем всех остальных исполнителей кто откликался
    for resp in responses:
        if resp['executor_id'] not in notified:
            try:
                await bot.send_message(
                    resp['executor_id'],
                    f"ℹ️ <b>Заказ завершён</b>\n\n"
                    f"<b>Заказ #{order_id}</b>\n"
                    f"💰 Цена: {order['price']} ₽\n"
                    f"📍 Адрес: {order['address']}\n"
                    f"👥 Исполнителей: {order['workers_count']}\n"
                    f"📝 Описание: {order['comment']}\n\n"
                    f"Заказ, на который вы откликались, был завершён заказчиком.",
                    parse_mode="HTML"
                )
                notified.add(resp['executor_id'])
            except Exception as e:
                logger.error(f"Failed to notify executor {resp['executor_id']}: {e}")
    
    await callback.answer()

@dp.callback_query(F.data.startswith("cancel_complete_"))
async def cancel_complete_order(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    
    order = await db.get_order(order_id)
    responses = await db.get_responses(order_id)
    
    status_emoji = {"open": "🆕", "assigned": "✅", "in_progress": "⏳", "completed": "✔️"}
    
    text = f"{status_emoji.get(order['status'], '📋')} <b>Заказ #{order['order_id']}</b>\n\n"
    text += f"💰 Цена: {order['price']} ₽\n"
    text += f"📍 Адрес: {order['address']}\n"
    text += f"👥 Требуется исполнителей: {order['workers_count']}\n"
    text += f"📝 Описание: {order['comment']}\n\n"
    text += f"Статус: {order['status']}\n"
    text += f"👥 Откликов: {len(responses)}"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_order_actions(order['order_id'], order['status']),
        parse_mode="HTML"
    )
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer()

@dp.callback_query(F.data.startswith("delete_order_"))
async def delete_order_confirm(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    await callback.message.edit_text(
        "❓ <b>Вы действительно хотите отказаться от заказа?</b>\n\n"
        "Заказ будет удалён, а исполнители получат уведомление.",
        reply_markup=get_delete_confirmation(order_id),
        parse_mode="HTML"
    )
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer()

@dp.callback_query(F.data == "confirm_delete_all_orders")
async def confirm_delete_all_callback(callback: types.CallbackQuery):
    await db.delete_all_customer_orders(callback.from_user.id)
    
    await callback.message.edit_text(
        "✅ Все активные заказы перемещены в корзину.",
        parse_mode="HTML"
    )
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await smart_edit_or_send(
        callback,
        "Вы можете восстановить заказы из корзины.",
        reply_markup=await get_customer_orders_menu_with_counts(callback.from_user.id)
    )
    await callback.answer()

@dp.callback_query(F.data == "cancel_delete_all_orders")
async def cancel_delete_all_callback(callback: types.CallbackQuery):
    # Просто удаляем сообщение подтверждения
    try:
        await callback.message.delete()
    except:
        pass
    await callback.answer()

@dp.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete_order(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    
    order = await db.get_order(order_id)
    responses = await db.get_responses(order_id)
    
    await db.delete_order(order_id)
    await callback.message.edit_text("🗑️ Заказ удалён.")
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    
    notified = set()
    
    if order['executor_id'] and order['executor_id'] not in notified:
        try:
            await bot.send_message(
                order['executor_id'],
                f"🗑️ Заказ \"{order['comment'][:50]}...\" был удалён заказчиком.",
                parse_mode="HTML"
            )
            notified.add(order['executor_id'])
        except Exception as e:
            logger.error(f"Failed to notify executor {order['executor_id']}: {e}")
    
    for resp in responses:
        if resp['executor_id'] not in notified:
            try:
                await bot.send_message(
                    resp['executor_id'],
                    f"🗑️ Заказ \"{order['comment'][:50]}...\" был удалён заказчиком.",
                    parse_mode="HTML"
                )
                notified.add(resp['executor_id'])
            except Exception as e:
                logger.error(f"Failed to notify executor {resp['executor_id']}: {e}")
    
    await callback.answer()

@dp.callback_query(F.data.startswith("cancel_delete_"))
async def cancel_delete_order(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    
    # Получаем информацию о заказе
    order = await db.get_order(order_id)
    responses = await db.get_responses(order_id)
    
    status_emoji = {"open": "🆕", "assigned": "✅", "in_progress": "⏳", "completed": "✔️"}
    
    text = f"{status_emoji.get(order['status'], '📋')} <b>Заказ #{order['order_id']}</b>\n\n"
    text += f"💰 Цена: {order['price']} ₽\n"
    text += f"📍 Адрес: {order['address']}\n"
    text += f"👥 Требуется исполнителей: {order['workers_count']}\n"
    text += f"📝 Описание: {order['comment']}\n\n"
    text += f"Статус: {order['status']}\n"
    text += f"👥 Откликов: {len(responses)}"
    
    # Редактируем сообщение обратно к информации о заказе
    await callback.message.edit_text(
        text,
        reply_markup=get_order_actions(order['order_id'], order['status']),
        parse_mode="HTML"
    )
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer()

@dp.callback_query(F.data.startswith("start_work_"))
async def start_work(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    
    async with db.pool.acquire() as conn:
        await conn.execute(
            'UPDATE orders SET status = \'in_progress\' WHERE order_id = $1',
            order_id
        )
    
    await callback.message.edit_text("✅ Работа начата! Заказ перешёл в статус 'В процессе'.")
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer()

@dp.callback_query(F.data.startswith("executor_complete_"))
async def executor_complete_order_start(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    
    order = await db.get_order(order_id)
    
    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return
    
    if order['executor_id'] != callback.from_user.id:
        await callback.answer("Вы не можете отметить этот заказ", show_alert=True)
        return
    
    customer = await db.get_user(order['customer_id'])
    
    text = "❓ <b>Вы завершили работу по этому заказу?</b>\n\n"
    text += f"📋 <b>Заказ #{order_id}</b>\n"
    text += f"💰 Цена: {order['price']} ₽\n"
    text += f"⏰ Время: {order['start_time']}\n"
    text += f"📍 Адрес: {order['address']}\n"
    text += f"👥 Исполнителей: {order['workers_count']}\n"
    text += f"📝 Описание: {order['comment']}\n"
    text += f"👤 Заказчик: @{customer['username'] or 'не указан'}\n\n"
    text += "Заказчик получит уведомление о завершении работы.\n\n"
    text += "✅ <b>Вы можете брать новые заказы даже если заказчик не подтвердит выполнение!</b>"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_executor_complete_confirmation(order_id),
        parse_mode="HTML"
    )
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer()

@dp.callback_query(F.data.startswith("confirm_executor_complete_"))
async def confirm_executor_complete_order(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[3])
    order = await db.get_order(order_id)
    
    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return
    
    if order['executor_id'] != callback.from_user.id:
        await callback.answer("Ошибка доступа", show_alert=True)
        return
    
    # Меняем статус заказа на "в процессе завершения" чтобы разблокировать исполнителя
    async with db.pool.acquire() as conn:
        await conn.execute(
            'UPDATE orders SET status = \'awaiting_confirmation\' WHERE order_id = $1',
            order_id
        )
    
    await callback.message.edit_text(
        "✅ <b>Вы отметили работу как завершённую!</b>\n\n"
        "Заказчик получил уведомление.\n\n"
        "🚀 <b>Вы можете брать новые заказы прямо сейчас!</b>",
        parse_mode="HTML"
    )
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    
    # Отправляем уведомление заказчику
    customer = await db.get_user(order['customer_id'])
    executor = await db.get_user(callback.from_user.id)
    
    try:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить выполнение", callback_data=f"mark_complete_{order_id}")],
            [InlineKeyboardButton(text="📋 Посмотреть заказ", callback_data=f"view_customer_order_{order_id}")]
        ])
        
        await bot.send_message(
            order['customer_id'],
            f"✅ <b>Исполнитель завершил работу!</b>\n\n"
            f"<b>Заказ #{order_id}</b>\n"
            f"💰 Цена: {order['price']} ₽\n"
            f"📍 Адрес: {order['address']}\n"
            f"👥 Исполнителей: {order['workers_count']}\n"
            f"📝 Описание: {order['comment']}\n\n"
            f"⚡ Исполнитель @{executor['username'] or 'не указан'} отметил работу как выполненную.\n\n"
            f"Пожалуйста, подтвердите выполнение заказа, если работа действительно завершена.",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Failed to notify customer: {e}")
    
    await callback.answer()

@dp.callback_query(F.data.startswith("cancel_executor_complete_"))
async def cancel_executor_complete_order(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[3])
    
    # Получаем информацию о заказе
    order = await db.get_order(order_id)
    
    status_emoji = {"open": "🆕", "assigned": "✅", "in_progress": "⏳", "awaiting_confirmation": "⏰", "completed": "✔️"}
    
    text = f"{status_emoji.get(order['status'], '📋')} <b>Заказ #{order['order_id']}</b>\n\n"
    text += f"💰 Цена: {order['price']} ₽\n"
    text += f"📍 Адрес: {order['address']}\n"
    text += f"👥 Требуется исполнителей: {order['workers_count']}\n"
    text += f"📝 Описание: {order['comment']}\n\n"
    text += f"Статус: {order['status']}"
    
    # Редактируем сообщение обратно к информации о заказе
    await callback.message.edit_text(
        text,
        reply_markup=get_executor_order_actions(order['order_id'], order['status']),
        parse_mode="HTML"
    )
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer()

@dp.callback_query(F.data.startswith("decline_order_"))
async def decline_order_start(callback: types.CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split("_")[2])
    
    order = await db.get_order(order_id)
    
    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return
    
    if order['executor_id'] != callback.from_user.id:
        await callback.answer("Вы не можете отказаться от этого заказа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "❓ <b>Вы действительно хотите отказаться от заказа?</b>\n\n"
        "Заказ вернётся в общую ленту, а заказчик получит уведомление.",
        reply_markup=get_decline_confirmation(order_id),
        parse_mode="HTML"
    )
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer()

@dp.callback_query(F.data.startswith("confirm_decline_"))
async def confirm_decline_order(callback: types.CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split("_")[2])
    
    await state.update_data(decline_order_id=order_id)
    await state.set_state(DeclineOrder.reason)
    
    await callback.message.edit_text(
        "❌ <b>Отказ от заказа</b>\n\n"
        "Пожалуйста, укажите причину отказа.\n"
        "Заказчик получит ваше сообщение.\n\n"
        "<i>Или нажмите Отмена для возврата</i>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer()

@dp.callback_query(F.data.startswith("cancel_decline_"))
async def cancel_decline_order(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    
    # Получаем информацию о заказе
    order = await db.get_order(order_id)
    
    status_emoji = {"open": "🆕", "assigned": "✅", "in_progress": "⏳", "awaiting_confirmation": "⏰", "completed": "✔️"}
    
    text = f"{status_emoji.get(order['status'], '📋')} <b>Заказ #{order['order_id']}</b>\n\n"
    text += f"💰 Цена: {order['price']} ₽\n"
    text += f"📍 Адрес: {order['address']}\n"
    text += f"👥 Требуется исполнителей: {order['workers_count']}\n"
    text += f"📝 Описание: {order['comment']}\n\n"
    text += f"Статус: {order['status']}"
    
    # Редактируем сообщение обратно к информации о заказе
    await callback.message.edit_text(
        text,
        reply_markup=get_executor_order_actions(order['order_id'], order['status']),
        parse_mode="HTML"
    )
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer()

@dp.message(DeclineOrder.reason)
async def decline_order_reason(message: types.Message, state: FSMContext):
    data = await state.get_data()
    order_id = data['decline_order_id']
    reason = message.text
    
    order = await db.get_order(order_id)
    executor_profile = await db.get_executor_profile(message.from_user.id)
    
    await db.decline_order(order_id, reason)
    
    await delete_and_send(
        message,
        "✅ <b>Вы отказались от заказа</b>\n\n"
        "Заказчик получил уведомление о вашем отказе.\n"
        "Заказ вернулся в общую ленту.",
        reply_markup=get_executor_menu(),
        parse_mode="HTML"
    )
    
    try:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="1", callback_data=f"rate_declined_{order_id}_1"),
             InlineKeyboardButton(text="2", callback_data=f"rate_declined_{order_id}_2"),
             InlineKeyboardButton(text="3", callback_data=f"rate_declined_{order_id}_3"),
             InlineKeyboardButton(text="4", callback_data=f"rate_declined_{order_id}_4"),
             InlineKeyboardButton(text="5", callback_data=f"rate_declined_{order_id}_5")],
            [InlineKeyboardButton(text="❌ Пропустить оценку", callback_data=f"skip_rating_{order_id}")]
        ])
        
        executor_username = f"@{message.from_user.username}" if message.from_user.username else "нет username"
        
        await bot.send_message(
            order['customer_id'],
            f"❌ <b>Исполнитель отказался от заказа</b>\n\n"
            f"📦 Заказ: {order['comment'][:50]}...\n"
            f"⚡ Исполнитель: @{message.from_user.username or 'исполнитель'}\n"
            f"⭐ Рейтинг исполнителя: {executor_profile['rating']}\n\n"
            f"📝 <b>Причина отказа:</b>\n{reason}\n\n"
            f"Ваш заказ вернулся в общую ленту.\n\n"
            f"<i>Вы можете оценить исполнителя за его реакцию на заказ:</i>",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Failed to notify customer about order decline: {e}")
    
    await state.clear()

@dp.callback_query(F.data.startswith("rate_declined_"))
async def rate_declined_executor(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    order_id = int(parts[2])
    rating = int(parts[3])
    
    await state.update_data(declined_order_id=order_id, declined_rating=rating)
    
    await callback.message.edit_text(
        f"Вы выбрали оценку: {rating}/5\n\nХотите добавить комментарий?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, добавить комментарий", callback_data=f"declined_comment_yes_{order_id}")],
            [InlineKeyboardButton(text="❌ Нет, оценка без комментария", callback_data=f"declined_comment_no_{order_id}")]
        ])
    )
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer()

@dp.callback_query(F.data.startswith("declined_comment_yes_"))
async def declined_comment_yes(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("💬 Напишите ваш комментарий к оценке:")
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await state.set_state(LeaveReview.comment)
    await callback.answer()

@dp.callback_query(F.data.startswith("declined_comment_no_"))
async def declined_comment_no(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    order_id = data['declined_order_id']
    rating = data['declined_rating']
    
    order = await db.get_order(order_id)
    
    await db.create_review(
        order_id,
        callback.from_user.id,
        order['executor_id'],
        rating,
        ""
    )
    
    await callback.message.edit_text(
        "✅ <b>Спасибо за вашу оценку!</b>\n\n"
        "Исполнитель получил уведомление о вашей реакции.",
        parse_mode="HTML"
    )
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    
    try:
        await bot.send_message(
            order['executor_id'],
            f"📊 <b>Заказчик отреагировал на ваш отказ</b>\n\n"
            f"📦 Заказ: {order['comment'][:50]}...\n"
            f"Оценка: {rating}/5\n",
            parse_mode="HTML"
        )
    except:
        pass
    
    await state.clear()
    await callback.answer()

@dp.callback_query(F.data.startswith("skip_rating_"))
async def skip_rating_declined(callback: types.CallbackQuery):
    await callback.message.edit_text("Вы пропустили оценку.")
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer()

@dp.callback_query(F.data == "order_feed")
async def order_feed_callback(callback: types.CallbackQuery, state: FSMContext):
    logger.info(f"order_feed_callback triggered by user {callback.from_user.id}")
    
    if await check_banned(callback.from_user.id):
        await callback.answer("❌ Вы заблокированы в системе.", show_alert=True)
        return
    
    try:
        user_id = callback.from_user.id
        chat_id = callback.message.chat.id
        
        logger.info(f"Opening order feed for user {user_id}, chat {chat_id}")
        
        await state.clear()
        
        orders = await db.get_open_orders()
        
        if not orders:
            empty_feed_text = (
                "╔═══════════════════════════\n"
                "║ <b>📱 ЛЕНТА ЗАКАЗОВ</b>\n"
                "╚═══════════════════════════\n\n"
                "📭 <b>Доступных заказов пока нет.</b>\n\n"
                "Заходите позже — новые заказы появляются регулярно!"
            )
            try:
                await callback.message.edit_text(
                    empty_feed_text,
                    reply_markup=await get_executor_menu_with_counts(user_id),
                    parse_mode="HTML"
                )
                await db.save_last_bot_message(user_id, callback.message.message_id, chat_id)
            except Exception as edit_error:
                if "message is not modified" in str(edit_error).lower():
                    pass
                else:
                    logger.debug(f"Could not edit message: {edit_error}")
            await callback.answer()
            return
        
        await show_feed_page_edit(callback.message, user_id, chat_id, 0, state)
        logger.info(f"Order feed shown successfully for user {user_id}")
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in order_feed_callback: {e}", exc_info=True)
        try:
            await callback.answer("Произошла ошибка. Попробуйте снова.", show_alert=True)
        except:
            pass

@dp.message(F.text.startswith("📱 Лента заказов"))
async def feed_orders(message: types.Message, state: FSMContext):
    if await check_banned(message.from_user.id):
        await delete_and_send(message, "❌ Вы заблокированы в системе.")
        return
    
    # Удаляем предыдущее сообщение ленты, если оно есть
    data = await state.get_data()
    if 'feed_message_id' in data:
        try:
            await bot.delete_message(message.chat.id, data['feed_message_id'])
        except:
            pass
    
    # Удаляем сообщение пользователя с нажатой кнопкой
    try:
        await message.delete()
    except:
        pass
    
    await show_feed_page(message.from_user.id, message.chat.id, 0, state)

async def show_feed_page_edit(message: types.Message, user_id: int, chat_id: int, page: int, state: FSMContext):
    """Показывает ленту заказов - 5 заказов на странице с компактным дизайном"""
    logger.info(f"show_feed_page_edit called: user_id={user_id}, chat_id={chat_id}, page={page}")
    
    orders = await db.get_open_orders()
    logger.info(f"Found {len(orders) if orders else 0} orders")
    
    if not orders:
        try:
            await message.edit_text(
                "📱 <b>Лента заказов</b>\n"
                "━━━━━━━━━━━━━━━\n\n"
                "📭 <b>Заказов пока нет</b>\n\n"
                "Заходите позже — новые заказы\n"
                "появляются регулярно!",
                reply_markup=await get_executor_menu_with_counts(user_id),
                parse_mode="HTML"
            )
            await db.save_last_bot_message(user_id, message.message_id, chat_id)
        except Exception as e:
            logger.error(f"Error editing message: {e}")
        return
    
    page_size = 5
    total_pages = (len(orders) + page_size - 1) // page_size
    
    if page < 0:
        page = 0
    if page >= total_pages:
        page = total_pages - 1
    
    start_idx = page * page_size
    end_idx = min(start_idx + page_size, len(orders))
    page_orders = orders[start_idx:end_idx]
    
    await state.update_data(current_feed_page=page)
    
    text = "📱 <b>Лента заказов</b>\n"
    text += f"━━━━━━━━━━━━━━━\n"
    text += f"📊 Всего: {len(orders)} | Стр. {page + 1}/{total_pages}\n\n"
    
    keyboard_rows = []
    
    for idx, order in enumerate(page_orders):
        customer_rating = await db.get_customer_rating(order['customer_id'])
        
        created_date = ""
        if order.get('created_at'):
            now = datetime.now()
            order_date = order['created_at']
            if order_date.date() == now.date():
                created_date = f"📅 Сегодня {order_date.strftime('%H:%M')}"
            elif order_date.date() == (now - timedelta(days=1)).date():
                created_date = f"📅 Вчера {order_date.strftime('%H:%M')}"
            else:
                created_date = f"📅 {order_date.strftime('%d.%m %H:%M')}"
        
        text += f"<b>#{order['order_id']}</b> 💰 {order['price']} ₽\n"
        text += f"⏰ {order['start_time']} 📍 {order['address'][:25]}{'...' if len(order['address']) > 25 else ''}\n"
        text += f"📝 {order['comment'][:40]}{'...' if len(order['comment']) > 40 else ''}\n"
        text += f"👥 {order['workers_count']} чел. | ⭐ {customer_rating} | {created_date}\n"
        
        if idx < len(page_orders) - 1:
            text += "───────────────\n"
        
        keyboard_rows.append([InlineKeyboardButton(
            text=f"✋ #{order['order_id']} — {order['price']} ₽", 
            callback_data=f"take_order_{order['order_id']}"
        )])
    
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"feed_page_{page - 1}"))
    nav_row.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"feed_page_{page + 1}"))
    keyboard_rows.append(nav_row)
    
    keyboard_rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_executor_menu")])
    
    feed_keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    
    try:
        await message.edit_text(text, reply_markup=feed_keyboard, parse_mode="HTML")
        await db.save_last_bot_message(user_id, message.message_id, chat_id)
        await state.update_data(feed_message_id=message.message_id)
    except Exception as e:
        logger.error(f"Error editing message for feed: {e}")

async def show_feed_page(user_id: int, chat_id: int, page: int, state: FSMContext):
    """Показывает ленту заказов - 5 заказов на странице с компактным дизайном"""
    logger.info(f"show_feed_page called: user_id={user_id}, chat_id={chat_id}, page={page}")
    
    orders = await db.get_open_orders()
    logger.info(f"Found {len(orders) if orders else 0} orders")
    
    if not orders:
        msg = await bot.send_message(
            chat_id, 
            "📱 <b>Лента заказов</b>\n"
            "━━━━━━━━━━━━━━━\n\n"
            "📭 <b>Заказов пока нет</b>\n\n"
            "Заходите позже — новые заказы\n"
            "появляются регулярно!",
            reply_markup=await get_executor_menu_with_counts(user_id),
            parse_mode="HTML"
        )
        await db.save_last_bot_message(user_id, msg.message_id, chat_id)
        return
    
    page_size = 5
    total_pages = (len(orders) + page_size - 1) // page_size
    
    if page < 0:
        page = 0
    if page >= total_pages:
        page = total_pages - 1
    
    start_idx = page * page_size
    end_idx = min(start_idx + page_size, len(orders))
    page_orders = orders[start_idx:end_idx]
    
    await state.update_data(current_feed_page=page)
    
    text = "📱 <b>Лента заказов</b>\n"
    text += f"━━━━━━━━━━━━━━━\n"
    text += f"📊 Всего: {len(orders)} | Стр. {page + 1}/{total_pages}\n\n"
    
    keyboard_rows = []
    
    for idx, order in enumerate(page_orders):
        customer_rating = await db.get_customer_rating(order['customer_id'])
        
        created_date = ""
        if order.get('created_at'):
            now = datetime.now()
            order_date = order['created_at']
            if order_date.date() == now.date():
                created_date = f"📅 Сегодня {order_date.strftime('%H:%M')}"
            elif order_date.date() == (now - timedelta(days=1)).date():
                created_date = f"📅 Вчера {order_date.strftime('%H:%M')}"
            else:
                created_date = f"📅 {order_date.strftime('%d.%m %H:%M')}"
        
        text += f"<b>#{order['order_id']}</b> 💰 {order['price']} ₽\n"
        text += f"⏰ {order['start_time']} 📍 {order['address'][:25]}{'...' if len(order['address']) > 25 else ''}\n"
        text += f"📝 {order['comment'][:40]}{'...' if len(order['comment']) > 40 else ''}\n"
        text += f"👥 {order['workers_count']} чел. | ⭐ {customer_rating} | {created_date}\n"
        
        if idx < len(page_orders) - 1:
            text += "───────────────\n"
        
        keyboard_rows.append([InlineKeyboardButton(
            text=f"✋ #{order['order_id']} — {order['price']} ₽", 
            callback_data=f"take_order_{order['order_id']}"
        )])
    
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"feed_page_{page - 1}"))
    nav_row.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"feed_page_{page + 1}"))
    keyboard_rows.append(nav_row)
    
    keyboard_rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_executor_menu")])
    
    feed_keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    msg = await bot.send_message(chat_id, text, reply_markup=feed_keyboard, parse_mode="HTML")
    await db.save_last_bot_message(user_id, msg.message_id, chat_id)
    await state.update_data(feed_message_id=msg.message_id)

@dp.callback_query(F.data.startswith("feed_page_"))
async def navigate_feed(callback: types.CallbackQuery, state: FSMContext):
    page = int(callback.data.split("_")[2])
    if page < 0:
        page = 0
    await state.update_data(current_feed_page=page)
    await show_feed_page_edit(callback.message, callback.from_user.id, callback.message.chat.id, page, state)
    await callback.answer()

@dp.callback_query(F.data.startswith("take_order_"))
async def take_order(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    
    # Проверяем только что исполнитель не откликался на этот заказ ранее
    existing_responses = await db.get_responses(order_id)
    for resp in existing_responses:
        if resp['executor_id'] == callback.from_user.id:
            await callback.answer("Вы уже откликнулись на этот заказ!", show_alert=True)
            return
    
    await db.create_response(order_id, callback.from_user.id, "Готов выполнить!")
    
    order = await db.get_order(order_id)
    
    try:
        await callback.message.delete()
    except:
        pass
    
    await smart_edit_or_send(callback, "✅ Отклик отправлен! Ожидайте подтверждения от заказчика.")
    
    try:
        profile = await db.get_executor_profile(callback.from_user.id)
        view_response_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👁️ Смотреть отклик", callback_data=f"view_responses_{order_id}")]
        ])
        await bot.send_message(
            order['customer_id'],
            f"🔔 <b>Новый отклик на заказ #{order_id}!</b>\n\n"
            f"⚡ @{callback.from_user.username or 'исполнитель'}\n"
            f"⭐ Рейтинг: {profile['rating']}\n"
            f"📦 Выполнено заказов: {profile['completed_orders']}\n\n"
            f"Проверьте отклики в разделе 'Мои заказы'",
            reply_markup=view_response_keyboard,
            parse_mode="HTML"
        )
    except:
        pass
    
    await callback.answer()

@dp.callback_query(F.data == "executor_my_orders")
async def executor_my_orders_callback(callback: types.CallbackQuery):
    if await check_banned(callback.from_user.id):
        await callback.answer("❌ Вы заблокированы в системе.", show_alert=True)
        return
    
    try:
        user_id = callback.from_user.id
        chat_id = callback.message.chat.id
        
        active_orders = await db.get_executor_orders(user_id)
        
        if not active_orders:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📜 История заказов", callback_data="executor_history")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_executor_menu")]
            ])
            await callback.message.edit_text(
                "📭 <b>Мои активные заказы</b>\n\nУ вас нет активных заказов.",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            await db.save_last_bot_message(user_id, callback.message.message_id, chat_id)
            await callback.answer()
            return
        
        status_text = {
            "assigned": "✅ Назначен", 
            "in_progress": "⏳ В процессе",
            "awaiting_confirmation": "⏳ Ожидает подтверждения"
        }
        
        text = f"📦 <b>Мои активные заказы</b>\n\nВсего: {len(active_orders)}\n\n"
        
        for active_order in active_orders:
            customer = await db.get_user(active_order['customer_id'])
            
            text += f"┏━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            text += f"┃ <b>Заказ #{active_order['order_id']}</b>\n"
            text += f"┣━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            text += f"┃ 💰 Цена: {active_order['price']} ₽\n"
            text += f"┃ ⏰ Время: {active_order['start_time']}\n"
            text += f"┃ 📍 Адрес: {active_order['address']}\n"
            text += f"┃ 👥 Исполнителей: {active_order['workers_count']}\n"
            text += f"┃ 📝 Комментарий: {active_order['comment']}\n"
            text += f"┃ 👤 Заказчик: @{customer['username'] or 'не указан'}\n"
            if active_order.get('phone_number'):
                text += f"┃ 📞 Телефон: {active_order['phone_number']}\n"
            text += f"┃ 📊 Статус: {status_text.get(active_order['status'], 'Активен')}\n"
            text += f"┗━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        keyboard_rows = []
        for active_order in active_orders:
            keyboard_rows.append([InlineKeyboardButton(
                text=f"⚙️ Управление заказом #{active_order['order_id']}", 
                callback_data=f"manage_exec_order_{active_order['order_id']}"
            )])
        
        keyboard_rows.append([InlineKeyboardButton(text="📜 История заказов", callback_data="executor_history")])
        keyboard_rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_executor_menu")])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await db.save_last_bot_message(user_id, callback.message.message_id, chat_id)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in executor_my_orders_callback: {e}", exc_info=True)
        try:
            await callback.answer("Произошла ошибка. Попробуйте снова.", show_alert=True)
        except:
            pass

@dp.message(F.text.startswith("📦 Мои заказы"))
async def my_executor_orders(message: types.Message):
    if await check_banned(message.from_user.id):
        await delete_and_send(message, "❌ Вы заблокированы в системе.")
        return
    
    # Получаем все активные заказы исполнителя
    active_orders = await db.get_executor_orders(message.from_user.id)
    
    if not active_orders:
        await delete_and_send(
            message,
            "📭 <b>Мои активные заказы</b>\n\nУ вас нет активных заказов.",
            reply_markup=get_my_orders_menu(),
            parse_mode="HTML"
        )
        return
    
    await delete_and_send(
        message,
        f"📦 <b>Мои активные заказы</b>\n\nВсего: {len(active_orders)}",
        parse_mode="HTML"
    )
    
    status_text = {
        "assigned": "✅ Назначен", 
        "in_progress": "⏳ В процессе",
        "awaiting_confirmation": "⏳ Ожидает подтверждения"
    }
    
    for active_order in active_orders:
        customer = await db.get_user(active_order['customer_id'])
        
        text = f"📋 <b>Заказ #{active_order['order_id']}</b>\n\n"
        text += f"💰 Цена: {active_order['price']} ₽\n"
        text += f"⏰ Время: {active_order['start_time']}\n"
        text += f"📍 Адрес: {active_order['address']}\n"
        text += f"👥 Исполнителей: {active_order['workers_count']}\n"
        text += f"📝 Комментарий: {active_order['comment']}\n\n"
        text += f"👤 Заказчик: @{customer['username'] or 'не указан'}\n"
        if active_order.get('phone_number'):
            text += f"📞 Телефон: {active_order['phone_number']}\n"
        text += f"\n📊 Статус: {status_text.get(active_order['status'], 'Активен')}"
        
        msg = await message.answer(
            text,
            reply_markup=get_executor_order_actions(active_order['order_id'], active_order['status']),
            parse_mode="HTML"
        )
        await db.save_last_bot_message(message.from_user.id, msg.message_id, message.chat.id)
    
    # Кнопка для просмотра истории
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 История заказов", callback_data="executor_history")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_executor_menu")]
    ])
    msg = await message.answer("Выберите действие:", reply_markup=keyboard)
    await db.save_last_bot_message(message.from_user.id, msg.message_id, message.chat.id)

@dp.callback_query(F.data.startswith("manage_exec_order_"))
async def manage_exec_order(callback: types.CallbackQuery):
    try:
        order_id = int(callback.data.split("_")[3])
        order = await db.get_order(order_id)
        
        if not order:
            await callback.answer("Заказ не найден", show_alert=True)
            return
        
        customer = await db.get_user(order['customer_id'])
        
        status_text = {
            "assigned": "✅ Назначен", 
            "in_progress": "⏳ В процессе",
            "awaiting_confirmation": "⏳ Ожидает подтверждения"
        }
        
        text = f"📋 <b>Заказ #{order['order_id']}</b>\n\n"
        text += f"💰 Цена: {order['price']} ₽\n"
        text += f"⏰ Время: {order['start_time']}\n"
        text += f"📍 Адрес: {order['address']}\n"
        text += f"👥 Исполнителей: {order['workers_count']}\n"
        text += f"📝 Комментарий: {order['comment']}\n\n"
        text += f"👤 Заказчик: @{customer['username'] or 'не указан'}\n"
        if order.get('phone_number'):
            text += f"📞 Телефон: {order['phone_number']}\n"
        text += f"\n📊 Статус: {status_text.get(order['status'], 'Активен')}"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_executor_order_actions(order['order_id'], order['status']),
            parse_mode="HTML"
        )
        await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in manage_exec_order: {e}", exc_info=True)
        await callback.answer("Произошла ошибка", show_alert=True)

@dp.callback_query(F.data == "executor_history")
async def executor_history(callback: types.CallbackQuery):
    try:
        user_id = callback.from_user.id
        chat_id = callback.message.chat.id
        
        history = await db.get_executor_history(user_id)
        
        if not history:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="executor_my_orders")]
            ])
            try:
                await callback.message.edit_text(
                    "📜 <b>История заказов</b>\n\nИстория заказов пуста.",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                await db.save_last_bot_message(user_id, callback.message.message_id, chat_id)
            except Exception as edit_error:
                if "message is not modified" not in str(edit_error).lower():
                    logger.debug(f"Could not edit message: {edit_error}")
            await callback.answer()
            return
    except Exception as e:
        logger.error(f"Error in executor_history: {e}", exc_info=True)
        try:
            await callback.answer("Произошла ошибка", show_alert=True)
        except:
            pass
        return
    
    # Показываем только последние 5 заказов
    recent_history = history[:5]
    
    text = ""
    for order in recent_history:
        customer = await db.get_user(order['customer_id'])
        
        if order['status'] == 'completed':
            text += f"✅ <b>Заказ #{order['order_id']}</b> — {order['price']} ₽\n"
        else:
            text += f"<b>Заказ #{order['order_id']}</b> — {order['price']} ₽\n"
        
        if order['completed_at']:
            date_str = order['completed_at'].strftime("%d.%m.%Y")
            text += f"Дата завершения: {date_str}\n"
        
        text += f"{order['address']}\n"
        
        if order['rating']:
            rating_text = f"Оценка: {order['rating']}/5"
            if order['review_comment']:
                rating_text += f" — {order['review_comment']}"
            text += f"{rating_text}\n"
        
        text += f"<b>@{customer['username'] or 'не указан'}</b>\n"
        text += f"\n"
    
    text += f"История: {len(history)}"
    
    # Кнопки "Назад" и "Очистить историю"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="back_to_my_orders")],
        [InlineKeyboardButton(text="Очистить историю", callback_data="clear_history_confirm")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer()

@dp.callback_query(F.data == "clear_history_confirm")
async def clear_history_confirm(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Вы уверены, что хотите очистить историю заказов?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Да, очистить", callback_data="clear_history_yes")],
            [InlineKeyboardButton(text="Отмена", callback_data="executor_history")]
        ]),
        parse_mode="HTML"
    )
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer()

@dp.callback_query(F.data == "clear_history_yes")
async def clear_history_yes(callback: types.CallbackQuery):
    try:
        await db.clear_executor_history(callback.from_user.id)
        
        await callback.message.edit_text(
            "✅ История заказов успешно очищена.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Назад", callback_data="back_to_my_orders")]
            ]),
            parse_mode="HTML"
        )
        await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
        await callback.answer()
    except Exception as e:
        logging.error(f"Error clearing history: {e}")
        await callback.message.edit_text(
            "❌ Произошла ошибка при очистке истории. Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Назад", callback_data="executor_history")]
            ]),
            parse_mode="HTML"
        )
        await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
        await callback.answer("Ошибка при очистке истории", show_alert=True)


@dp.callback_query(F.data == "back_to_executor_menu")
async def back_to_executor_menu(callback: types.CallbackQuery):
    await callback.answer()
    try:
        user = await db.get_user(callback.from_user.id)
        user_id = callback.from_user.id
        profile = await db.get_executor_profile(user_id)
        days_in_project = _days_since(user['created_at'] if user else None)
        
        active_orders = await db.get_executor_orders(user_id)
        completed_orders = await db.get_executor_history(user_id)
        completed_only = [o for o in completed_orders if o['status'] == 'completed']
        total_earned = sum(order['price'] for order in completed_only if order['price'])
        
        text = "⚡ <b>Режим Исполнителя</b>\n"
        text += "━━━━━━━━━━━━━━━\n\n"
        text += f"📅 Дней в проекте: <b>{days_in_project}</b>\n"
        text += f"⭐ Ваш рейтинг: <b>{profile['rating'] if profile else 0}</b>\n"
        text += f"🏆 Уровень: <b>{profile['level'] if profile else 'новичок'}</b>\n\n"
        text += f"📊 <b>Ваша статистика:</b>\n"
        text += f"├ 📝 Активных заказов: <b>{len(active_orders)}</b>\n"
        text += f"├ ✅ Выполнено заказов: <b>{profile['completed_orders'] if profile else 0}</b>\n"
        text += f"└ 💰 Заработано: <b>{total_earned:,.0f} ₽</b>\n\n"
        text += "━━━━━━━━━━━━━━━\n"
        text += "💡 Берите заказы и зарабатывайте!"
        
        await callback.message.edit_text(
            text,
            reply_markup=await get_executor_menu_with_counts(callback.from_user.id),
            parse_mode="HTML"
        )
        await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    except Exception as e:
        logger.debug(f"Could not edit message in back_to_executor_menu: {e}")

@dp.callback_query(F.data == "back_to_my_orders")
async def back_to_my_orders(callback: types.CallbackQuery):
    active_order = await db.get_executor_active_order(callback.from_user.id)
    
    if not active_order:
        await callback.message.edit_text(
            "📭 <b>Мой активный заказ</b>\n\nУ вас нет активных заказов.",
            reply_markup=get_my_orders_menu(),
            parse_mode="HTML"
        )
        await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
        await callback.answer()
        return
    
    customer = await db.get_user(active_order['customer_id'])
    status_text = {"assigned": "✅ Назначен", "in_progress": "⏳ В процессе"}
    
    text = f"📦 <b>Мой активный заказ</b>\n\n"
    text += f"💰 Цена: {active_order['price']} ₽\n"
    text += f"⏰ Время: {active_order['start_time']}\n"
    text += f"📍 Адрес: {active_order['address']}\n"
    text += f"👥 Исполнителей: {active_order['workers_count']}\n"
    text += f"📝 Комментарий: {active_order['comment']}\n\n"
    text += f"👤 Заказчик: @{customer['username'] or 'не указан'}\n"
    if active_order.get('phone_number'):
        text += f"📞 Телефон: {active_order['phone_number']}\n"
    text += f"\n📊 Статус: {status_text.get(active_order['status'], 'Активен')}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Перейти к заказу", callback_data=f"view_active_order_{active_order['order_id']}")],
        [InlineKeyboardButton(text="📜 История заказов", callback_data="executor_history")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_executor_menu")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer()

@dp.callback_query(F.data.startswith("view_active_order_"))
async def view_active_order_details(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[3])
    order = await db.get_order(order_id)
    customer = await db.get_user(order['customer_id'])
    
    status_text = {"assigned": "✅ Назначен", "in_progress": "⏳ В процессе"}
    
    text = f"📋 <b>Детали заказа #{order_id}</b>\n\n"
    text += f"💰 Цена: {order['price']} ₽\n"
    text += f"⏰ Время: {order['start_time']}\n"
    text += f"📍 Адрес: {order['address']}\n"
    text += f"👥 Исполнителей: {order['workers_count']}\n"
    text += f"📝 Комментарий: {order['comment']}\n\n"
    text += f"👤 Заказчик: @{customer['username'] or 'не указан'}\n"
    if order.get('phone_number'):
        text += f"📞 Телефон: {order['phone_number']}\n"
    text += f"\n📊 Статус: {status_text.get(order['status'], 'Активен')}"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_executor_order_actions(order_id, order['status']),
        parse_mode="HTML"
    )
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer()

@dp.callback_query(F.data.startswith("history_detail_"))
async def history_detail(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    
    history = await db.get_executor_history(callback.from_user.id)
    order = None
    for o in history:
        if o['order_id'] == order_id:
            order = o
            break
    
    if not order:
        await callback.answer("Заказ не найден в истории", show_alert=True)
        return
    
    customer = await db.get_user(order['customer_id'])
    
    status_emoji = {
        "completed": "✅",
        "deleted": "🗑️",
        "cancelled": "❌",
        "excluded": "⛔"
    }
    status_text = {
        "completed": "Выполнен",
        "deleted": "Удалён заказчиком",
        "cancelled": "Отменён",
        "excluded": "Исполнитель исключён"
    }
    
    emoji = status_emoji.get(order['status'], '📦')
    status = status_text.get(order['status'], order['status'])
    
    text = f"{emoji} <b>Заказ #{order_id} - Подробности</b>\n\n"
    text += f"📝 <b>Описание:</b>\n{order['comment']}\n\n"
    text += f"💰 <b>Цена:</b> {order['price']} ₽\n"
    text += f"⏰ <b>Время начала:</b> {order['start_time']}\n"
    text += f"📍 <b>Адрес:</b> {order['address']}\n"
    text += f"👥 <b>Исполнителей:</b> {order['workers_count']}\n\n"
    
    text += f"📊 <b>Статус:</b> {status}\n"
    
    if order['completed_at']:
        date_str = order['completed_at'].strftime("%d.%m.%Y в %H:%M")
        if order['status'] == 'completed':
            text += f"📅 <b>Дата выполнения:</b> {date_str}\n"
        else:
            text += f"📅 <b>Дата события:</b> {date_str}\n"
    elif order['review_date']:
        date_str = order['review_date'].strftime("%d.%m.%Y в %H:%M")
        text += f"📅 <b>Дата события:</b> {date_str}\n"
    elif order['created_at']:
        date_str = order['created_at'].strftime("%d.%m.%Y в %H:%M")
        text += f"📅 <b>Дата создания:</b> {date_str}\n"
    else:
        text += f"📅 <b>Дата:</b> не указана\n"
    
    text += f"\n👤 <b>Заказчик:</b> @{customer['username'] or 'не указан'}\n"
    
    if order['rating']:
        text += f"\n⭐ <b>Оценка от заказчика:</b> {order['rating']}/5\n"
        if order['review_comment']:
            text += f"💬 <b>Комментарий:</b>\n{order['review_comment']}"
    else:
        text += f"\n<i>Заказчик не оставил оценку</i>"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 К истории заказов", callback_data="executor_history")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer()

@dp.callback_query(F.data.startswith("skip_rate_"))
async def skip_rate_order(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    
    user = await db.get_user(callback.from_user.id)
    
    if not user:
        main_menu_text = await get_main_menu_text(callback.from_user.id)
        await smart_edit_or_send(callback, f"⏭️ Оценка пропущена.\n\n{main_menu_text}", reply_markup=await get_main_menu_with_role(callback.from_user.id, db), parse_mode="HTML")
    elif user.get('is_admin') and user.get('user_role') not in ['customer', 'executor']:
        await smart_edit_or_send(callback, "⏭️ Оценка пропущена.", reply_markup=get_admin_menu())
    elif user.get('user_role') == 'executor':
        menu = await get_executor_menu_with_counts(callback.from_user.id)
        await smart_edit_or_send(callback, "⏭️ Оценка пропущена.", reply_markup=menu)
    else:
        menu = await get_customer_menu_with_counts(callback.from_user.id)
        await smart_edit_or_send(callback, "⏭️ Оценка пропущена.", reply_markup=menu)
    
    await callback.answer("Оценка пропущена")

@dp.callback_query(F.data.startswith("rate_"))
async def rate_order(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    order_id = int(parts[1])
    rating = int(parts[2])
    
    await state.update_data(review_order_id=order_id, review_rating=rating)
    
    await callback.message.edit_text(
        f"Оценка: {rating}\n\nХотите добавить комментарий?",
        reply_markup=get_comment_question_keyboard(order_id)
    )
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer()

@dp.callback_query(F.data.startswith("comment_yes_"))
async def comment_yes(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "💬 Напишите комментарий:\n\n<i>Или нажмите Отмена для возврата в меню</i>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await state.set_state(LeaveReview.comment)
    await callback.answer()

@dp.callback_query(F.data.startswith("comment_no_"))
async def comment_no(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    order_id = data['review_order_id']
    rating = data['review_rating']
    
    order = await db.get_order(order_id)
    
    if callback.from_user.id == order['customer_id']:
        reviewee_id = order['executor_id']
        reviewee_role = "исполнителя"
        notify_id = order['executor_id']
        menu = get_customer_menu()
    else:
        reviewee_id = order['customer_id']
        reviewee_role = "заказчика"
        notify_id = order['customer_id']
        menu = get_executor_menu()
    
    await db.create_review(
        order_id,
        callback.from_user.id,
        reviewee_id,
        rating,
        ""
    )
    
    await callback.message.edit_text(f"✅ Спасибо за отзыв о {reviewee_role}!")
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await smart_edit_or_send(callback, "Возвращаю в меню...", reply_markup=menu)
    
    try:
        await bot.send_message(
            notify_id,
            f"⭐ <b>Новый отзыв!</b>\n\n"
            f"Заказ #{order_id}\n"
            f"От: {callback.from_user.first_name}\n"
            f"Оценка: {rating}",
            parse_mode="HTML",
            reply_markup=get_profile_keyboard(notify_id)
        )
    except:
        pass
    
    await state.clear()
    await callback.answer()

@dp.message(LeaveReview.comment)
async def leave_review_comment(message: types.Message, state: FSMContext):
    data = await state.get_data()
    
    if 'declined_order_id' in data:
        order_id = data['declined_order_id']
        rating = data['declined_rating']
        comment = message.text
        
        order = await db.get_order(order_id)
        
        await db.create_review(
            order_id,
            message.from_user.id,
            order['executor_id'],
            rating,
            comment
        )
        
        await delete_and_send(
            message,
            "✅ <b>Спасибо за вашу оценку!</b>\n\n"
            "Исполнитель получил уведомление о вашей реакции.",
            reply_markup=get_customer_menu(),
            parse_mode="HTML"
        )
        
        try:
            await bot.send_message(
                order['executor_id'],
                f"📊 <b>Заказчик отреагировал на ваш отказ</b>\n\n"
                f"📦 Заказ: {order['comment'][:50]}...\n"
                f"Оценка: {rating}/5\n"
                f"💬 Комментарий: {comment}",
                parse_mode="HTML"
            )
        except:
            pass
        
        await state.clear()
        return
    
    order_id = data['review_order_id']
    rating = data['review_rating']
    
    comment = message.text if message.text != "/skip" else ""
    
    order = await db.get_order(order_id)
    user = await db.get_user(message.from_user.id)
    
    if message.from_user.id == order['customer_id']:
        reviewee_id = order['executor_id']
        reviewee_role = "исполнителя"
        notify_id = order['executor_id']
        menu = get_customer_menu()
    else:
        reviewee_id = order['customer_id']
        reviewee_role = "заказчика"
        notify_id = order['customer_id']
        menu = get_executor_menu()
    
    await db.create_review(
        order_id,
        message.from_user.id,
        reviewee_id,
        rating,
        comment
    )
    
    await delete_and_send(message, f"✅ Спасибо за отзыв о {reviewee_role}!", reply_markup=menu)
    
    try:
        await bot.send_message(
            notify_id,
            f"⭐ <b>Новый отзыв!</b>\n\n"
            f"Заказ #{order_id}\n"
            f"От: {message.from_user.first_name}\n"
            f"Оценка: {rating}\n"
            f"{comment if comment else ''}",
            parse_mode="HTML",
            reply_markup=get_profile_keyboard(notify_id)
        )
    except:
        pass
    
    await state.clear()

@dp.callback_query(F.data == "my_profile")
async def my_profile(callback: types.CallbackQuery):
    if await check_banned(callback.from_user.id):
        await callback.answer("❌ Вы заблокированы в системе.", show_alert=True)
        return
    
    user = await db.get_user(callback.from_user.id)
    profile = await db.get_executor_profile(callback.from_user.id)
    reviews = await db.get_reviews(callback.from_user.id)
    
    days_in_project = (datetime.now() - user['created_at']).days
    username_str = f"@{user['username']}" if user['username'] else "не указан"
    
    # Gamification elements
    review_count = len(reviews)
    completed = profile['completed_orders']
    rating = profile['rating']
    
    # Determine level and progress
    if completed < 10:
        current_level = "новичок"
        next_level = "опытный"
        level_threshold = 10
        progress = completed
        bar_max = 10
    elif completed < 100:
        current_level = "опытный"
        next_level = "топ"
        level_threshold = 100
        progress = completed - 10
        bar_max = 90
    else:
        current_level = "топ"
        next_level = "топ"
        level_threshold = 100
        progress = 100
        bar_max = 100
    
    text = f"━━━━━━━━━━━━━━━━━\n\n"
    
    # Compact stats with gamification - more centered
    text += f"⭐ {rating:.1f}   •   🏆 {current_level}   •   💬 {review_count}\n\n"
    
    # Progress bar for next level
    bar_length = 10
    filled = int((progress / bar_max) * bar_length) if bar_max > 0 else bar_length
    bar = "🟩" * filled + "⬜" * (bar_length - filled)
    text += f"📊 {bar}\n"
    
    # Next level info
    if current_level != "топ":
        remaining = level_threshold - completed
        text += f"   ➜ До <b>{next_level}</b>: <b>{remaining}</b>\n\n"
    else:
        text += f"   👑 Максимальный уровень!\n\n"
    
    # Key stats - side by side
    text += f"✅ <b>{completed}</b>   •   📅 <b>{days_in_project}</b> дн.\n"
    
    text += f"\n━━━━━━━━━━━━━━━━━"
    
    await callback.message.edit_text(
        text, 
        reply_markup=get_profile_keyboard(callback.from_user.id),
        parse_mode="HTML"
    )
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer()

@dp.callback_query(F.data.startswith("show_reviews_"))
async def show_all_reviews(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[2])
    reviews = await db.get_reviews(user_id)
    
    if not reviews:
        await callback.answer("💬 Отзывов пока нет", show_alert=True)
        return
    
    text = f"<b>Все отзывы ({len(reviews)}):</b>\n\n"
    for review in reviews:
        text += f"Оценка: {review['rating']}/5\n"
        text += f"От: @{review['username'] or 'не указан'}\n"
        if review['comment']:
            text += f"💬 {review['comment']}\n"
        text += "\n"
    
    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="my_profile")]
    ])
    await smart_edit_or_send(callback, text, reply_markup=back_keyboard, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "customer_profile")
async def customer_profile(callback: types.CallbackQuery):
    """Shows customer profile with their statistics and ratings"""
    if await check_banned(callback.from_user.id):
        await callback.answer("❌ Вы заблокированы в системе.", show_alert=True)
        return
    
    user = await db.get_user(callback.from_user.id)
    reviews = await db.get_reviews(callback.from_user.id)
    
    # Get customer statistics
    active_orders = await db.get_customer_orders(callback.from_user.id)
    completed_orders = await db.get_customer_completed_orders(callback.from_user.id)
    customer_rating = float(await db.get_customer_rating(callback.from_user.id) or 0.0)
    
    days_in_project = (datetime.now() - user['created_at']).days
    username_str = f"@{user['username']}" if user['username'] else "не указан"
    
    # Calculate total orders
    total_orders = len(active_orders) + len(completed_orders)
    review_count = len(reviews)
    
    text = f"━━━━━━━━━━━━━━━━━\n\n"
    
    # Compact stats - more centered
    text += f"⭐ {customer_rating:.1f}   •   📦 {total_orders}   •   💬 {review_count}\n\n"
    
    # Key stats - side by side
    text += f"📝 Активных: <b>{len(active_orders)}</b>   •   ✅ Выполнено: <b>{len(completed_orders)}</b>\n"
    text += f"📅 Дней в проекте: <b>{days_in_project}</b>\n"
    
    text += f"\n━━━━━━━━━━━━━━━━━"
    
    await callback.message.edit_text(
        text, 
        reply_markup=get_customer_profile_keyboard(callback.from_user.id),
        parse_mode="HTML"
    )
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer()

@dp.callback_query(F.data.startswith("show_customer_reviews_"))
async def show_all_customer_reviews(callback: types.CallbackQuery):
    """Shows all reviews for a customer"""
    user_id = int(callback.data.split("_")[3])
    reviews = await db.get_reviews(user_id)
    
    if not reviews:
        await callback.answer("💬 Отзывов пока нет", show_alert=True)
        return
    
    text = f"<b>Все отзывы ({len(reviews)}):</b>\n\n"
    for review in reviews:
        text += f"Оценка: {review['rating']}/5\n"
        text += f"От: @{review['username'] or 'не указан'}\n"
        if review['comment']:
            text += f"💬 {review['comment']}\n"
        text += "\n"
    
    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="customer_profile")]
    ])
    await smart_edit_or_send(callback, text, reply_markup=back_keyboard, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "leaderboard")
async def leaderboard(callback: types.CallbackQuery):
    if await check_banned(callback.from_user.id):
        await callback.answer("❌ Вы заблокированы в системе.", show_alert=True)
        return
    
    # Получаем топ активных за 24 часа
    active_24h = await db.get_top_active_executors_24h(3)
    
    executors = await db.get_leaderboard('executor', 10)
    
    text = "🏆 <b>Топ юзеров</b>\n"
    text += "━━━━━━━━━━━━━━━\n\n"
    
    # Добавляем счетчик активных за 24 часа
    if active_24h:
        text += "🔥 <b>Топ активных (24ч):</b>\n"
        for i, exec in enumerate(active_24h, 1):
            username = f"@{exec['username']}" if exec['username'] else exec['first_name'] or 'Пользователь'
            text += f"{i}. {username} - <b>{exec['orders_24h']} заказов</b>\n"
        text += "\n"
    
    medals = ["🥇", "🥈", "🥉"]
    for i, exec in enumerate(executors):
        if i < 3:
            medal = medals[i]
        else:
            medal = f"<b>{i+1}.</b>"
        
        username = f"@{exec['username']}" if exec['username'] else exec['first_name'] or 'Пользователь'
        level_emoji = {"новичок": "🌱", "опытный": "💪", "топ": "👑"}.get(exec['level'], "🌱")
        
        text += f"{medal} {username}\n"
        text += f"    ├ ⭐ Рейтинг: <b>{exec['rating']}</b>\n"
        text += f"    ├ 📦 Заказов: <b>{exec['completed_orders']}</b>\n"
        text += f"    └ {level_emoji} <b>{exec['level'].capitalize()}</b>\n\n"
    
    if not executors:
        text += "😔 Пока нет исполнителей в рейтинге\n\n"
    
    text += "━━━━━━━━━━━━━━━\n"
    text += "💡 Выполняйте заказы, чтобы попасть в топ!"
    
    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_executor_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=back_keyboard, parse_mode="HTML")
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer()

@dp.callback_query(F.data == "top_executors")
async def top_executors(callback: types.CallbackQuery):
    if await check_banned(callback.from_user.id):
        await callback.answer("❌ Вы заблокированы в системе.", show_alert=True)
        return
    
    # Получаем топ активных за 24 часа
    active_24h = await db.get_top_active_executors_24h(3)
    
    executors = await db.get_leaderboard('executor', 10)
    
    text = "🏆 <b>Топ юзеров</b>\n"
    text += "━━━━━━━━━━━━━━━\n\n"
    
    # Добавляем счетчик активных за 24 часа
    if active_24h:
        text += "🔥 <b>Топ активных (24ч):</b>\n"
        for i, exec in enumerate(active_24h, 1):
            username = f"@{exec['username']}" if exec['username'] else exec['first_name'] or 'Пользователь'
            text += f"{i}. {username} - <b>{exec['orders_24h']} заказов</b>\n"
        text += "\n"
    
    medals = ["🥇", "🥈", "🥉"]
    for i, exec in enumerate(executors):
        if i < 3:
            medal = medals[i]
        else:
            medal = f"<b>{i+1}.</b>"
        
        username = f"@{exec['username']}" if exec['username'] else exec['first_name'] or 'Пользователь'
        level_emoji = {"новичок": "🌱", "опытный": "💪", "топ": "👑"}.get(exec['level'], "🌱")
        
        text += f"{medal} {username}\n"
        text += f"    ├ ⭐ Рейтинг: <b>{exec['rating']}</b>\n"
        text += f"    ├ 📦 Заказов: <b>{exec['completed_orders']}</b>\n"
        text += f"    └ {level_emoji} <b>{exec['level'].capitalize()}</b>\n\n"
    
    if not executors:
        text += "😔 Пока нет исполнителей в рейтинге\n\n"
    
    text += "━━━━━━━━━━━━━━━\n"
    text += "💡 Лучшие исполнители нашего сервиса!"
    
    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_customer")]
    ])
    await callback.message.edit_text(text, reply_markup=back_keyboard, parse_mode="HTML")
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer()

# REMOVED: Text handler replaced by callback handler "completed_orders"
# @dp.message(F.text == "✅ Завершённые заказы")
# async def completed_customer_orders(message: types.Message):
#     if await check_banned(message.from_user.id):
#         await message.answer("❌ Вы заблокированы в системе.")
#         return
#     
#     # Удаляем сообщение пользователя
#     try:
#         await message.delete()
#     except:
#         pass
#     
#     orders = await db.get_completed_orders(message.from_user.id, 'customer')
#     
#     if not orders:
#         await message.answer("📭 У вас нет завершённых заказов.", reply_markup=get_customer_menu())
#         return
#     
#     await message.answer(f"✅ <b>Завершённые заказы</b>\n\nВсего: {len(orders)}", parse_mode="HTML")
#     
#     for order in orders:
#         text = f"✔️ <b>Заказ #{order['order_id']}</b>\n\n"
#         text += f"💰 Цена: {order['price']} ₽\n"
#         text += f"📍 Адрес: {order['address']}\n"
#         text += f"📝 {order['comment']}\n"
#         text += f"\n✅ Завершён: {order['completed_at'].strftime('%d.%m.%Y %H:%M') if order['completed_at'] else 'N/A'}"
#         
#         await message.answer(text, parse_mode="HTML")

@dp.callback_query(F.data.startswith("open_chat_"))
async def open_chat(callback: types.CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split("_")[2])
    order = await db.get_order(order_id)
    
    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return
    
    if callback.from_user.id == order['customer_id']:
        chat_partner_id = order['executor_id']
        partner = await db.get_user(chat_partner_id)
        partner_name = partner['first_name']
    elif callback.from_user.id == order['executor_id']:
        chat_partner_id = order['customer_id']
        partner = await db.get_user(chat_partner_id)
        partner_name = partner['first_name']
    else:
        await callback.answer("У вас нет доступа к этому чату", show_alert=True)
        return
    
    chat_id = await db.get_or_create_chat(order_id, order['customer_id'], order['executor_id'])
    messages = await db.get_chat_messages(chat_id)
    
    text = f"💬 <b>Чат по заказу #{order_id}</b>\n"
    text += f"С пользователем: {partner_name}\n\n"
    
    if messages:
        for msg in reversed(messages[-10:]):
            text += f"<b>{msg['first_name']}</b>: {msg['message']}\n"
        text += "\n"
    
    text += "Отправьте сообщение или нажмите /cancel для выхода:"
    
    await smart_edit_or_send(callback, text, reply_markup=get_cancel_keyboard(), parse_mode="HTML")
    
    await state.update_data(chat_id=chat_id, chat_partner_id=chat_partner_id)
    await state.set_state(Chat.messaging)
    await callback.answer()

@dp.message(Chat.messaging)
async def chat_message(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await delete_and_send(message, "Чат закрыт.", reply_markup=await get_executor_menu_with_counts(message.from_user.id))
        return
    
    data = await state.get_data()
    chat_id = data['chat_id']
    chat_partner_id = data['chat_partner_id']
    
    await db.send_message(chat_id, message.from_user.id, message.text)
    await delete_and_send(message, "✅ Сообщение отправлено")
    
    try:
        await bot.send_message(
            chat_partner_id,
            f"💬 <b>Новое сообщение от {message.from_user.first_name}:</b>\n\n{message.text}",
            parse_mode="HTML"
        )
    except:
        pass

@dp.callback_query(F.data == "back_to_customer")
async def back_to_customer(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    user_id = callback.from_user.id
    
    days_in_project = (datetime.now() - user['created_at']).days
    active_orders = await db.get_customer_orders(user_id)
    completed_orders = await db.get_customer_completed_orders(user_id)
    customer_rating = await db.get_customer_rating(user_id)
    
    text = "👤 <b>Режим Заказчика</b>\n"
    text += "━━━━━━━━━━━━━━━\n\n"
    text += f"📅 Дней в проекте: <b>{days_in_project}</b>\n"
    text += f"⭐ Ваш рейтинг: <b>{customer_rating:.1f}</b>\n\n"
    text += f"📊 <b>Ваша статистика:</b>\n"
    text += f"├ 📝 Активных заказов: <b>{len(active_orders)}</b>\n"
    text += f"└ ✅ Выполнено заказов: <b>{len(completed_orders)}</b>\n\n"
    text += "━━━━━━━━━━━━━━━\n"
    text += "💡 Создавайте заказы и находите исполнителей!"
    
    await callback.message.edit_text(text, reply_markup=await get_customer_menu_with_counts(callback.from_user.id), parse_mode="HTML")
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer()

@dp.callback_query(F.data == "delete_all_orders")
async def delete_all_orders(callback: types.CallbackQuery):
    if await check_banned(callback.from_user.id):
        await callback.answer("❌ Вы заблокированы в системе.", show_alert=True)
        return
    
    orders = await db.get_customer_orders(callback.from_user.id)
    
    if not orders:
        await smart_edit_or_send(callback, "📭 У вас нет активных заказов.", reply_markup=await get_customer_orders_menu_with_counts(callback.from_user.id))
        await callback.answer()
        return
    
    await smart_edit_or_send(
        callback,
        f"⚠️ <b>Внимание!</b>\n\n"
        f"Вы действительно хотите удалить все активные заказы ({len(orders)} шт.)?\n\n"
        f"Заказы будут перемещены в корзину, откуда их можно восстановить.",
        reply_markup=get_delete_all_confirmation(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "deleted_orders")
async def trash_orders(callback: types.CallbackQuery):
    if await check_banned(callback.from_user.id):
        await callback.answer("❌ Вы заблокированы в системе.", show_alert=True)
        return
    
    deleted_orders = await db.get_deleted_orders(callback.from_user.id)
    
    if not deleted_orders:
        await smart_edit_or_send(
            callback,
            "♻️ <b>Корзина пуста</b>\n\nУдаленных заказов нет.",
            reply_markup=await get_customer_orders_menu_with_counts(callback.from_user.id),
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    text = f"♻️ <b>Корзина удаленных заказов</b>\n\n"
    text += f"Всего: {len(deleted_orders)}\n\n"
    
    for order in deleted_orders[:5]:
        text += f"🗑️ <b>Заказ #{order['order_id']}</b>\n"
        text += f"💰 Цена: {order['price']} ₽\n"
        text += f"📍 Адрес: {order['address']}\n"
        text += f"👥 Требуется исполнителей: {order['workers_count']}\n"
        text += f"📝 Описание: {order['comment'][:50]}...\n" if len(order['comment']) > 50 else f"📝 Описание: {order['comment']}\n"
        text += f"📅 Создан: {order['created_at'].strftime('%d.%m.%Y %H:%M')}\n\n"
    
    if len(deleted_orders) > 5:
        text += f"<i>...и ещё {len(deleted_orders) - 5} заказов</i>\n"
    
    await smart_edit_or_send(callback, text, reply_markup=await get_customer_orders_menu_with_counts(callback.from_user.id), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "completed_orders")
async def completed_orders(callback: types.CallbackQuery):
    if await check_banned(callback.from_user.id):
        await callback.answer("❌ Вы заблокированы в системе.", show_alert=True)
        return
    
    completed_orders_list = await db.get_customer_completed_orders(callback.from_user.id)
    
    if not completed_orders_list:
        await smart_edit_or_send(
            callback,
            "✅ <b>Завершенных заказов нет</b>\n\nУ вас пока нет завершенных заказов.",
            reply_markup=await get_customer_orders_menu_with_counts(callback.from_user.id),
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    text = f"✅ <b>Завершенные заказы</b>\n\n"
    text += f"Всего: {len(completed_orders_list)}\n\n"
    
    for order in completed_orders_list[:5]:
        executor_user = await db.get_user(order['executor_id']) if order['executor_id'] else None
        
        text += f"✅ <b>Заказ #{order['order_id']}</b>\n"
        text += f"💰 Цена: {order['price']} ₽\n"
        text += f"📍 Адрес: {order['address']}\n"
        if executor_user:
            text += f"⚡ Исполнитель: @{executor_user['username'] or 'не указан'}\n"
        if order['completed_at']:
            text += f"✅ Завершен: {order['completed_at'].strftime('%d.%m.%Y %H:%M')}\n"
        text += "\n"
    
    if len(completed_orders_list) > 5:
        text += f"<i>...и ещё {len(completed_orders_list) - 5} заказов</i>\n"
    
    await smart_edit_or_send(callback, text, reply_markup=await get_customer_orders_menu_with_counts(callback.from_user.id), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data.startswith("restore_order_"))
async def restore_order(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    
    await db.restore_order(order_id)
    
    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 К моим заказам", callback_data="my_orders")]
    ])
    await callback.message.edit_text(
        f"✅ Заказ #{order_id} восстановлен!",
        reply_markup=back_keyboard,
        parse_mode="HTML"
    )
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer("Заказ восстановлен!")

@dp.callback_query(F.data.startswith("permanent_delete_"))
async def permanent_delete(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    
    await db.permanent_delete_order(order_id)
    
    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 К моим заказам", callback_data="my_orders")]
    ])
    await callback.message.edit_text(
        f"🗑️ Заказ #{order_id} удален навсегда.",
        reply_markup=back_keyboard,
        parse_mode="HTML"
    )
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer("Заказ удален навсегда!")

@dp.callback_query(F.data == "main_menu")
async def back_to_main(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    menu = await get_main_menu_with_role(callback.from_user.id, db)
    text = await get_main_menu_text(callback.from_user.id)
    await callback.message.edit_text(text, reply_markup=menu, parse_mode="HTML")
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer()

@dp.callback_query(F.data == "show_current_role")
async def show_current_role(callback: types.CallbackQuery):
    """Открывает панель текущей роли пользователя"""
    user = await db.get_user(callback.from_user.id)
    
    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return
    
    # Открываем соответствующую панель в зависимости от роли
    if user.get('user_role') == 'executor':
        user_id = callback.from_user.id
        await db.ensure_executor_profile(user_id)
        profile = await db.get_executor_profile(user_id)
        days_in_project = _days_since(user['created_at'] if user else None)
        
        active_orders = await db.get_executor_orders(user_id)
        completed_orders = await db.get_executor_history(user_id)
        completed_only = [o for o in completed_orders if o['status'] == 'completed']
        total_earned = sum(float(order['price']) for order in completed_only if order['price'])
        rating_val = float(profile['rating']) if profile and profile['rating'] is not None else 0.0
        level_val = profile['level'] if profile and profile['level'] else 'новичок'
        completed_val = profile['completed_orders'] if profile and profile['completed_orders'] is not None else 0
        
        text = "⚡ <b>Режим Исполнителя</b>\n"
        text += "━━━━━━━━━━━━━━━\n\n"
        text += f"📅 Дней в проекте: <b>{days_in_project}</b>\n"
        text += f"⭐ Ваш рейтинг: <b>{rating_val:.2f}</b>\n"
        text += f"🏆 Уровень: <b>{level_val}</b>\n\n"
        text += f"📊 <b>Ваша статистика:</b>\n"
        text += f"├ 📝 Активных заказов: <b>{len(active_orders)}</b>\n"
        text += f"├ ✅ Выполнено заказов: <b>{completed_val}</b>\n"
        text += f"└ 💰 Заработано: <b>{total_earned:,.0f} ₽</b>\n\n"
        text += "━━━━━━━━━━━━━━━\n"
        text += "💡 Берите заказы и зарабатывайте!"
        
        menu = await get_executor_menu_with_counts(callback.from_user.id)
        message_id = await smart_edit_or_send(callback, text, reply_markup=menu, parse_mode="HTML")
        await db.save_last_bot_message(callback.from_user.id, message_id, callback.message.chat.id)
    else:
        user_id = callback.from_user.id
        await db.ensure_customer_profile(user_id)
        days_in_project = _days_since(user['created_at'] if user else None)
        active_orders = await db.get_customer_orders(user_id)
        completed_orders = await db.get_customer_completed_orders(user_id)
        customer_rating = float(await db.get_customer_rating(user_id) or 0.0)
        
        text = "👤 <b>Режим Заказчика</b>\n"
        text += "━━━━━━━━━━━━━━━\n\n"
        text += f"📅 Дней в проекте: <b>{days_in_project}</b>\n"
        text += f"⭐ Ваш рейтинг: <b>{customer_rating:.1f}</b>\n\n"
        text += f"📊 <b>Ваша статистика:</b>\n"
        text += f"├ 📝 Активных заказов: <b>{len(active_orders)}</b>\n"
        text += f"└ ✅ Выполнено заказов: <b>{len(completed_orders)}</b>\n\n"
        text += "━━━━━━━━━━━━━━━\n"
        text += "💡 Создавайте заказы и находите исполнителей!"
        
        menu = await get_customer_menu_with_counts(callback.from_user.id)
        message_id = await smart_edit_or_send(callback, text, reply_markup=menu, parse_mode="HTML")
        await db.save_last_bot_message(callback.from_user.id, message_id, callback.message.chat.id)
    
    await callback.answer()

@dp.callback_query(F.data == "switch_role_menu")
async def switch_role_menu(callback: types.CallbackQuery):
    """Показывает меню выбора ролей"""
    switch_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Заказчик", callback_data="role_customer")],
        [InlineKeyboardButton(text="⚡ Исполнитель", callback_data="role_executor")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
    ])
    
    await smart_edit_or_send(
        callback,
        "🔀 <b>Выберите роль:</b>\n\n"
        "👤 <b>Заказчик</b> — публикуйте заказы\n"
        "⚡ <b>Исполнитель</b> — берите заказы",
        reply_markup=switch_keyboard
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("filter_"))
async def filter_handler(callback: types.CallbackQuery):
    filter_type = callback.data.replace("filter_", "")
    filter_names = {
        "type": "Тип работы",
        "location": "Локация", 
        "price": "Цена",
        "rating": "Рейтинг"
    }
    await smart_edit_or_send(
        callback,
        f"🔍 Фильтр <b>{filter_names.get(filter_type, filter_type)}</b>\n\n"
        "⚙️ Эта функция находится в разработке.\n"
        "Скоро вы сможете фильтровать заказы!",
        reply_markup=await get_executor_menu_with_counts(callback.from_user.id),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "clear_filters")
async def clear_filters_handler(callback: types.CallbackQuery):
    await smart_edit_or_send(
        callback,
        "✅ Фильтры сброшены!\n\n"
        "⚙️ Функция фильтрации находится в разработке.",
        reply_markup=await get_executor_menu_with_counts(callback.from_user.id),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "back_to_admin")
async def back_from_admin(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    
    # Если пользователь админ - возвращаем в админ-панель, иначе в главное меню
    if user and user['is_admin']:
        await callback.message.edit_text(
            "🔐 <b>Админ-панель</b>\n"
            "─────────────\n"
            "Выберите раздел:",
            reply_markup=get_admin_menu(),
            parse_mode="HTML"
        )
    else:
        text = await get_main_menu_text(callback.from_user.id)
        menu = await get_main_menu_with_role(callback.from_user.id, db)
        await callback.message.edit_text(text, reply_markup=menu, parse_mode="HTML")
    
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer()

# ============================================
# АДМИН-ПАНЕЛЬ (обработчики в конце для низкого приоритета)
# ============================================

@dp.message(F.text == ADMIN_CODE)
async def admin_panel(message: types.Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await delete_and_send(message, "❌ Пользователь не найден.")
        return
    
    await db.make_admin(message.from_user.id)
    
    await delete_and_send(
        message,
        "🔐 <b>Админ-панель</b>\n"
        "─────────────\n"
        "Выберите раздел:",
        reply_markup=get_admin_menu(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "admin_users")
async def admin_users_menu(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or not user['is_admin']:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "👥 <b>Управление пользователями</b>\n"
        "─────────────\n"
        "Выберите действие:",
        reply_markup=get_admin_users_menu(),
        parse_mode="HTML"
    )
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer()

@dp.callback_query(F.data == "admin_find_user")
async def admin_find_user(callback: types.CallbackQuery, state: FSMContext):
    user = await db.get_user(callback.from_user.id)
    if not user or not user['is_admin']:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await smart_edit_or_send(
        callback,
        "🔍 <b>Поиск пользователя</b>\n"
        "─────────────\n"
        "Введите @username или ID пользователя:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(AdminSearchUser.waiting_username)
    await callback.answer()

@dp.message(AdminSearchUser.waiting_username)
async def admin_search_user_process(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await delete_and_send(message, "Отменено", reply_markup=get_admin_users_menu())
        return
    
    search_text = message.text.replace("@", "").strip()
    
    try:
        user_id = int(search_text)
        found_user = await db.get_user(user_id)
    except ValueError:
        users = await db.get_all_users(limit=1000)
        found_user = next((u for u in users if u.get('username') == search_text), None)
    
    if not found_user:
        await delete_and_send(message, "❌ Пользователь не найден", reply_markup=get_admin_users_menu())
        await state.clear()
        return
    
    await show_user_card(message, found_user['user_id'])
    await state.clear()

@dp.callback_query(F.data == "admin_list_executors")
async def admin_list_executors(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or not user['is_admin']:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    users = await db.get_all_users(limit=1000)
    executors = [u for u in users if u.get('user_role') in ('executor', 'both')]
    
    if not executors:
        await smart_edit_or_send(callback, "📭 Исполнителей нет", reply_markup=get_admin_users_menu())
        await callback.answer()
        return
    
    text = f"⚡ <b>Список исполнителей</b>\n"
    text += f"─────────────\n"
    text += f"Всего: {len(executors)}\n\n"
    
    for executor in executors[:10]:
        profile = await db.get_executor_profile(executor['user_id'])
        text += f"👤 @{executor.get('username') or 'не указан'}\n"
        text += f"⭐ Рейтинг: {profile['rating'] if profile else 'N/A'}\n"
        text += f"✅ Заказов: {profile['completed_orders'] if profile else 0}\n"
        text += f"ID: <code>{executor['user_id']}</code>\n\n"
    
    if len(executors) > 10:
        text += f"<i>...и ещё {len(executors) - 10} исполнителей</i>"
    
    await smart_edit_or_send(callback, text, reply_markup=get_admin_users_menu(), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "admin_list_customers")
async def admin_list_customers(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or not user['is_admin']:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    users = await db.get_all_users(limit=1000)
    customers = [u for u in users if u.get('user_role') in ('customer', 'both')]
    
    if not customers:
        await smart_edit_or_send(callback, "📭 Заказчиков нет", reply_markup=get_admin_users_menu())
        await callback.answer()
        return
    
    text = f"👤 <b>Список заказчиков</b>\n"
    text += f"─────────────\n"
    text += f"Всего: {len(customers)}\n\n"
    
    for customer in customers[:10]:
        rating = await db.get_customer_rating(customer['user_id'])
        text += f"👤 @{customer.get('username') or 'не указан'}\n"
        text += f"⭐ Рейтинг: {rating}\n"
        text += f"ID: <code>{customer['user_id']}</code>\n\n"
    
    if len(customers) > 10:
        text += f"<i>...и ещё {len(customers) - 10} заказчиков</i>"
    
    await smart_edit_or_send(callback, text, reply_markup=get_admin_users_menu(), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "admin_ban_menu")
async def admin_ban_menu(callback: types.CallbackQuery, state: FSMContext):
    user = await db.get_user(callback.from_user.id)
    if not user or not user['is_admin']:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await smart_edit_or_send(
        callback,
        "🚫 <b>Бан / Разбан пользователя</b>\n"
        "─────────────\n"
        "Введите @username или ID пользователя:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(AdminSearchUser.waiting_username)
    await callback.answer()

@dp.callback_query(F.data == "admin_edit_ratings")
async def admin_rating_menu(callback: types.CallbackQuery, state: FSMContext):
    user = await db.get_user(callback.from_user.id)
    if not user or not user['is_admin']:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await smart_edit_or_send(
        callback,
        "⭐ <b>Редактирование рейтинга</b>\n"
        "─────────────\n"
        "Введите @username или ID пользователя:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(AdminSearchUser.waiting_username)
    await callback.answer()

@dp.callback_query(F.data == "admin_reset_order")
async def admin_reset_menu(callback: types.CallbackQuery, state: FSMContext):
    user = await db.get_user(callback.from_user.id)
    if not user or not user['is_admin']:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await smart_edit_or_send(
        callback,
        "🔄 <b>Сброс активного заказа</b>\n"
        "─────────────\n"
        "Введите @username или ID пользователя:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(AdminSearchUser.waiting_username)
    await callback.answer()

async def show_user_card(message: types.Message, user_id: int):
    target_user = await db.get_user(user_id)
    if not target_user:
        await delete_and_send(message, "❌ Пользователь не найден")
        return
    
    executor_profile = await db.get_executor_profile(user_id)
    
    status = "✅ Активен" if not target_user.get('is_banned') else "🚫 Заблокирован"
    user_type = target_user.get('user_role', 'unknown')
    rating = executor_profile['rating'] if executor_profile else "N/A"
    
    text = f"─────────────\n"
    text += f"👤 <b>Пользователь #{user_id}</b>\n\n"
    text += f"Имя: {target_user.get('first_name', 'не указано')}\n"
    text += f"Username: @{target_user.get('username', 'не указан')}\n"
    text += f"Тип: {user_type}\n"
    text += f"Статус: {status}\n"
    text += f"Рейтинг: {rating}\n"
    text += f"─────────────"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚫 Заблокировать", callback_data=f"admin_ban_user_{user_id}")],
        [InlineKeyboardButton(text="✅ Разблокировать", callback_data=f"admin_unban_user_{user_id}")],
        [InlineKeyboardButton(text="⭐ Изменить рейтинг", callback_data=f"admin_edit_rating_{user_id}")],
        [InlineKeyboardButton(text="🔄 Сброс активного заказа", callback_data=f"admin_reset_order_{user_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back_to_users")]
    ])
    
    await delete_and_send(message, text, reply_markup=keyboard, parse_mode="HTML")

@dp.callback_query(F.data.startswith("admin_ban_user_"))
async def admin_ban_user_confirm(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[3])
    await db.ban_user(user_id, "Заблокирован администратором")
    await callback.message.edit_text("✅ Пользователь заблокирован")
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer("Пользователь заблокирован")

@dp.callback_query(F.data.startswith("admin_unban_user_"))
async def admin_unban_user_confirm(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[3])
    await db.unban_user(user_id)
    await callback.message.edit_text("✅ Пользователь разблокирован")
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer("Пользователь разблокирован")

@dp.callback_query(F.data.startswith("admin_edit_rating_"))
async def admin_edit_rating_start(callback: types.CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[3])
    await state.update_data(target_user_id=user_id)
    await state.set_state(AdminEditRating.waiting_rating)
    await smart_edit_or_send(
        callback,
        "⭐ Введите новый рейтинг (число от 0 до 5):",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()

@dp.message(AdminEditRating.waiting_rating)
async def admin_edit_rating_process(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await delete_and_send(message, "Отменено.", reply_markup=get_admin_menu())
        return
    
    try:
        new_rating = float(message.text)
        if new_rating < 0 or new_rating > 5:
            await delete_and_send(message, "❌ Рейтинг должен быть от 0 до 5. Попробуйте снова:")
            return
        
        data = await state.get_data()
        user_id = data['target_user_id']
        
        # Получаем роль пользователя
        user = await db.get_user(user_id)
        
        # Обновляем рейтинг в зависимости от роли
        if user['user_role'] == 'executor':
            await db.update_executor_rating(user_id, new_rating)
        else:
            await db.update_customer_rating(user_id, new_rating)
        
        await delete_and_send(
            message,
            f"✅ Рейтинг пользователя {user_id} успешно изменен на {new_rating}",
            reply_markup=get_admin_menu()
        )
        await state.clear()
    except ValueError:
        await delete_and_send(message, "❌ Неверный формат. Введите число (например: 4.5):")

@dp.callback_query(F.data.startswith("admin_reset_order_"))
async def admin_reset_order_confirm(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[3])
    
    # Сбрасываем все активные заказы пользователя
    await db.delete_all_user_orders(user_id)
    
    await smart_edit_or_send(
        callback,
        f"✅ Все активные заказы пользователя {user_id} сброшены:\n"
        f"• Заказы где он заказчик - отменены\n"
        f"• Заказы где он исполнитель - возвращены в открытые",
        reply_markup=get_admin_menu()
    )
    await callback.answer("Заказы сброшены")

@dp.callback_query(F.data == "admin_back_to_users")
async def admin_back_to_users_callback(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "👥 <b>Управление пользователями</b>\n"
        "─────────────\n"
        "Выберите действие:",
        reply_markup=get_admin_users_menu(),
        parse_mode="HTML"
    )
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer()

@dp.callback_query(F.data == "admin_orders")
async def admin_orders_menu(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or not user['is_admin']:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📦 <b>Управление заказами</b>\n"
        "─────────────\n"
        "Выберите действие:",
        reply_markup=get_admin_orders_menu(),
        parse_mode="HTML"
    )
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer()

@dp.callback_query(F.data == "admin_all_active_orders")
async def admin_all_active_orders(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or not user['is_admin']:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    orders = await db.get_all_active_orders()
    
    if not orders:
        await smart_edit_or_send(
            callback,
            "📭 <b>Активных заказов нет</b>",
            reply_markup=get_admin_orders_menu(),
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    text = f"📋 <b>Активные заказы ({len(orders)})</b>\n"
    text += "─────────────\n\n"
    
    for order in orders[:10]:
        customer = await db.get_user(order['customer_id'])
        customer_name = f"@{customer['username']}" if customer and customer['username'] else f"ID:{order['customer_id']}"
        text += f"📦 <b>Заказ #{order['order_id']}</b>\n"
        text += f"👤 Заказчик: {customer_name}\n"
        text += f"💰 Цена: {order['price']} ₽\n"
        text += f"📍 {order['address'][:30]}...\n" if len(order['address']) > 30 else f"📍 {order['address']}\n"
        text += f"📊 Статус: {order['status']}\n\n"
    
    if len(orders) > 10:
        text += f"<i>...и ещё {len(orders) - 10} заказов</i>"
    
    await smart_edit_or_send(callback, text, reply_markup=get_admin_orders_menu(), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "admin_search_order")
async def admin_search_order(callback: types.CallbackQuery, state: FSMContext):
    user = await db.get_user(callback.from_user.id)
    if not user or not user['is_admin']:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await smart_edit_or_send(
        callback,
        "🔍 <b>Поиск заказа</b>\n"
        "─────────────\n"
        "Введите ID заказа:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(AdminSearchOrder.waiting_order_id)
    await callback.answer()

@dp.callback_query(F.data == "admin_stop_recruiting")
async def admin_stop_recruiting(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or not user['is_admin']:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await smart_edit_or_send(
        callback,
        "⏸️ <b>Остановка набора</b>\n\n"
        "⚙️ Эта функция находится в разработке.",
        reply_markup=get_admin_orders_menu(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_change_status")
async def admin_change_status(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or not user['is_admin']:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await smart_edit_or_send(
        callback,
        "📝 <b>Изменение статуса</b>\n\n"
        "⚙️ Эта функция находится в разработке.",
        reply_markup=get_admin_orders_menu(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_edit_order")
async def admin_edit_order(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or not user['is_admin']:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await smart_edit_or_send(
        callback,
        "✏️ <b>Редактирование заказа</b>\n\n"
        "⚙️ Эта функция находится в разработке.",
        reply_markup=get_admin_orders_menu(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_delete_order")
async def admin_delete_order(callback: types.CallbackQuery, state: FSMContext):
    user = await db.get_user(callback.from_user.id)
    if not user or not user['is_admin']:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await smart_edit_or_send(
        callback,
        "⚠️ <b>Удаление заказа</b>\n"
        "─────────────\n"
        "Введите ID заказа для удаления:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(AdminDeleteOrder.waiting_order_id)
    await callback.answer()

@dp.message(AdminSearchOrder.waiting_order_id)
async def admin_search_order_process(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await delete_and_send(message, "Отменено", reply_markup=get_admin_orders_menu())
        return
    
    try:
        order_id = int(message.text)
        order = await db.get_order(order_id)
        
        if not order:
            await delete_and_send(message, "❌ Заказ не найден", reply_markup=get_admin_orders_menu())
            await state.clear()
            return
        
        customer = await db.get_user(order['customer_id'])
        executor = await db.get_user(order['executor_id']) if order['executor_id'] else None
        
        text = f"📦 <b>Заказ #{order['order_id']}</b>\n"
        text += "─────────────\n\n"
        text += f"📊 Статус: {order['status']}\n"
        text += f"👤 Заказчик: @{customer['username'] if customer and customer['username'] else 'N/A'}\n"
        if executor:
            text += f"⚡ Исполнитель: @{executor['username'] if executor['username'] else 'N/A'}\n"
        text += f"\n💰 Цена: {order['price']} ₽\n"
        text += f"📍 Адрес: {order['address']}\n"
        text += f"📝 Описание: {order['comment']}\n"
        text += f"📅 Создан: {order['created_at'].strftime('%d.%m.%Y %H:%M')}\n"
        
        await delete_and_send(message, text, reply_markup=get_admin_orders_menu(), parse_mode="HTML")
        await state.clear()
    except ValueError:
        await delete_and_send(message, "❌ Введите числовой ID заказа")

@dp.message(AdminDeleteOrder.waiting_order_id)
async def admin_delete_order_process(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await delete_and_send(message, "Отменено", reply_markup=get_admin_orders_menu())
        return
    
    try:
        order_id = int(message.text)
        order = await db.get_order(order_id)
        
        if not order:
            await delete_and_send(message, "❌ Заказ не найден", reply_markup=get_admin_orders_menu())
            await state.clear()
            return
        
        await db.delete_order(order_id)
        await delete_and_send(
            message,
            f"✅ Заказ #{order_id} удален администратором",
            reply_markup=get_admin_orders_menu()
        )
        await state.clear()
    except ValueError:
        await delete_and_send(message, "❌ Введите числовой ID заказа")

@dp.callback_query(F.data == "admin_complaints")
async def admin_complaints_menu(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or not user['is_admin']:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    new_count = await db.get_complaints_count('new')
    resolved_count = await db.get_complaints_count('resolved')
    
    await callback.message.edit_text(
        "⚠️ <b>Жалобы / обращения</b>\n"
        "─────────────\n"
        f"📥 Новых: {new_count}\n"
        f"✅ Решённых: {resolved_count}\n\n"
        "Выберите действие:",
        reply_markup=get_admin_complaints_menu(),
        parse_mode="HTML"
    )
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer()

@dp.callback_query(F.data == "admin_new_complaints")
async def admin_new_complaints(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or not user['is_admin']:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    complaints = await db.get_complaints('new')
    
    if not complaints:
        await smart_edit_or_send(
            callback,
            "📭 <b>Новых жалоб нет</b>",
            reply_markup=get_admin_complaints_menu(),
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    text = f"📥 <b>Новые жалобы ({len(complaints)})</b>\n"
    text += "─────────────\n\n"
    
    for complaint in complaints[:5]:
        complaint_user = await db.get_user(complaint['user_id'])
        username = f"@{complaint_user['username']}" if complaint_user and complaint_user['username'] else f"ID:{complaint['user_id']}"
        text += f"#{complaint['complaint_id']} от {username}\n"
        text += f"Тип: {complaint['complaint_type']}\n"
        text += f"Описание: {complaint['description'][:50]}...\n\n" if len(complaint['description']) > 50 else f"Описание: {complaint['description']}\n\n"
    
    if len(complaints) > 5:
        text += f"<i>...и ещё {len(complaints) - 5} жалоб</i>"
    
    await smart_edit_or_send(callback, text, reply_markup=get_admin_complaints_menu(), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "admin_resolved_complaints")
async def admin_resolved_complaints(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or not user['is_admin']:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    complaints = await db.get_complaints('resolved')
    
    if not complaints:
        await smart_edit_or_send(
            callback,
            "📭 <b>Решённых жалоб нет</b>",
            reply_markup=get_admin_complaints_menu(),
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    text = f"✅ <b>Решённые жалобы ({len(complaints)})</b>\n"
    text += "─────────────\n\n"
    
    for complaint in complaints[:5]:
        complaint_user = await db.get_user(complaint['user_id'])
        username = f"@{complaint_user['username']}" if complaint_user and complaint_user['username'] else f"ID:{complaint['user_id']}"
        text += f"#{complaint['complaint_id']} от {username}\n"
        text += f"Тип: {complaint['complaint_type']}\n"
        text += f"Описание: {complaint['description'][:50]}...\n\n" if len(complaint['description']) > 50 else f"Описание: {complaint['description']}\n\n"
    
    if len(complaints) > 5:
        text += f"<i>...и ещё {len(complaints) - 5} жалоб</i>"
    
    await smart_edit_or_send(callback, text, reply_markup=get_admin_complaints_menu(), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "admin_all_complaints")
async def admin_all_complaints(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or not user['is_admin']:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    complaints = await db.get_complaints()
    
    if not complaints:
        await smart_edit_or_send(
            callback,
            "📭 <b>Жалоб нет</b>",
            reply_markup=get_admin_complaints_menu(),
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    text = f"📋 <b>Все жалобы ({len(complaints)})</b>\n"
    text += "─────────────\n\n"
    
    for complaint in complaints[:5]:
        complaint_user = await db.get_user(complaint['user_id'])
        username = f"@{complaint_user['username']}" if complaint_user and complaint_user['username'] else f"ID:{complaint['user_id']}"
        text += f"#{complaint['complaint_id']} от {username}\n"
        text += f"Тип: {complaint['complaint_type']}\n"
        text += f"Статус: {'✅ Решено' if complaint['status'] == 'resolved' else '📥 Новая'}\n"
        text += f"Описание: {complaint['description'][:50]}...\n\n" if len(complaint['description']) > 50 else f"Описание: {complaint['description']}\n\n"
    
    if len(complaints) > 5:
        text += f"<i>...и ещё {len(complaints) - 5} жалоб</i>"
    
    await smart_edit_or_send(callback, text, reply_markup=get_admin_complaints_menu(), parse_mode="HTML")
    await callback.answer()

async def show_complaint_card(message: types.Message, complaint):
    complaint_id = complaint['complaint_id']
    user_id = complaint['user_id']
    complaint_type = complaint['complaint_type']
    target_id = complaint['target_id']
    description = complaint['description']
    status = complaint['status']
    created_at = complaint['created_at'].strftime("%d.%m.%Y %H:%M")
    
    user = await db.get_user(user_id)
    username = f"@{user['username']}" if user and user['username'] else f"ID:{user_id}"
    
    type_emoji = {
        'order': '📦',
        'user': '👤',
        'idea': '💡'
    }
    
    type_text = {
        'order': 'Жалоба на объявление',
        'user': 'Жалоба на пользователя',
        'idea': 'Идея'
    }
    
    status_emoji = '📥' if status == 'new' else '✅'
    
    text = f"{status_emoji} <b>Жалоба #{complaint_id}</b>\n"
    text += f"{type_emoji.get(complaint_type, '📝')} {type_text.get(complaint_type, 'Обращение')}\n"
    text += f"👤 От: {username}\n"
    
    if target_id:
        if complaint_type == 'order':
            text += f"📦 Объявление: #{target_id}\n"
            # Получаем информацию о создателе объявления
            try:
                order = await db.get_order(int(target_id))
                if order:
                    customer = await db.get_user(order['customer_id'])
                    customer_username = f"@{customer['username']}" if customer and customer['username'] else f"ID:{order['customer_id']}"
                    text += f"👤 Создатель объявления: {customer_username}\n"
            except (ValueError, TypeError):
                pass
        elif complaint_type == 'user':
            target_user = await db.get_user(int(target_id))
            target_username = f"@{target_user['username']}" if target_user and target_user['username'] else f"ID:{target_id}"
            text += f"👤 На пользователя: {target_username}\n"
    
    text += f"📝 {description}\n"
    text += f"📅 {created_at}\n"
    
    if status == 'resolved' and complaint.get('resolved_at'):
        resolved_at = complaint['resolved_at'].strftime("%d.%m.%Y %H:%M")
        text += f"✅ Решена: {resolved_at}\n"
        if complaint.get('admin_note'):
            text += f"💬 Заметка: {complaint['admin_note']}\n"
    
    keyboard = get_complaint_actions(complaint_id) if status == 'new' else None
    await delete_and_send(message, text, reply_markup=keyboard, parse_mode="HTML")

@dp.callback_query(F.data.startswith("resolve_complaint_"))
async def resolve_complaint_callback(callback: types.CallbackQuery, state: FSMContext):
    user = await db.get_user(callback.from_user.id)
    if not user or not user['is_admin']:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    complaint_id = int(callback.data.split("_")[2])
    
    await callback.message.edit_reply_markup(reply_markup=None)
    await smart_edit_or_send(
        callback,
        f"✅ <b>Решение жалобы #{complaint_id}</b>\n\n"
        "Введите заметку (или напишите '-' чтобы пропустить):",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    
    await state.update_data(complaint_id=complaint_id)
    await state.set_state(AdminResolveComplaint.waiting_note)
    await callback.answer()

@dp.message(AdminResolveComplaint.waiting_note)
async def admin_resolve_note(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        # Запрашиваем подтверждение отмены
        data = await state.get_data()
        complaint_id = data.get('complaint_id')
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, отложить", callback_data=f"confirm_postpone_{complaint_id}")],
            [InlineKeyboardButton(text="❌ Нет, продолжить решение", callback_data=f"continue_resolve_{complaint_id}")]
        ])
        
        await delete_and_send(
            message,
            "⚠️ Вы действительно хотите отложить решение вопроса на потом?",
            reply_markup=keyboard
        )
        return
    
    data = await state.get_data()
    complaint_id = data['complaint_id']
    note = message.text.strip() if message.text.strip() != '-' else None
    
    complaint = await db.get_complaint(complaint_id)
    if not complaint:
        await delete_and_send(message, "❌ Жалоба не найдена", reply_markup=get_admin_complaints_menu())
        await state.clear()
        return
    
    await db.resolve_complaint(complaint_id, note)
    
    success, error_msg = await send_complaint_resolution_notification(complaint, note)
    
    if success:
        await delete_and_send(
            message,
            f"✅ Жалоба #{complaint_id} отмечена как решённая\n"
            f"✅ Пользователь получил уведомление",
            reply_markup=get_admin_complaints_menu()
        )
    else:
        await delete_and_send(
            message,
            f"✅ Жалоба #{complaint_id} отмечена как решённая\n"
            f"⚠️ Не удалось отправить уведомление пользователю\n"
            f"Причина: {error_msg}",
            reply_markup=get_admin_complaints_menu()
        )
    await state.clear()

@dp.callback_query(F.data.startswith("confirm_postpone_"))
async def confirm_postpone_complaint(callback: types.CallbackQuery, state: FSMContext):
    """Подтверждение отложить решение жалобы"""
    user = await db.get_user(callback.from_user.id)
    if not user or not user['is_admin']:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    complaint_id = int(callback.data.split("_")[2])
    
    # Очищаем состояние
    await state.clear()
    
    # Уведомление о том, что жалоба отложена (останется в новых)
    await callback.message.edit_text(
        f"📋 Решение жалобы #{complaint_id} отложено.\n"
        f"Жалоба остаётся в разделе 'Новые жалобы'.",
        parse_mode="HTML"
    )
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    
    # Возвращаем клавиатуру админ-панели жалоб
    await smart_edit_or_send(
        callback,
        "Выберите действие:",
        reply_markup=get_admin_complaints_menu()
    )
    
    await callback.answer("✅ Решение отложено")

@dp.callback_query(F.data.startswith("continue_resolve_"))
async def continue_resolve_complaint(callback: types.CallbackQuery, state: FSMContext):
    """Продолжить решение жалобы после нажатия отмены"""
    user = await db.get_user(callback.from_user.id)
    if not user or not user['is_admin']:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    complaint_id = int(callback.data.split("_")[2])
    
    # Возвращаемся к вводу заметки
    await callback.message.edit_text(
        f"✅ <b>Решение жалобы #{complaint_id}</b>\n\n"
        "Введите заметку (или напишите '-' чтобы пропустить):",
        parse_mode="HTML"
    )
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    
    await state.update_data(complaint_id=complaint_id)
    await state.set_state(AdminResolveComplaint.waiting_note)
    await callback.answer("↩️ Продолжаем решение")

async def send_complaint_resolution_notification(complaint, admin_note):
    user_id = complaint['user_id']
    complaint_id = complaint['complaint_id']
    complaint_type = complaint['complaint_type']
    target_id = complaint['target_id']
    description = complaint['description']
    
    type_emoji = {
        'order': '📦',
        'user': '👤',
        'idea': '💡'
    }
    
    type_text = {
        'order': 'жалобу на объявление',
        'user': 'жалобу на пользователя',
        'idea': 'вашу идею'
    }
    
    notification = f"🔔 <b>УВЕДОМЛЕНИЕ ОТ АДМИНИСТРАЦИИ</b>\n\n"
    notification += f"Администрация рассмотрела {type_text.get(complaint_type, 'ваше обращение')} #{complaint_id}\n\n"
    
    notification += f"{type_emoji.get(complaint_type, '📝')} <b>Ваше обращение:</b>\n"
    
    if complaint_type == 'order' and target_id:
        notification += f"📦 Объявление: #{target_id}\n"
    elif complaint_type == 'user' and target_id:
        target_user = await db.get_user(int(target_id))
        target_username = f"@{target_user['username']}" if target_user and target_user['username'] else f"ID:{target_id}"
        notification += f"👤 Пользователь: {target_username}\n"
    
    notification += f"📝 {description}\n\n"
    
    if admin_note:
        notification += f"💬 <b>Реакция администрации:</b>\n{admin_note}\n\n"
    else:
        notification += f"✅ <b>Статус:</b> Меры приняты\n\n"
    
    notification += f"Спасибо за ваше обращение!"
    
    try:
        await bot.send_message(
            user_id,
            notification,
            parse_mode="HTML"
        )
        return True, None
    except Exception as e:
        error_msg = str(e)
        logging.error(f"Failed to send complaint resolution notification to user {user_id}: {e}")
        return False, error_msg

@dp.callback_query(F.data == "complaints_back")
async def complaints_back_callback(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or not user['is_admin']:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    # Показываем меню жалоб заново
    new_count = await db.get_complaints_count('new')
    resolved_count = await db.get_complaints_count('resolved')
    
    await smart_edit_or_send(
        callback,
        "⚠️ <b>Жалобы / обращения</b>\n"
        "─────────────\n"
        f"📥 Новых: {new_count}\n"
        f"✅ Решённых: {resolved_count}\n\n"
        "Выберите действие:",
        reply_markup=get_admin_complaints_menu(),
        parse_mode="HTML"
    )
    
    await callback.answer()

# REMOVED: Text handler replaced by callback handler "admin_settings"
# @dp.message(F.text == "⚙️ Настройки проекта")
# async def admin_settings_menu(message: types.Message):
#     user = await db.get_user(message.from_user.id)
#     if not user or not user['is_admin']:
#         return
#     
#     try:
#         await message.delete()
#     except:
#         pass
#     
#     await message.answer(
#         "⚙️ <b>Настройки проекта</b>\n"
#         "─────────────\n"
#         "Выберите параметр:",
#         reply_markup=get_admin_settings_menu(),
#         parse_mode="HTML"
#     )

@dp.callback_query(F.data == "admin_settings")
async def admin_my_settings(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or not user['is_admin']:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    settings = await db.get_admin_notification_settings(callback.from_user.id)
    sensitivity = await db.get_moderation_sensitivity()
    
    text = "⚙️ <b>Мои настройки</b>\n\n"
    text += "Управляйте своими уведомлениями и глобальной защитой системы:"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_admin_settings_keyboard(
            settings['suspicious_orders_notifications'],
            settings['complaints_notifications'],
            settings['quiet_mode'],
            sensitivity
        ),
        parse_mode="HTML"
    )
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer()

@dp.callback_query(F.data == "toggle_quiet_mode")
async def toggle_quiet_mode_handler(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or not user['is_admin']:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    # Переключаем режим спокойствия
    new_quiet_mode = await db.toggle_quiet_mode(callback.from_user.id)
    
    # Обновляем клавиатуру
    updated_settings = await db.get_admin_notification_settings(callback.from_user.id)
    sensitivity = await db.get_moderation_sensitivity()
    await callback.message.edit_reply_markup(
        reply_markup=get_admin_settings_keyboard(
            updated_settings['suspicious_orders_notifications'],
            updated_settings['complaints_notifications'],
            updated_settings['quiet_mode'],
            sensitivity
        )
    )
    
    # Отправляем уведомление
    if new_quiet_mode:
        await callback.answer("🔕 Режим спокойствия активирован")
    else:
        await callback.answer("🔔 Режим спокойствия отключен")

@dp.callback_query(F.data == "toggle_suspicious_notif")
async def toggle_suspicious_notifications(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or not user['is_admin']:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    settings = await db.get_admin_notification_settings(callback.from_user.id)
    new_value = not settings['suspicious_orders_notifications']
    
    await db.toggle_notifications(callback.from_user.id, 'suspicious_orders', new_value)
    
    # Обновляем клавиатуру
    updated_settings = await db.get_admin_notification_settings(callback.from_user.id)
    sensitivity = await db.get_moderation_sensitivity()
    await callback.message.edit_reply_markup(
        reply_markup=get_admin_settings_keyboard(
            updated_settings['suspicious_orders_notifications'],
            updated_settings['complaints_notifications'],
            updated_settings['quiet_mode'],
            sensitivity
        )
    )
    
    status = "включены" if new_value else "выключены"
    await callback.answer(f"Уведомления о подозрительных объявлениях {status}")

@dp.callback_query(F.data == "toggle_complaints_notif")
async def toggle_complaints_notifications(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or not user['is_admin']:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    settings = await db.get_admin_notification_settings(callback.from_user.id)
    new_value = not settings['complaints_notifications']
    
    await db.toggle_notifications(callback.from_user.id, 'complaints', new_value)
    
    # Обновляем клавиатуру
    updated_settings = await db.get_admin_notification_settings(callback.from_user.id)
    sensitivity = await db.get_moderation_sensitivity()
    await callback.message.edit_reply_markup(
        reply_markup=get_admin_settings_keyboard(
            updated_settings['suspicious_orders_notifications'],
            updated_settings['complaints_notifications'],
            updated_settings['quiet_mode'],
            sensitivity
        )
    )
    
    status = "включены" if new_value else "выключены"
    await callback.answer(f"Уведомления о жалобах {status}")

@dp.callback_query(F.data == "change_moderation_sensitivity")
async def change_moderation_sensitivity(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or not user['is_admin']:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    text = (
        "🛡️ <b>Настройка защиты ИИ</b>\n\n"
        "⚠️ <b>ГЛОБАЛЬНАЯ НАСТРОЙКА</b> - применяется ко всем объявлениям\n\n"
        "Выберите уровень чувствительности:\n\n"
        "⚪ <b>Выключена</b> - все объявления публикуются\n"
        "🟢 <b>Низкая</b> - только явно подозрительное\n"
        "🟡 <b>Средняя</b> - рекомендуется (риск ≥ 4)\n"
        "🔴 <b>Высокая</b> - строгая проверка (риск ≥ 2)"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_moderation_sensitivity_keyboard(),
        parse_mode="HTML"
    )
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer()

@dp.callback_query(F.data.startswith("sensitivity_"))
async def set_sensitivity(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or not user['is_admin']:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    # Обработка "Назад"
    if callback.data == "sensitivity_back":
        settings = await db.get_admin_notification_settings(callback.from_user.id)
        sensitivity = await db.get_moderation_sensitivity()
        
        text = "⚙️ <b>Мои настройки</b>\n\n"
        text += "Управляйте своими уведомлениями и защитой:"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_admin_settings_keyboard(
                settings['suspicious_orders_notifications'],
                settings['complaints_notifications'],
                settings['quiet_mode'],
                sensitivity
            ),
            parse_mode="HTML"
        )
        await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
        await callback.answer()
        return
    
    # Получаем новый уровень
    new_sensitivity = callback.data.replace("sensitivity_", "")
    
    # Сохраняем глобальную настройку (указываем кто изменил)
    await db.set_moderation_sensitivity(new_sensitivity, callback.from_user.id)
    
    # Сообщения для уведомления
    sensitivity_names = {
        'off': '⚪ Выключена',
        'low': '🟢 Низкая',
        'medium': '🟡 Средняя',
        'high': '🔴 Высокая'
    }
    
    await callback.answer(f"Защита ИИ: {sensitivity_names.get(new_sensitivity, 'Средняя')}", show_alert=True)
    
    # Возвращаемся в настройки
    settings = await db.get_admin_notification_settings(callback.from_user.id)
    
    text = "⚙️ <b>Мои настройки</b>\n\n"
    text += "Управляйте своими уведомлениями и защитой:"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_admin_settings_keyboard(
            settings['suspicious_orders_notifications'],
            settings['complaints_notifications'],
            settings['quiet_mode'],
            new_sensitivity
        ),
        parse_mode="HTML"
    )
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)

@dp.callback_query(F.data == "admin_settings_back")
async def admin_settings_back(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or not user['is_admin']:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    try:
        await callback.message.delete()
    except:
        pass
    
    await bot.send_message(
        callback.from_user.id,
        "🔐 <b>Админ-панель</b>\n"
        "─────────────\n"
        "Выберите раздел:",
        reply_markup=get_admin_menu(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_suspicious")
async def admin_suspicious_orders(callback: types.CallbackQuery):
    """Перенаправляет на полную версию подозрительных объявлений"""
    await go_to_suspicious_orders(callback)

@dp.callback_query(F.data.startswith("block_order_"))
async def block_suspicious_order(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or not user['is_admin']:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    order_id = int(callback.data.split("_")[2])
    
    # Блокируем заказ (помечаем как удаленный)
    await db.delete_order(order_id)
    
    await callback.message.edit_text(
        f"🚫 <b>Объявление #{order_id} заблокировано</b>\n\n"
        "Заказ удален из ленты.",
        parse_mode="HTML"
    )
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer("✅ Заказ заблокирован")

@dp.callback_query(F.data == "suspicious_back")
async def suspicious_back(callback: types.CallbackQuery):
    try:
        await callback.message.delete()
    except:
        pass
    await callback.answer()

@dp.callback_query(F.data == "admin_exit")
async def admin_exit(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or not user['is_admin']:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    text = await get_main_menu_text(callback.from_user.id)
    menu = await get_main_menu_with_role(callback.from_user.id, db)
    await callback.message.edit_text(text, reply_markup=menu, parse_mode="HTML")
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer()

@dp.callback_query(F.data == "admin_all_users")
async def admin_users(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or not user['is_admin']:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    users = await db.get_all_users(limit=10)
    
    if not users:
        back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back_to_users")]
        ])
        await smart_edit_or_send(callback, "📭 Пользователей нет.", reply_markup=back_keyboard)
        await callback.answer()
        return
    
    text = "👥 <b>Список пользователей:</b>\n\n"
    for u in users:
        status = "🚫" if u['is_banned'] else "✅"
        role_emoji = "👤" if u['user_role'] == 'customer' else "⚡"
        text += f"{status} {role_emoji} <b>{u['first_name']}</b> (@{u['username'] or 'нет'}) - ID: <code>{u['user_id']}</code>\n"
    
    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back_to_users")]
    ])
    await smart_edit_or_send(callback, text, reply_markup=back_keyboard, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or not user['is_admin']:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    stats = await db.get_stats()
    users = await db.get_all_users(limit=1000)
    
    banned_count = sum(1 for u in users if u['is_banned'])
    executors_count = sum(1 for u in users if u.get('user_role') == 'executor' or u.get('user_role') == 'both')
    customers_count = sum(1 for u in users if u.get('user_role') == 'customer' or u.get('user_role') == 'both')
    
    await callback.message.edit_text(
        "📊 <b>Статистика</b>\n"
        "─────────────\n"
        f"👥 Пользователи: {stats['total_users']}\n"
        f"⚡ Исполнители: {executors_count}\n"
        f"👤 Заказчиков: {customers_count}\n\n"
        f"📦 Активных заказов: {stats['active_orders']}\n"
        f"✅ Завершённых: {stats['completed_orders']}\n"
        f"❌ Отменённых: 0\n\n"
        f"⭐ Средний рейтинг: 4.6\n"
        f"⚠️ Жалоб за месяц: 0\n"
        "─────────────",
        reply_markup=get_admin_menu(),
        parse_mode="HTML"
    )
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer()

@dp.callback_query(F.data == "admin_logs")
async def admin_logs(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or not user['is_admin']:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📝 <b>Логи действий</b>\n"
        "─────────────\n"
        "Последние действия администраторов:\n\n"
        "• Пока нет записей\n"
        "─────────────",
        reply_markup=get_admin_menu(),
        parse_mode="HTML"
    )
    await db.save_last_bot_message(callback.from_user.id, callback.message.message_id, callback.message.chat.id)
    await callback.answer()

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: types.CallbackQuery, state: FSMContext):
    user = await db.get_user(callback.from_user.id)
    if not user or not user['is_admin']:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await smart_edit_or_send(
        callback,
        "📢 <b>Рассылка всем пользователям</b>\n\n"
        "Введите сообщение для рассылки:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(Broadcast.message)
    await callback.answer()

@dp.message(Broadcast.message)
async def admin_broadcast_send(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await delete_and_send(message, "Отменено.", reply_markup=get_admin_menu())
        return
    
    users = await db.get_all_users(limit=10000)
    sent = 0
    
    try:
        await message.delete()
    except Exception as e:
        logger.debug(f"Не удалось удалить сообщение пользователя: {e}")
    
    status_msg = await bot.send_message(message.chat.id, f"📤 Отправка... 0/{len(users)}")
    await db.save_last_bot_message(message.from_user.id, status_msg.message_id, message.chat.id)
    
    for i, user in enumerate(users):
        try:
            await bot.send_message(user['user_id'], f"📢 <b>Уведомление от администрации:</b>\n\n{message.text}", parse_mode="HTML")
            sent += 1
            if (i + 1) % 10 == 0:
                await status_msg.edit_text(f"📤 Отправка... {i+1}/{len(users)}")
        except Exception as e:
            logger.error(f"Failed to send to {user['user_id']}: {e}")
    
    await status_msg.edit_text(f"✅ Рассылка завершена!\n\nОтправлено: {sent}/{len(users)}")
    await state.clear()

@dp.callback_query(F.data.startswith("admin_view_"))
async def admin_view_user_profile(callback: types.CallbackQuery):
    target_id = int(callback.data.split("_")[2])
    target_user = await db.get_user(target_id)
    
    if not target_user:
        await callback.answer("❌ Пользователь не найден.", show_alert=True)
        return
    
    exec_profile = await db.get_executor_profile(target_id)
    reviews = await db.get_reviews(target_id)
    
    status = "🚫 ЗАБАНЕН" if target_user['is_banned'] else "✅ Активен"
    
    text = f"👤 <b>Профиль пользователя</b>\n\n"
    text += f"Статус: {status}\n"
    text += f"Имя: {target_user['first_name']}\n"
    text += f"Username: @{target_user['username'] or 'нет'}\n"
    text += f"ID: <code>{target_id}</code>\n"
    text += f"Роль: {target_user['user_role']}\n\n"
    
    if exec_profile:
        text += f"⭐ Рейтинг: {exec_profile['rating']}\n"
        text += f"📦 Выполнено заказов: {exec_profile['completed_orders']}\n"
        text += f"🏆 Уровень: {exec_profile['level']}\n\n"
    
    text += f"💬 Отзывов: {len(reviews)}\n"
    
    if target_user['is_banned']:
        text += f"\n🚫 <b>Причина бана:</b> {target_user['ban_reason']}"
    
    await smart_edit_or_send(callback, text, reply_markup=get_user_actions(target_id), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data.startswith("admin_ban_"))
async def admin_ban_user(callback: types.CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[2])
    await state.update_data(ban_user_id=user_id)
    await smart_edit_or_send(callback, "Введите причину бана:", reply_markup=get_cancel_keyboard())
    await state.set_state(AdminBan.reason)
    await callback.answer()

@dp.message(AdminBan.reason)
async def admin_ban_reason(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await delete_and_send(message, "Отменено.", reply_markup=get_admin_menu())
        return
    
    data = await state.get_data()
    user_id = data['ban_user_id']
    
    await db.ban_user(user_id, message.text)
    
    # Удаляем все активные заказы забаненного пользователя
    await db.delete_all_user_orders(user_id)
    
    await delete_and_send(
        message,
        f"✅ Пользователь {user_id} заблокирован.\n"
        f"✅ Все его активные объявления удалены из ленты.",
        reply_markup=get_admin_menu()
    )
    
    try:
        await bot.send_message(user_id, f"🚫 Вы были заблокированы.\n\nПричина: {message.text}")
    except:
        pass
    
    await state.clear()

@dp.callback_query(F.data.startswith("admin_unban_"))
async def admin_unban_user(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[2])
    await db.unban_user(user_id)
    await smart_edit_or_send(callback, f"✅ Пользователь {user_id} разблокирован.")
    
    try:
        await bot.send_message(user_id, "✅ Вы были разблокированы. Добро пожаловать обратно!")
    except:
        pass
    
    await callback.answer()

@dp.callback_query(F.data.startswith("admin_msg_"))
async def admin_send_message(callback: types.CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[2])
    await state.update_data(msg_user_id=user_id)
    await smart_edit_or_send(callback, "Введите сообщение для отправки:", reply_markup=get_cancel_keyboard())
    await state.set_state(AdminMessage.message)
    await callback.answer()

@dp.message(AdminMessage.message)
async def admin_send_message_text(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await delete_and_send(message, "Отменено.", reply_markup=get_admin_menu())
        return
    
    data = await state.get_data()
    user_id = data['msg_user_id']
    
    try:
        await bot.send_message(user_id, f"📨 <b>Сообщение от администрации:</b>\n\n{message.text}", parse_mode="HTML")
        await delete_and_send(message, f"✅ Сообщение отправлено пользователю {user_id}", reply_markup=get_admin_menu())
    except Exception as e:
        await delete_and_send(message, f"❌ Ошибка отправки: {e}", reply_markup=get_admin_menu())
    
    await state.clear()

# ============================================
# MISSING HANDLERS (СТАБЫ)
# ============================================

@dp.callback_query(F.data.startswith("sensitivity_"))
async def handle_sensitivity(callback: types.CallbackQuery):
    sensitivity = callback.data.replace("sensitivity_", "")
    await db.set_moderation_sensitivity(sensitivity, callback.from_user.id)
    settings = await db.get_admin_notification_settings(callback.from_user.id)
    new_sensitivity = await db.get_moderation_sensitivity()
    await callback.message.edit_reply_markup(
        reply_markup=get_admin_settings_keyboard(
            settings['suspicious_orders_notifications'],
            settings['complaints_notifications'],
            settings['quiet_mode'],
            new_sensitivity
        )
    )
    await callback.answer(f"✅ Уровень защиты установлен: {sensitivity}")

@dp.callback_query(F.data == "sensitivity_back")
async def sensitivity_back_handler(callback: types.CallbackQuery):
    await admin_my_settings(callback)

@dp.callback_query(F.data.startswith("work_"))
async def handle_work_type(callback: types.CallbackQuery, state: FSMContext):
    work_type = callback.data.replace("work_", "")
    await state.update_data(work_type=work_type)
    await smart_edit_or_send(callback, "⏰ Укажите время работы (например: 14:00)", reply_markup=get_cancel_keyboard())
    await state.set_state(CreateOrder.start_time)
    await callback.answer()

@dp.callback_query(F.data.startswith("filter_"))
async def handle_filters(callback: types.CallbackQuery):
    filter_type = callback.data.replace("filter_", "")
    filter_names = {"type": "Тип работы", "location": "Локация", "price": "Цена", "rating": "Рейтинг"}
    await smart_edit_or_send(callback, f"🔍 Фильтр <b>{filter_names.get(filter_type, filter_type)}</b>\n\n⚙️ Эта функция находится в разработке.", 
        reply_markup=await get_executor_menu_with_counts(callback.from_user.id), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "admin_commission")
async def admin_commission(callback: types.CallbackQuery):
    await smart_edit_or_send(callback, "💰 <b>Комиссия</b>\n\n⚙️ В разработке", reply_markup=get_admin_menu(), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "admin_min_price")
async def admin_min_price(callback: types.CallbackQuery):
    await smart_edit_or_send(callback, "💵 <b>Минимальная цена</b>\n\n⚙️ В разработке", reply_markup=get_admin_menu(), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "admin_executor_limit")
async def admin_executor_limit(callback: types.CallbackQuery):
    await smart_edit_or_send(callback, "👥 <b>Лимит исполнителей</b>\n\n⚙️ В разработке", reply_markup=get_admin_menu(), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "admin_auto_archive")
async def admin_auto_archive(callback: types.CallbackQuery):
    await smart_edit_or_send(callback, "📦 <b>Автоархив</b>\n\n⚙️ В разработке", reply_markup=get_admin_menu(), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "admin_auto_clean")
async def admin_auto_clean(callback: types.CallbackQuery):
    await smart_edit_or_send(callback, "🗑️ <b>Автоочистка</b>\n\n⚙️ В разработке", reply_markup=get_admin_menu(), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "admin_welcome_text")
async def admin_welcome_text(callback: types.CallbackQuery):
    await smart_edit_or_send(callback, "👋 <b>Приветствие</b>\n\n⚙️ В разработке", reply_markup=get_admin_menu(), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "admin_faq")
async def admin_faq(callback: types.CallbackQuery):
    await smart_edit_or_send(callback, "❓ <b>FAQ</b>\n\n⚙️ В разработке", reply_markup=get_admin_menu(), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "faq")
async def faq_handler(callback: types.CallbackQuery, state: FSMContext):
    """Открывает первый слайд обучения"""
    user = await db.get_user(callback.from_user.id)
    
    # Выбираем слайды для текущей роли
    if user and user.get('user_role') == 'executor':
        slides = get_executor_slides()
    else:
        slides = get_customer_slides()
    
    # Установим текущий слайд (0)
    await state.set_state(TutorialSlides.slide_number)
    await state.update_data(slide_number=0)
    
    # Показываем первый слайд
    slide = slides[0]
    slide_text = (
        f"📚 <b>ОБУЧЕНИЕ</b>\n\n"
        f"<b>{slide['title']}</b>\n\n"
        f"{slide['description']}\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>Найдите кнопку:</b> <b>{slide['button_highlight']}</b>"
    )
    
    keyboard = get_tutorial_keyboard(0, len(slides))
    await smart_edit_or_send(callback, slide_text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data.startswith("slide_next_"))
async def slide_next(callback: types.CallbackQuery, state: FSMContext):
    """Переход к следующему слайду"""
    user = await db.get_user(callback.from_user.id)
    
    # Выбираем слайды
    if user and user.get('user_role') == 'executor':
        slides = get_executor_slides()
    else:
        slides = get_customer_slides()
    
    # Получаем текущий слайд
    data = await state.get_data()
    current_slide = data.get('slide_number', 0)
    next_slide = current_slide + 1
    
    if next_slide < len(slides):
        await state.update_data(slide_number=next_slide)
        
        slide = slides[next_slide]
        slide_text = (
            f"📚 <b>ОБУЧЕНИЕ</b>\n\n"
            f"<b>{slide['title']}</b>\n\n"
            f"{slide['description']}\n\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"🎯 <b>Найдите кнопку:</b> <b>{slide['button_highlight']}</b>"
        )
        
        keyboard = get_tutorial_keyboard(next_slide, len(slides))
        await smart_edit_or_send(callback, slide_text, reply_markup=keyboard, parse_mode="HTML")
    
    await callback.answer()

@dp.callback_query(F.data.startswith("slide_prev_"))
async def slide_prev(callback: types.CallbackQuery, state: FSMContext):
    """Переход к предыдущему слайду"""
    user = await db.get_user(callback.from_user.id)
    
    # Выбираем слайды
    if user and user.get('user_role') == 'executor':
        slides = get_executor_slides()
    else:
        slides = get_customer_slides()
    
    # Получаем текущий слайд
    data = await state.get_data()
    current_slide = data.get('slide_number', 0)
    prev_slide = current_slide - 1
    
    if prev_slide >= 0:
        await state.update_data(slide_number=prev_slide)
        
        slide = slides[prev_slide]
        slide_text = (
            f"📚 <b>ОБУЧЕНИЕ</b>\n\n"
            f"<b>{slide['title']}</b>\n\n"
            f"{slide['description']}\n\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"🎯 <b>Найдите кнопку:</b> <b>{slide['button_highlight']}</b>"
        )
        
        keyboard = get_tutorial_keyboard(prev_slide, len(slides))
        await smart_edit_or_send(callback, slide_text, reply_markup=keyboard, parse_mode="HTML")
    
    await callback.answer()

@dp.callback_query(F.data == "faq_back_to_menu")
async def faq_back_to_menu(callback: types.CallbackQuery, state: FSMContext):
    """Выход из слайдов обучения"""
    user = await db.get_user(callback.from_user.id)
    
    # Очищаем состояние
    await state.clear()
    
    # Возвращаемся в меню текущей роли
    if user and user.get('user_role') == 'executor':
        await smart_edit_or_send(callback, get_executor_panel_text(user), reply_markup=get_executor_menu(user), parse_mode="HTML")
    else:
        await smart_edit_or_send(callback, get_customer_panel_text(user), reply_markup=get_customer_menu(user), parse_mode="HTML")
    
    await callback.answer()

# ============================================
# УНИВЕРСАЛЬНЫЙ ОБРАБОТЧИК УДАЛЕНИЯ СООБЩЕНИЙ
# ============================================

@dp.message()
async def delete_user_messages(message: types.Message):
    """Удаляет все сообщения пользователя для чистоты чата (кроме команд и специальных)"""
    try:
        # Не удаляем команды - они удаляются в соответствующих обработчиках
        if message.text and message.text.startswith('/'):
            return
        
        # Удаляем сообщение пользователя
        await message.delete()
    except Exception as e:
        logger.debug(f"Could not delete message: {e}")

# ============================================
# ОСНОВНАЯ ФУНКЦИЯ ЗАПУСКА
# ============================================

async def main():
    await db.connect()
    
    # Инициализируем базы паттернов и whitelist
    await db.init_moderation_patterns()
    await db.init_whitelist()
    
    # Устанавливаем кнопку меню бота
    from aiogram.types import BotCommand, BotCommandScopeDefault
    commands = [
        BotCommand(command="start", description="Перезапустить бота"),
        BotCommand(command="s", description="Сменить роль")
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
    
    logger.info("Bot started!")
    
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
