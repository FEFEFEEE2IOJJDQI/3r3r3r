"""
Telegram Bot - Точка входа
Запуск основного приложения и инициализация всех сервисов
"""
import asyncio
import logging
from bot import dp, bot, db

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Основная функция для запуска бота"""
    logger.info("🚀 Запуск Telegram бота...")
    
    try:
        # Попытка подключения к БД
        try:
            await db.connect()
            logger.info("✅ Подключение к БД успешно")
        except Exception as db_error:
            logger.warning(f"⚠️ Не удалось подключиться к БД: {db_error}")
            logger.info("   Бот работает в режиме без БД")
        
        async def cleanup_worker():
            """Периодически чистит записи о последних сообщениях, чтобы не копился мусор."""
            while True:
                await asyncio.sleep(3600)
                if db.is_connected():
                    try:
                        await db.prune_old_bot_messages(hours=48)
                        logger.debug("🧹 Очистка старых записей user_bot_messages завершена")
                    except Exception as clean_err:
                        logger.debug(f"Не удалось очистить старые записи user_bot_messages: {clean_err}")

        # Пропускаем все накопившиеся обновления при запуске (только старые)
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("🗑️ Старые обновления пропущены")
        
        # Запуск фоновой уборки и polling
        asyncio.create_task(cleanup_worker())
        logger.info("📡 Бот начал слушать сообщения...")
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        raise
    finally:
        logger.info("🛑 Бот остановлен")
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⚠️ Бот остановлен пользователем")
