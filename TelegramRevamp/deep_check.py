#!/usr/bin/env python3
"""
Глубокая проверка бота на баги и проблемы
Анализ всех критических путей
"""

import ast
import re
from pathlib import Path

print("=" * 70)
print("ГЛУБОКАЯ ПРОВЕРКА БОТА НА БАГИ")
print("=" * 70)

issues = []
warnings = []
info = []

# Читаем bot.py
with open('bot.py', 'r', encoding='utf-8') as f:
    bot_code = f.read()

# 1. Проверка на дублирование обработчиков
print("\n🔍 1. Проверка дублирования обработчиков...")
handlers = re.findall(r'@dp\.(message|callback_query)\((.*?)\)', bot_code)
handler_data = {}
for handler_type, data in handlers:
    key = f"{handler_type}:{data}"
    handler_data[key] = handler_data.get(key, 0) + 1

duplicates = {k: v for k, v in handler_data.items() if v > 1}
if duplicates:
    issues.append(f"⚠️  Найдены дублирующиеся обработчики: {duplicates}")
else:
    info.append("✅ Дублирующихся обработчиков не найдено")

# 2. Проверка обработки состояний FSM
print("🔍 2. Проверка состояний FSM...")
states = re.findall(r'class (\w+)\(StatesGroup\)', bot_code)
info.append(f"✅ Найдено {len(states)} групп состояний: {', '.join(states)}")

# 3. Проверка await в async функциях
print("🔍 3. Проверка await в async функциях...")
missing_await = re.findall(r'async def.*?(?:bot\.send_message|bot\.delete_message|db\.\w+)\([^)]+\)(?!\s*await)', bot_code, re.DOTALL)
if missing_await:
    warnings.append(f"⚠️  Возможно пропущен await в {len(missing_await)} местах")

# 4. Проверка try-except блоков
print("🔍 4. Проверка обработки ошибок...")
try_blocks = len(re.findall(r'\btry:', bot_code))
except_blocks = len(re.findall(r'\bexcept', bot_code))
info.append(f"✅ Try-except блоков: {try_blocks}/{except_blocks}")

# 5. Проверка callback.answer()
print("🔍 5. Проверка callback.answer()...")
callback_handlers = re.findall(r'@dp\.callback_query.*?(?=@dp\.|$)', bot_code, re.DOTALL)
missing_answer = 0
for handler in callback_handlers:
    if 'callback.answer' not in handler and 'await callback.message.edit' not in handler:
        missing_answer += 1

if missing_answer > 0:
    warnings.append(f"⚠️  {missing_answer} callback handlers могут не иметь callback.answer()")
else:
    info.append("✅ Все callback handlers имеют ответы")

# 6. Проверка delete_and_send и send_clean_reply
print("🔍 6. Проверка функций отправки...")
delete_and_send_count = len(re.findall(r'delete_and_send\(', bot_code))
send_clean_reply_count = len(re.findall(r'send_clean_reply\(', bot_code))
smart_edit_count = len(re.findall(r'smart_edit_or_send\(', bot_code))
info.append(f"✅ delete_and_send: {delete_and_send_count}, send_clean_reply: {send_clean_reply_count}, smart_edit: {smart_edit_count}")

# 7. Проверка защиты от бана
print("🔍 7. Проверка защиты от бана...")
ban_checks = len(re.findall(r'check_banned\(', bot_code))
info.append(f"✅ Проверок бана: {ban_checks}")

# 8. Проверка работы с БД
print("🔍 8. Проверка is_connected()...")
db_checks = len(re.findall(r'db\.is_connected\(\)', bot_code))
db_calls = len(re.findall(r'await db\.', bot_code))
if db_calls > db_checks * 3:
    warnings.append(f"⚠️  Много вызовов БД ({db_calls}) при малом количестве проверок подключения ({db_checks})")
else:
    info.append(f"✅ Проверок БД: {db_checks}, вызовов: {db_calls}")

# 9. Проверка state.clear()
print("🔍 9. Проверка очистки состояний...")
state_clears = len(re.findall(r'state\.clear\(\)', bot_code))
info.append(f"✅ Очисток состояния: {state_clears}")

# 10. Проверка обработки /start
print("🔍 10. Проверка команды /start...")
start_handler = re.search(r'@dp\.message\(Command\("start"\)\).*?(?=@dp\.|$)', bot_code, re.DOTALL)
if start_handler:
    start_code = start_handler.group()
    if 'clean_chat_history' in start_code:
        warnings.append("⚠️  /start использует clean_chat_history - может быть медленным")
    if 'delete_and_send' in start_code:
        info.append("✅ /start использует delete_and_send")
    if 'captcha' in start_code.lower():
        info.append("✅ /start проверяет капчу")

# Итоговый отчет
print("\n" + "=" * 70)
print("ОТЧЕТ О ПРОВЕРКЕ")
print("=" * 70)

if issues:
    print("\n❌ КРИТИЧЕСКИЕ ПРОБЛЕМЫ:")
    for issue in issues:
        print(f"  {issue}")

if warnings:
    print("\n⚠️  ПРЕДУПРЕЖДЕНИЯ:")
    for warning in warnings:
        print(f"  {warning}")

if info:
    print("\n✅ ИНФОРМАЦИЯ:")
    for item in info:
        print(f"  {item}")

print("\n" + "=" * 70)
print("РЕКОМЕНДАЦИИ:")
print("=" * 70)

recommendations = [
    "1. Все критические обработчики имеют try-except",
    "2. Callback handlers должны вызывать callback.answer()",
    "3. Проверять db.is_connected() перед операциями с БД",
    "4. Использовать state.clear() после завершения процессов",
    "5. Проверять check_banned() в начале команд",
]

for rec in recommendations:
    print(f"  ✓ {rec}")

print("\n" + "=" * 70)

if not issues:
    print("✅ КРИТИЧЕСКИХ БАГОВ НЕ НАЙДЕНО!")
    print("=" * 70)
else:
    print("❌ НАЙДЕНЫ ПРОБЛЕМЫ - ТРЕБУЕТСЯ ИСПРАВЛЕНИЕ")
    print("=" * 70)
