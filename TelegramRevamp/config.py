"""
Конфигурация бота
Все константы и переменные окружения в одном месте
"""
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()
load_dotenv("telebot.env")

# ==================== TELEGRAM SETTINGS ====================
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8573231093:AAGzONKrZ_OVz_dfjGepG5rpDe66z2cyeQM')
ADMIN_CODE = "4577"

# ==================== DATABASE SETTINGS ====================
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:4577@localhost:5432/postgres')

# ==================== WEB APP SETTINGS ====================
# Телеграм мини-приложение может жить на разных доменах (Replit, Codespaces, прод)
FLASK_PORT = int(os.getenv('FLASK_PORT', 5000))
EXPLICIT_WEBAPP_URL = os.getenv('WEBAPP_URL')
REPLIT_DEV_DOMAIN = os.getenv('REPLIT_DEV_DOMAIN')
_codespace = os.getenv('CODESPACE_NAME')
_codespace_domain = os.getenv('GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN')

def _normalize_host(host: str, secure: bool = True) -> str:
	if host.startswith('http://') or host.startswith('https://'):
		return host.rstrip('/')
	scheme = 'https' if secure else 'http'
	return f"{scheme}://{host}".rstrip('/')

if EXPLICIT_WEBAPP_URL:
	WEBAPP_URL = _normalize_host(EXPLICIT_WEBAPP_URL)
elif REPLIT_DEV_DOMAIN and REPLIT_DEV_DOMAIN not in {"localhost", "localhost:5000", "127.0.0.1", "127.0.0.1:5000"}:
	WEBAPP_URL = _normalize_host(REPLIT_DEV_DOMAIN)
elif _codespace and _codespace_domain:
	# GitHub Codespaces публикует порты по паттерну <name>-<port>.<domain>
	WEBAPP_URL = _normalize_host(f"{_codespace}-{FLASK_PORT}.{_codespace_domain}")
else:
	# Локальный режим – Telegram Mini App не откроется, но ссылка пригодится для браузера
	WEBAPP_URL = _normalize_host(f"localhost:{FLASK_PORT}", secure=False)

# ==================== LOGGING SETTINGS ====================
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# ==================== TIME SETTINGS ====================
APP_TIMEZONE = os.getenv('APP_TIMEZONE', 'Europe/Moscow')

# ==================== BOT SETTINGS ====================
MAX_MESSAGE_LENGTH = 4096
TIMEOUT = 30

# ==================== PAGINATION ====================
ORDERS_PER_PAGE = 5
USERS_PER_PAGE = 10

# ==================== RATE LIMITING ====================
RATE_LIMIT_ENABLED = os.getenv('RATE_LIMIT_ENABLED', 'true').lower() == 'true'
RATE_LIMIT_CALLS = 30  # количество вызовов
RATE_LIMIT_PERIOD = 60  # за период в секундах

print(f"✅ Конфигурация загружена")
print(f"   Токен: {'***' + TELEGRAM_BOT_TOKEN[-4:]}")
print(f"   БД: {DATABASE_URL.split('@')[0]}***@{DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'localhost'}")
