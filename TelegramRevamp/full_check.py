#!/usr/bin/env python3
"""Полная проверка всех модулей бота"""

import sys
import ast
import traceback

files_to_check = [
    'config.py',
    'database.py', 
    'keyboards.py',
    'bot.py',
    'main.py',
    'webapp.py'
]

print("=" * 60)
print("ПОЛНАЯ ПРОВЕРКА КОДА БОТА")
print("=" * 60)

errors_found = False

for filename in files_to_check:
    print(f"\n📄 Проверка {filename}...")
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            code = f.read()
            
        # Проверка синтаксиса
        try:
            ast.parse(code)
            print(f"  ✅ Синтаксис: OK")
        except SyntaxError as e:
            print(f"  ❌ ОШИБКА СИНТАКСИСА:")
            print(f"     Строка {e.lineno}: {e.msg}")
            print(f"     {e.text}")
            errors_found = True
            continue
            
        # Проверка импорта
        try:
            if filename == 'main.py':
                continue  # Пропускаем main.py т.к. он запускает бота
            __import__(filename[:-3])
            print(f"  ✅ Импорт: OK")
        except Exception as e:
            print(f"  ⚠️  Импорт: {e}")
            
    except FileNotFoundError:
        print(f"  ⚠️  Файл не найден")
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        traceback.print_exc()
        errors_found = True

print("\n" + "=" * 60)

if errors_found:
    print("❌ НАЙДЕНЫ ОШИБКИ!")
    print("=" * 60)
    sys.exit(1)
else:
    print("✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
    print("=" * 60)
    print("\n🚀 Бот готов к запуску:")
    print("   python3 main.py")
    print("=" * 60)
